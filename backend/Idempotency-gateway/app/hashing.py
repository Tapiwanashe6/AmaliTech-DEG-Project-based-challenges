"""Stable request-body hashing.

Two semantically-identical request bodies can arrive with keys in
different orders (e.g. ``{"amount":1,"currency":"USD"}`` vs
``{"currency":"USD","amount":1}``). A naive ``json.dumps`` yields different
strings and therefore different hashes, which would incorrectly classify
them as conflicting bodies under the same Idempotency-Key.

We canonicalize by recursively sorting object keys before hashing.
Arrays are left in their original order (order is semantically
significant for lists).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonicalize(value: Any) -> Any:
    """Return a value with all nested dict keys sorted lexicographically."""
    if isinstance(value, dict):
        return {k: canonicalize(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        return [canonicalize(v) for v in value]
    return value


def hash_body(body: Any) -> str:
    """SHA-256 hex digest of a JSON-serializable body, order-independent."""
    canonical = json.dumps(canonicalize(body if body is not None else {}),
                           separators=(",", ":"), sort_keys=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
