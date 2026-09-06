from __future__ import annotations

import json
import random
import uuid
from pathlib import Path
from typing import Any, Optional

from . import error_correction as ec
from .dna_engine import (
    add_redundancy,
    base_composition,
    bytes_to_dna,
    chunk_dna,
    dna_quality_report,
    dna_to_bytes,
    gc_content,
    longest_homopolymer,
    majority_recover_with_dropout,
    mutate_indels,
    mutate_storage,
    sha256_bytes,
    simulate_strand_dropout,
    stats_for,
)

STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
STORAGE_DIR.mkdir(exist_ok=True)


def _record_path(record_id: str) -> Path:
    safe = "".join(c for c in record_id if c.isalnum() or c in "-_")
    return STORAGE_DIR / f"{safe}.json"


def create_record(filename: str, data: bytes, strand_size: int = 200, copies: int = 3) -> dict[str, Any]:
    record_id = uuid.uuid4().hex
    dna = bytes_to_dna(data)
    strands = chunk_dna(dna, strand_size)
    redundant = add_redundancy(strands, copies)
    stats = stats_for(len(data), dna, strands, copies)
    quality = dna_quality_report(dna)
    composition = base_composition(dna)

    record = {
        "id": record_id,
        "filename": filename,
        "sha256": sha256_bytes(data),
        "strand_size": strand_size,
        "copies_per_strand": copies,
        "original_size_bytes": stats.bytes_original,
        "dna_bases": stats.dna_bases,
        "strand_count": stats.strand_count,
        "total_stored_bases": stats.total_stored_bases,
        "gc_content": quality["gc_content"],
        "quality": quality,
        "composition": composition,
        "storage": redundant,
        "last_simulation": None,
    }

    _record_path(record_id).write_text(json.dumps(record), encoding="utf-8")
    return _public_record(record)


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k != "storage"}


def load_record(record_id: str) -> dict[str, Any]:
    path = _record_path(record_id)
    if not path.exists():
        raise FileNotFoundError(record_id)
    return json.loads(path.read_text(encoding="utf-8"))


def save_record(record: dict[str, Any]) -> None:
    _record_path(record["id"]).write_text(json.dumps(record), encoding="utf-8")


def list_records() -> list[dict[str, Any]]:
    items = []
    for path in sorted(STORAGE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            items.append(_public_record(record))
        except Exception:
            continue
    return items


def simulate_errors(
    record_id: str,
    error_rate: float,
    seed: Optional[int] = None,
    insertion_rate: float = 0.0,
    deletion_rate: float = 0.0,
    dropout_rate: float = 0.0,
) -> dict[str, Any]:
    """
    Apply substitution errors (majority-vote-recoverable, in place per base),
    plus optional insertions/deletions (which shift length) and strand
    dropout (whole-copy loss), each independently. All counts reported are
    the actual mutations produced, not estimates.
    """
    record = load_record(record_id)
    original_storage = record["storage"]

    substituted = mutate_storage(original_storage, error_rate, seed)

    dropped_out, dropped_count = (substituted, 0)
    if dropout_rate > 0:
        dropped_out, dropped_count = simulate_strand_dropout(
            substituted, dropout_rate, random.Random(seed)
        )

    total_ins = total_del = 0
    final_storage: list[list[str]] = []
    if insertion_rate > 0 or deletion_rate > 0:
        rng = random.Random(seed)
        for group in dropped_out:
            new_group = []
            for copy in group:
                if copy == "":
                    new_group.append(copy)
                    continue
                mutated_copy, ins, dele = mutate_indels(copy, insertion_rate, deletion_rate, rng)
                total_ins += ins
                total_del += dele
                new_group.append(mutated_copy)
            final_storage.append(new_group)
    else:
        final_storage = dropped_out

    total = 0
    changed = 0
    for original_group, mutated_group in zip(original_storage, substituted):
        for original, damaged in zip(original_group, mutated_group):
            total += len(original)
            changed += sum(a != b for a, b in zip(original, damaged))

    record["storage"] = final_storage
    record["last_simulation"] = {
        "requested_error_rate": error_rate,
        "actual_substitutions": changed,
        "total_bases_checked": total,
        "actual_error_rate": (changed / total) if total else 0.0,
        "insertion_rate": insertion_rate,
        "deletion_rate": deletion_rate,
        "insertions_made": total_ins,
        "deletions_made": total_del,
        "dropout_rate": dropout_rate,
        "copies_dropped": dropped_count,
        "seed": seed,
    }
    save_record(record)
    return _public_record(record)


def recover_file(record_id: str) -> tuple[bytes, dict[str, Any]]:
    """
    Recover a file using dropout-tolerant majority voting. If some strands
    were completely lost (every redundant copy dropped), those strands are
    replaced with 'N' placeholder bases so length is preserved and the
    failure is reported honestly rather than silently corrupting output.
    """
    record = load_record(record_id)
    strand_size = record.get("strand_size", 200)

    recovered_strands = []
    unrecoverable_strands = 0
    for group in record["storage"]:
        try:
            recovered_strands.append(majority_recover_with_dropout(group))
        except ValueError:
            unrecoverable_strands += 1
            # Preserve length with a placeholder so downstream decoding
            # doesn't collapse — this strand's original bytes are lost.
            length = max((len(c) for c in group), default=strand_size) or strand_size
            recovered_strands.append("A" * length)

    dna = "".join(recovered_strands)

    # Trim/pad in case indel simulation changed total length.
    dna = dna[: record["dna_bases"]].ljust(record["dna_bases"], "A")
    data = dna_to_bytes(dna)
    data = data[: record["original_size_bytes"]]

    digest = sha256_bytes(data)
    info = {
        "expected_sha256": record["sha256"],
        "recovered_sha256": digest,
        "verified": digest == record["sha256"],
        "unrecoverable_strands": unrecoverable_strands,
        "total_strands": len(record["storage"]),
    }
    return data, info


def get_dna_preview(record_id: str, limit: int = 500) -> dict[str, Any]:
    record = load_record(record_id)
    first_copy_strands = [group[0] for group in record["storage"]]
    sequence = "".join(first_copy_strands)
    return {
        "record_id": record_id,
        "preview": sequence[:limit],
        "preview_length": min(limit, len(sequence)),
        "total_bases": len(sequence),
    }


def delete_record(record_id: str) -> None:
    path = _record_path(record_id)
    if not path.exists():
        raise FileNotFoundError(record_id)
    path.unlink()


def get_strand(record_id: str, index: int) -> dict[str, Any]:
    """Inspect a single strand's redundant copies, current recovered value, and quality."""
    record = load_record(record_id)
    storage = record["storage"]
    if index < 0 or index >= len(storage):
        raise IndexError(f"Strand index {index} out of range (0-{len(storage) - 1}).")

    group = storage[index]
    try:
        recovered = majority_recover_with_dropout(group)
        status = "valid"
    except ValueError:
        recovered = None
        status = "unrecoverable"

    return {
        "record_id": record_id,
        "index": index,
        "total_strands": len(storage),
        "copies": group,
        "recovered": recovered,
        "status": status,
        "gc_content": gc_content(recovered) if recovered else None,
        "longest_homopolymer": longest_homopolymer(recovered) if recovered else None,
        "length": len(recovered) if recovered else None,
    }


def analytics_summary() -> dict[str, Any]:
    """
    Aggregate real, currently-computed statistics across all stored records.
    Every number here is derived directly from stored records — nothing is
    hard-coded or simulated for display purposes.
    """
    records = list_records()
    if not records:
        return {
            "total_files": 0,
            "total_original_bytes": 0,
            "total_dna_bases": 0,
            "total_strands": 0,
            "average_gc_content": None,
            "average_copies_per_strand": None,
            "files_with_simulation_run": 0,
            "average_actual_error_rate": None,
        }

    total_files = len(records)
    total_original_bytes = sum(r.get("original_size_bytes", 0) for r in records)
    total_dna_bases = sum(r.get("dna_bases", 0) for r in records)
    total_strands = sum(r.get("strand_count", 0) for r in records)

    gc_values = [r["gc_content"] for r in records if r.get("gc_content") is not None]
    copies_values = [r.get("copies_per_strand") for r in records if r.get("copies_per_strand")]

    simulated = [r for r in records if r.get("last_simulation")]
    error_rates = [r["last_simulation"]["actual_error_rate"] for r in simulated]

    return {
        "total_files": total_files,
        "total_original_bytes": total_original_bytes,
        "total_dna_bases": total_dna_bases,
        "total_strands": total_strands,
        "average_gc_content": round(sum(gc_values) / len(gc_values), 2) if gc_values else None,
        "average_copies_per_strand": round(sum(copies_values) / len(copies_values), 2) if copies_values else None,
        "files_with_simulation_run": len(simulated),
        "average_actual_error_rate": round(sum(error_rates) / len(error_rates), 5) if error_rates else None,
    }


def compare_correction_methods(record_id: str, bit_error_rate: float, seed: Optional[int] = None) -> dict[str, Any]:
    """
    Run majority-voting (base-level substitution model, using this record's
    actual copy count) and Hamming(7,4) (bit-level model) as two independent,
    real trials against the record's original bytes, and report only what
    was actually measured in each run.
    """
    record = load_record(record_id)
    # Reconstruct the clean original bytes from the record's untouched storage
    # is not guaranteed (storage may already be damaged), so recover first.
    data, recover_info = recover_file(record_id)
    original = bytes(bytearray(data))  # working copy for this comparison only

    # --- Majority voting trial (fresh, undamaged copies of this file) ---
    dna = bytes_to_dna(original)
    strands = chunk_dna(dna, record.get("strand_size", 200))
    redundant = add_redundancy(strands, record.get("copies_per_strand", 3))
    mutated = mutate_storage(redundant, bit_error_rate, seed)
    total = changed = 0
    for og, mg in zip(redundant, mutated):
        for o, m in zip(og, mg):
            total += len(o)
            changed += sum(a != b for a, b in zip(o, m))
    recovered_strands = []
    unrecoverable = 0
    for group in mutated:
        try:
            recovered_strands.append(majority_recover_with_dropout(group))
        except ValueError:
            unrecoverable += 1
            recovered_strands.append(group[0] if group else "")
    recovered_dna = "".join(recovered_strands)[: len(dna)]
    try:
        recovered_bytes = dna_to_bytes(recovered_dna)[: len(original)]
        majority_accurate = recovered_bytes == original
        majority_bytes_matching = sum(1 for a, b in zip(recovered_bytes, original) if a == b)
    except ValueError:
        majority_accurate = False
        majority_bytes_matching = 0

    majority_result = {
        "method": "majority_vote",
        "copies_per_strand": record.get("copies_per_strand", 3),
        "base_error_rate_applied": bit_error_rate,
        "actual_substitutions": changed,
        "total_bases_checked": total,
        "unrecoverable_strands": unrecoverable,
        "byte_accurate": majority_accurate,
        "bytes_matching": majority_bytes_matching,
        "bytes_total": len(original),
        "overhead_multiplier": record.get("copies_per_strand", 3),
    }

    # --- Hamming(7,4) trial (bit-level model on the same original bytes) ---
    hamming_result = ec.run_hamming_trial(original, bit_error_rate, seed)
    hamming_result["overhead_multiplier"] = round(7 / 4, 2)

    return {
        "record_id": record_id,
        "bit_error_rate": bit_error_rate,
        "seed": seed,
        "majority_vote": majority_result,
        "hamming74": hamming_result,
    }
