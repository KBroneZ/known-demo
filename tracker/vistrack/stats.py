"""Small-sample statistics for repeat-run visibility rates. Stdlib only."""

from __future__ import annotations

import math
import random
from collections.abc import Iterable, Sequence
from itertools import combinations

Z95 = 1.959963984540054
_EPS = 1e-12


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion k/n.

    Well behaved at k=0 and k=n (unlike Wald). Returns (nan, nan) if n == 0.
    """
    if n <= 0:
        return (math.nan, math.nan)
    if not 0 <= k <= n:
        raise ValueError(f"need 0 <= k <= n, got k={k}, n={n}")
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    lo, hi = centre - half, centre + half
    if lo < _EPS:
        lo = 0.0
    if hi > 1 - _EPS:
        hi = 1.0
    return lo, hi


def newcombe_diff(k1: int, n1: int, k2: int, n2: int, z: float = Z95) -> tuple[float, float, float]:
    """Newcombe (method 10) interval for p1 - p2. Returns (diff, lo, hi)."""
    if n1 <= 0 or n2 <= 0:
        return (math.nan, math.nan, math.nan)
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1, z)
    l2, u2 = wilson(k2, n2, z)
    d = p1 - p2
    lo = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return d, max(-1.0, lo), min(1.0, hi)


def cluster_bootstrap(
    cells: Sequence[tuple[int, int]],
    iters: int = 2000,
    seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Mean of per-prompt rates with a prompt-level (cluster) bootstrap CI.

    cells: one (k, n) per prompt. Runs of the same prompt are correlated, so
    we resample prompts, not runs. Returns (mean, lo, hi); nan if no usable cell,
    and nan bounds when every prompt has the same rate (no variation to resample).
    """
    rates = [k / n for k, n in cells if n > 0]
    if not rates:
        return (math.nan, math.nan, math.nan)
    mean = sum(rates) / len(rates)
    if max(rates) == min(rates):  # no variation between prompts: a bootstrap would print a zero-width "interval"
        return (mean, math.nan, math.nan)
    rng = random.Random(seed)
    m = len(rates)
    means = sorted(sum(rates[rng.randrange(m)] for _ in range(m)) / m for _ in range(iters))
    lo = means[int((alpha / 2) * iters)]
    hi = means[min(iters - 1, int((1 - alpha / 2) * iters))]
    return mean, lo, hi


def jaccard(a: Iterable, b: Iterable) -> float:
    """Jaccard similarity; two empty sets count as identical (1.0)."""
    a, b = set(a), set(b)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def pair_jaccards(sets: Sequence[Iterable], skip_empty_pairs: bool = True) -> list[float]:
    """Jaccard for every pair of repetitions.

    With skip_empty_pairs, pairs where BOTH repetitions are empty are left out: "nothing named" twice
    is not agreement about anything and would otherwise count as a perfect 1.0.
    """
    out = []
    for a, b in combinations([set(s) for s in sets], 2):
        if skip_empty_pairs and not a and not b:
            continue
        out.append(jaccard(a, b))
    return out


def mean_pairwise_jaccard(sets: Sequence[Iterable], skip_empty_pairs: bool = True) -> float:
    """Mean Jaccard over pairs of repetitions. nan if there is no usable pair."""
    pairs = pair_jaccards(sets, skip_empty_pairs)
    return sum(pairs) / len(pairs) if pairs else math.nan


def fmt_pct(x: float, digits: int = 0) -> str:
    return "n/a" if x is None or math.isnan(x) else f"{x * 100:.{digits}f}%"
