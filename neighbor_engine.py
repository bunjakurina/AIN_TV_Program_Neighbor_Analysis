"""
Shared infrastructure for fast neighbor generation (bisect windows on sorted starts).

Complexity: O(N log N) sort + O(sum_i window_i) candidate checks; each check O(1).
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple


def flatten_programs(instance: Dict[str, Any]) -> List[Dict[str, Any]]:
    programs: List[Dict[str, Any]] = []
    gid = 0
    for channel in instance["channels"]:
        cid = channel["channel_id"]
        for program_index, program in enumerate(channel["programs"]):
            programs.append(
                {
                    "global_index": gid,
                    "program_id": program["program_id"],
                    "channel_id": cid,
                    "program_index": program_index,
                    "start": program["start"],
                    "end": program["end"],
                    "genre": program.get("genre"),
                    "score": program.get("score"),
                }
            )
            gid += 1
    return programs


def prepare_sorted_programs(programs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[int]]:
    programs.sort(key=lambda x: (x["start"], x["end"], x["channel_id"], x["program_id"]))
    for i, p in enumerate(programs):
        p["global_index"] = i
    return programs, [p["start"] for p in programs]


def intervals_overlap(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return a["start"] < b["end"] and b["start"] < a["end"]


def calculate_statistics(neighbors: Sequence[Sequence[int]]) -> Tuple[int, int, float]:
    counts = [len(x) for x in neighbors]
    if not counts:
        return 0, 0, 0.0
    return max(counts), min(counts), sum(counts) / len(counts)


def neighbor_counts(neighbors: Sequence[Sequence[int]]) -> List[int]:
    return [len(x) for x in neighbors]


def compute_basic_neighbors(programs: List[Dict[str, Any]], starts: Sequence[int]) -> List[List[int]]:
    """Basic: B.start >= A.start, strict interval overlap."""
    n = len(programs)
    out: List[List[int]] = [[] for _ in range(n)]
    for i in range(n):
        cur = programs[i]
        lo = bisect_left(starts, cur["start"])
        hi = bisect_left(starts, cur["end"])
        for j in range(lo, hi):
            if j == i:
                continue
            cand = programs[j]
            if cur["start"] < cand["end"] and cand["start"] < cur["end"]:
                out[i].append(cand["global_index"])
    return out


def compute_advanced_delta_neighbors(
    programs: List[Dict[str, Any]],
    starts: Sequence[int],
    delta: int,
) -> List[List[int]]:
    """
    Advanced (original semantics): B.start >= A.start and B.start <= A.end + delta.
    No overlap required. Matches legacy nested-loop behavior.
    """
    n = len(programs)
    out: List[List[int]] = [[] for _ in range(n)]
    for i in range(n):
        cur = programs[i]
        lo = bisect_left(starts, cur["start"])
        hi = bisect_right(starts, cur["end"] + delta)
        for j in range(lo, hi):
            if j == i:
                continue
            cand = programs[j]
            if cand["start"] <= cur["end"] + delta:
                out[i].append(cand["global_index"])
    return out


@dataclass(frozen=True)
class PremierParams:
    """
    Premier / optimized scheduler:
    - Cross-channel: wider lookahead than plain advanced (more swap alternatives).
    - Same-channel: overlap required (stricter than advanced — avoids useless same-channel
      edges that are not simultaneous).
    """

    delta_cross_channel: int = 75
    """Minutes past A.end for which a *different* channel's start still qualifies."""

    delta_advanced: int = 30
    """Horizon used for the 'advanced-style' scan upper bound (>= delta_cross_channel for one pass)."""


def default_premier_params() -> PremierParams:
    return PremierParams()


def compute_premier_neighbors(
    programs: List[Dict[str, Any]],
    starts: Sequence[int],
    params: PremierParams,
) -> List[List[int]]:
    """
    Premier neighbor rule:
    - Let H = max(delta_advanced, delta_cross_channel). Scan starts in [A.start, A.end + H].
    - If candidate.channel == A.channel: keep only if intervals overlap (scheduling conflict).
    - Else: keep if candidate.start <= A.end + delta_cross_channel (extended alt-channel window).

    Effects vs basic: strictly more (adds near-future cross-channel without overlap).
    Effects vs advanced: usually more cross-channel (larger horizon); fewer garbage same-channel
    non-overlap edges (overlap-only on same channel).
    """
    n = len(programs)
    horizon = max(params.delta_advanced, params.delta_cross_channel)
    out: List[List[int]] = [[] for _ in range(n)]

    for i in range(n):
        cur = programs[i]
        lo = bisect_left(starts, cur["start"])
        hi = bisect_right(starts, cur["end"] + horizon)
        lim_cross = cur["end"] + params.delta_cross_channel

        for j in range(lo, hi):
            if j == i:
                continue
            cand = programs[j]
            if cand["channel_id"] == cur["channel_id"]:
                if intervals_overlap(cur, cand):
                    out[i].append(cand["global_index"])
            else:
                if cand["start"] <= lim_cross:
                    out[i].append(cand["global_index"])

    return out


def premier_params_to_dict(p: PremierParams) -> Dict[str, Any]:
    return {
        "delta_cross_channel": p.delta_cross_channel,
        "delta_advanced": p.delta_advanced,
    }


def validate_basic_edge(programs: List[Dict[str, Any]], i: int, j: int) -> bool:
    if j == i or not (0 <= j < len(programs)):
        return False
    a, b = programs[i], programs[j]
    if b["start"] < a["start"]:
        return False
    return bool(a["start"] < b["end"] and b["start"] < a["end"])


def validate_advanced_delta_edge(programs: List[Dict[str, Any]], i: int, j: int, delta: int) -> bool:
    if j == i or not (0 <= j < len(programs)):
        return False
    a, b = programs[i], programs[j]
    if b["start"] < a["start"]:
        return False
    return bool(b["start"] <= a["end"] + delta)


def validate_premier_edge(programs: List[Dict[str, Any]], i: int, j: int, params: PremierParams) -> bool:
    if j == i or not (0 <= j < len(programs)):
        return False
    a, b = programs[i], programs[j]
    if b["start"] < a["start"]:
        return False
    if b["channel_id"] == a["channel_id"]:
        return intervals_overlap(a, b)
    return bool(b["start"] <= a["end"] + params.delta_cross_channel)
