"""Basic overlap neighbors — fast bisect implementation."""

from neighbor_engine import calculate_statistics, compute_basic_neighbors


def generate_basic_neighbors(programs, starts):
    """programs sorted by time; starts parallel array."""
    return compute_basic_neighbors(programs, starts)
