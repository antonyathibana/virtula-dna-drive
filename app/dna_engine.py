from __future__ import annotations

import hashlib
import random
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Optional

BITS_TO_BASE = {
    "00": "A",
    "01": "C",
    "10": "G",
    "11": "T",
}
BASE_TO_BITS = {v: k for k, v in BITS_TO_BASE.items()}
BASES = "ACGT"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bytes_to_dna(data: bytes) -> str:
    """Encode arbitrary bytes into a 2-bit-per-base virtual DNA sequence."""
    pieces: list[str] = []
    for byte in data:
        bits = f"{byte:08b}"
        pieces.extend(BITS_TO_BASE[bits[i:i+2]] for i in range(0, 8, 2))
    return "".join(pieces)


def dna_to_bytes(dna: str) -> bytes:
    """Decode a virtual DNA sequence created by bytes_to_dna()."""
    if len(dna) % 4 != 0:
        raise ValueError("DNA length must be divisible by 4 bases.")

    try:
        bits = "".join(BASE_TO_BITS[base] for base in dna)
    except KeyError as exc:
        raise ValueError(f"Invalid DNA base: {exc.args[0]}") from exc

    return bytes(int(bits[i:i+8], 2) for i in range(0, len(bits), 8))


def chunk_dna(dna: str, strand_size: int = 200) -> list[str]:
    if strand_size <= 0:
        raise ValueError("strand_size must be greater than 0")
    return [dna[i:i+strand_size] for i in range(0, len(dna), strand_size)]


def add_redundancy(strands: Iterable[str], copies: int = 3) -> list[list[str]]:
    if copies < 1:
        raise ValueError("copies must be at least 1")
    return [[strand for _ in range(copies)] for strand in strands]


def mutate_substitutions(sequence: str, error_rate: float, rng: Optional[random.Random] = None) -> str:
    """Randomly replace bases. error_rate is between 0.0 and 1.0."""
    if not 0 <= error_rate <= 1:
        raise ValueError("error_rate must be between 0 and 1")

    rng = rng or random.Random()
    out = []
    for base in sequence:
        if rng.random() < error_rate:
            choices = [b for b in BASES if b != base]
            out.append(rng.choice(choices))
        else:
            out.append(base)
    return "".join(out)


def mutate_storage(
    redundant_strands: list[list[str]],
    error_rate: float,
    seed: Optional[int] = None,
) -> list[list[str]]:
    rng = random.Random(seed)
    return [
        [mutate_substitutions(copy, error_rate, rng) for copy in group]
        for group in redundant_strands
    ]


def majority_recover(copies: list[str]) -> str:
    """Recover one strand using majority vote at each base position."""
    if not copies:
        raise ValueError("At least one copy is required.")

    lengths = {len(x) for x in copies}
    if len(lengths) != 1:
        raise ValueError("All redundant copies must have the same length.")

    recovered = []
    for column in zip(*copies):
        counts = Counter(column)
        recovered.append(counts.most_common(1)[0][0])
    return "".join(recovered)


def recover_all(redundant_strands: list[list[str]]) -> list[str]:
    return [majority_recover(group) for group in redundant_strands]


@dataclass
class DNAStats:
    bytes_original: int
    dna_bases: int
    strand_count: int
    copies_per_strand: int
    total_stored_bases: int


def stats_for(data_len: int, dna: str, strands: list[str], copies: int) -> DNAStats:
    return DNAStats(
        bytes_original=data_len,
        dna_bases=len(dna),
        strand_count=len(strands),
        copies_per_strand=copies,
        total_stored_bases=sum(len(s) for s in strands) * copies,
    )


# ---------------------------------------------------------------------------
# DNA quality metrics (real, computed from the sequence — not simulated)
# ---------------------------------------------------------------------------

def gc_content(sequence: str) -> float:
    """Percentage of G/C bases in the sequence. Returns 0.0 for empty input."""
    if not sequence:
        return 0.0
    gc = sum(1 for b in sequence if b in ("G", "C"))
    return round(gc / len(sequence) * 100, 2)


def longest_homopolymer(sequence: str) -> int:
    """Length of the longest run of a single repeated base."""
    if not sequence:
        return 0
    longest = current = 1
    for i in range(1, len(sequence)):
        if sequence[i] == sequence[i - 1]:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def dna_quality_report(sequence: str, min_length: int = 20, max_length: int = 10000) -> dict:
    """
    Score a DNA sequence against simple, realistic synthesis constraints.
    This mirrors published DNA-storage guidance (balanced GC%, no long
    homopolymer runs) but is a heuristic check, not a lab measurement.
    """
    gc = gc_content(sequence)
    homopolymer = longest_homopolymer(sequence)
    length = len(sequence)

    gc_ok = 40.0 <= gc <= 60.0
    homopolymer_ok = homopolymer <= 4
    length_ok = min_length <= length <= max_length

    checks_passed = sum([gc_ok, homopolymer_ok, length_ok])
    overall_score = round(checks_passed / 3 * 100, 1)

    return {
        "gc_content": gc,
        "gc_ok": gc_ok,
        "longest_homopolymer": homopolymer,
        "homopolymer_ok": homopolymer_ok,
        "length": length,
        "length_ok": length_ok,
        "overall_score": overall_score,
    }


def base_composition(sequence: str) -> dict:
    """Count of each base — used for the A/C/G/T composition chart."""
    counts = Counter(sequence)
    return {base: counts.get(base, 0) for base in BASES}


# ---------------------------------------------------------------------------
# Extended error simulation: insertions, deletions, strand dropout.
# These change sequence length, unlike substitutions, so they are modeled
# and reported separately rather than folded into majority-vote recovery.
# ---------------------------------------------------------------------------

def mutate_indels(
    sequence: str,
    insertion_rate: float,
    deletion_rate: float,
    rng: Optional[random.Random] = None,
) -> tuple[str, int, int]:
    """
    Apply insertions and deletions base-by-base. Returns (mutated_sequence,
    insertions_made, deletions_made). Rates are independent per-base
    probabilities between 0 and 1.
    """
    if not 0 <= insertion_rate <= 1 or not 0 <= deletion_rate <= 1:
        raise ValueError("insertion_rate and deletion_rate must be between 0 and 1")

    rng = rng or random.Random()
    out = []
    insertions = 0
    deletions = 0
    for base in sequence:
        if rng.random() < deletion_rate:
            deletions += 1
            continue  # base dropped
        out.append(base)
        if rng.random() < insertion_rate:
            out.append(rng.choice(BASES))
            insertions += 1
    return "".join(out), insertions, deletions


def simulate_strand_dropout(
    redundant_strands: list[list[str]],
    dropout_rate: float,
    rng: Optional[random.Random] = None,
) -> tuple[list[list[str]], int]:
    """
    Simulate total loss of individual redundant copies (e.g. a molecule that
    was never sequenced). A dropped copy is marked as an empty string so
    majority-vote recovery can detect and skip it. Returns (result, dropped_count).
    """
    if not 0 <= dropout_rate <= 1:
        raise ValueError("dropout_rate must be between 0 and 1")

    rng = rng or random.Random()
    dropped = 0
    result = []
    for group in redundant_strands:
        new_group = []
        for copy in group:
            if rng.random() < dropout_rate:
                new_group.append("")
                dropped += 1
            else:
                new_group.append(copy)
        result.append(new_group)
    return result, dropped


def majority_recover_with_dropout(copies: list[str]) -> str:
    """
    Like majority_recover, but tolerant of dropped ("") copies: they are
    excluded from the vote. Raises ValueError if every copy was dropped or
    surviving copies disagree on length.
    """
    surviving = [c for c in copies if c != ""]
    if not surviving:
        raise ValueError("All redundant copies were lost — strand unrecoverable.")
    return majority_recover(surviving)
