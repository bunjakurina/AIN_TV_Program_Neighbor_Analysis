"""Advanced delta-window neighbors — fast bisect (same semantics as legacy O(n²) loop)."""

from neighbor_engine import calculate_statistics, compute_advanced_delta_neighbors


def generate_advanced_neighbors(programs, starts, delta):
    return compute_advanced_delta_neighbors(programs, starts, delta)
