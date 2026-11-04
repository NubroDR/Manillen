"""Shared normalization and ID-generation helpers for canonical references."""

import re
import secrets


ID_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
ID_SUFFIX_LENGTH = 5
ID_PREFIXES = {"player": "plr_", "location": "loc_"}
_RESERVE_REFERENCE = re.compile(
    r"^(?:RESERVE:([1-9]\d*)|Reserve\s+([1-9]\d*))$",
    re.IGNORECASE,
)


def normalize_reference_name(value):
    """Normalize spaces and case for exact, non-fuzzy reference matching."""
    return " ".join(str(value or "").split()).casefold()


def is_reserve_reference(value):
    """Return whether a value is a reserve placeholder rather than a person."""
    return reserve_reference_token(value) is not None


def reserve_reference_token(value):
    """Return a reserve placeholder in canonical ``RESERVE:n`` form."""
    match = _RESERVE_REFERENCE.fullmatch(str(value or "").strip())
    if not match:
        return None
    return f"RESERVE:{int(match.group(1) or match.group(2))}"


def generate_reference_id(kind, used_ids):
    """Generate a unique, short ID without deriving it from a display name."""
    try:
        prefix = ID_PREFIXES[kind]
    except KeyError as error:
        raise ValueError(f"Unsupported reference type: {kind}") from error

    for _ in range(10_000):
        candidate = prefix + "".join(
            secrets.choice(ID_ALPHABET) for _ in range(ID_SUFFIX_LENGTH)
        )
        if candidate not in used_ids:
            used_ids.add(candidate)
            return candidate
    raise RuntimeError(f"Unable to generate a unique {kind} ID after 10000 attempts.")
