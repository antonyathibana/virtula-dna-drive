"""
Real, working error-correction implementations used to compare strategies.

Two strategies are implemented honestly here:

1. Majority voting (see dna_engine.majority_recover) — corrects a wrong base
   at a given position as long as a majority of the redundant copies agree.

2. Hamming(7,4) — a genuine single-error-correcting linear block code,
   applied to the *bitstream* before it is translated into DNA bases. It
   corrects a single flipped bit per 7-bit block; it cannot correct a DNA
   base substitution that flips 2 of its 2 encoding bits at once, so its
   real-world accuracy on base-level substitution noise is reported as
   measured, not assumed.

No other coding scheme (e.g. Reed-Solomon) is implemented — do not report
metrics for schemes that aren't actually run.
"""

from __future__ import annotations

import random
from typing import Optional

# Hamming(7,4) generator/parity structure.
# Data bits d1 d2 d3 d4 -> codeword p1 p2 d1 p3 d2 d3 d4
_DATA_POSITIONS = [2, 4, 5, 6]   # 0-indexed positions of data bits in the 7-bit word
_PARITY_POSITIONS = [0, 1, 3]    # 0-indexed positions of parity bits


def _parity_covers(parity_index: int, bit_position_1indexed: int) -> bool:
    """Standard Hamming parity-coverage rule using 1-indexed bit positions."""
    return (bit_position_1indexed >> parity_index) & 1 == 1


def hamming74_encode_nibble(nibble: str) -> str:
    """Encode 4 data bits into a 7-bit Hamming codeword."""
    if len(nibble) != 4 or any(c not in "01" for c in nibble):
        raise ValueError("nibble must be exactly 4 bits ('0'/'1')")

    word = [0] * 7
    for i, pos in enumerate(_DATA_POSITIONS):
        word[pos] = int(nibble[i])

    for p_idx, p_pos in enumerate(_PARITY_POSITIONS):
        parity = 0
        for bit_pos in range(7):
            if bit_pos == p_pos:
                continue
            if _parity_covers(p_idx, bit_pos + 1) and word[bit_pos]:
                parity ^= 1
        word[p_pos] = parity

    return "".join(str(b) for b in word)


def hamming74_decode_codeword(codeword: str) -> tuple[str, bool]:
    """
    Decode a 7-bit Hamming codeword, correcting a single-bit error if present.
    Returns (4_data_bits, was_corrected).
    """
    if len(codeword) != 7 or any(c not in "01" for c in codeword):
        raise ValueError("codeword must be exactly 7 bits ('0'/'1')")

    word = [int(c) for c in codeword]
    syndrome = 0
    for p_idx, p_pos in enumerate(_PARITY_POSITIONS):
        parity = 0
        for bit_pos in range(7):
            if _parity_covers(p_idx, bit_pos + 1) and word[bit_pos]:
                parity ^= 1
        syndrome |= (parity << p_idx)

    corrected = False
    if syndrome != 0:
        error_pos = syndrome - 1
        if 0 <= error_pos < 7:
            word[error_pos] ^= 1
            corrected = True

    data = "".join(str(word[pos]) for pos in _DATA_POSITIONS)
    return data, corrected


def bytes_to_hamming_bits(data: bytes) -> str:
    """Convert bytes to a bitstream, then Hamming(7,4)-encode every 4 bits."""
    bits = "".join(f"{byte:08b}" for byte in data)
    # Pad to a multiple of 4 bits.
    pad = (-len(bits)) % 4
    bits += "0" * pad
    encoded = "".join(hamming74_encode_nibble(bits[i:i + 4]) for i in range(0, len(bits), 4))
    return encoded


def hamming_bits_to_bytes(encoded_bits: str, original_bit_length: int) -> tuple[bytes, int]:
    """
    Decode a Hamming(7,4)-encoded bitstream back to bytes, correcting
    single-bit errors per 7-bit block. Returns (data, corrections_made).
    """
    if len(encoded_bits) % 7 != 0:
        raise ValueError("Hamming-encoded bitstream length must be a multiple of 7.")

    data_bits = []
    corrections = 0
    for i in range(0, len(encoded_bits), 7):
        nibble, was_corrected = hamming74_decode_codeword(encoded_bits[i:i + 7])
        data_bits.append(nibble)
        if was_corrected:
            corrections += 1

    bits = "".join(data_bits)[:original_bit_length]
    pad = (-len(bits)) % 8
    bits += "0" * pad
    data = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
    return data[: original_bit_length // 8 + (1 if original_bit_length % 8 else 0)], corrections


def flip_random_bits(bits: str, error_rate: float, rng: Optional[random.Random] = None) -> tuple[str, int]:
    """Flip each bit independently with probability error_rate. Returns (bits, flips)."""
    if not 0 <= error_rate <= 1:
        raise ValueError("error_rate must be between 0 and 1")
    rng = rng or random.Random()
    out = []
    flips = 0
    for b in bits:
        if rng.random() < error_rate:
            out.append("1" if b == "0" else "0")
            flips += 1
        else:
            out.append(b)
    return "".join(out), flips


def run_hamming_trial(data: bytes, bit_error_rate: float, seed: Optional[int] = None) -> dict:
    """
    Encode data with Hamming(7,4), flip bits at bit_error_rate, decode with
    correction, and report real measured results (no fabricated numbers).
    """
    rng = random.Random(seed)
    original_bit_length = len(data) * 8

    encoded = bytes_to_hamming_bits(data)
    noisy, flips = flip_random_bits(encoded, bit_error_rate, rng)
    recovered, corrections = hamming_bits_to_bytes(noisy, original_bit_length)
    recovered = recovered[: len(data)]

    return {
        "method": "hamming74",
        "bit_error_rate": bit_error_rate,
        "bits_flipped": flips,
        "blocks_corrected": corrections,
        "total_blocks": len(encoded) // 7,
        "byte_accurate": recovered == data,
        "bytes_matching": sum(1 for a, b in zip(recovered, data) if a == b),
        "bytes_total": len(data),
    }
