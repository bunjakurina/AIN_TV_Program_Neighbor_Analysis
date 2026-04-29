"""Premier optimized scheduler — channel-aware extended horizon + overlap discipline."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Sequence, Tuple

from neighbor_engine import (
    PremierParams,
    calculate_statistics,
    compute_premier_neighbors,
    default_premier_params,
)

# Skip writing full premier JSON when estimated size exceeds this (neighbor_indices dominates).
_DEFAULT_MB = int(os.environ.get("PREMIER_MAX_OUTPUT_MB", "120"))
PREMIER_MAX_OUTPUT_BYTES_ESTIMATE = max(8, _DEFAULT_MB) * 1024 * 1024


def estimate_premier_output_json_bytes(programs: Sequence[Dict[str, Any]], neighbors: Sequence[Sequence[int]]) -> int:
    """
    Cheap upper-bound estimate for indented JSON size (programs + neighbor_indices).
    Avoids serializing to disk when the result would be enormous.
    """
    n = len(programs)
    edges = sum(len(x) for x in neighbors)
    # Indented JSON: neighbor ints + brackets/commas/newlines; programs metadata per row.
    neighbor_blob = edges * 20
    programs_blob = n * 240
    return int(neighbor_blob + programs_blob + 12288)


def premier_should_skip_json_write(
    programs: Sequence[Dict[str, Any]],
    neighbors: Sequence[Sequence[int]],
    max_bytes: Optional[int] = None,
) -> Tuple[bool, int]:
    """
    Returns (skip_write, estimated_bytes). When skip_write is True, callers should not
    write the full premier output JSON (statistics may still be printed).
    """
    lim = max_bytes if max_bytes is not None else PREMIER_MAX_OUTPUT_BYTES_ESTIMATE
    est = estimate_premier_output_json_bytes(programs, neighbors)
    return est > lim, est


def generate_premier_neighbors(programs, starts, params=None):
    effective = params if params is not None else default_premier_params()
    return compute_premier_neighbors(programs, starts, effective)
