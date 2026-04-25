from __future__ import annotations

import hashlib
import json
from typing import Any


# sort keys recursively so {"a":1,"b":2} and {"b":2,"a":1} produce the same hash
def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: canonicalize(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        return [canonicalize(v) for v in value]
    return value


def hash_body(body: Any) -> str:
    canonical = json.dumps(canonicalize(body if body is not None else {}),
                           separators=(",", ":"), sort_keys=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
