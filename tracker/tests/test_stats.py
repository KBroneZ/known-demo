import math

import pytest

from vistrack.stats import cluster_bootstrap, jaccard, mean_pairwise_jaccard, newcombe_diff, wilson


@pytest.mark.parametrize(
    "k,n,lo,hi",
    [
        (0, 10, 0.0, 0.2775),
        (3, 10, 0.1078, 0.6032),
        (5, 10, 0.2366, 0.7634),
        (7, 10, 0.3968, 0.8922),
        (10, 10, 0.7225, 1.0),
        (0, 5, 0.0, 0.4345),
        (5, 5, 0.5655, 1.0),
        (50, 100, 0.4038, 0.5962),
    ],
)
def test_wilson_matches_reference_values(k, n, lo, hi):
    got_lo, got_hi = wilson(k, n)
    assert got_lo == pytest.approx(lo, abs=5e-4)
    assert got_hi == pytest.approx(hi, abs=5e-4)


def test_wilson_never_degenerate_at_extremes():
    _lo0, hi0 = wilson(0, 10)
    lo1, _hi1 = wilson(10, 10)
    assert hi0 > 0.2 and lo1 < 0.8  # Wald would give [0,0] and [1,1]


def test_wilson_bounds_and_symmetry():
    for n in (1, 5, 20, 100):
        for k in range(n + 1):
            lo, hi = wilson(k, n)
            assert 0 <= lo <= k / n <= hi <= 1
            lo2, hi2 = wilson(n - k, n)
            assert lo == pytest.approx(1 - hi2) and hi == pytest.approx(1 - lo2)


def test_wilson_narrows_with_n():
    w10 = wilson(5, 10)
    w100 = wilson(50, 100)
    assert (w100[1] - w100[0]) < (w10[1] - w10[0])


def test_wilson_rejects_bad_input_and_handles_empty():
    with pytest.raises(ValueError):
        wilson(11, 10)
    assert all(math.isnan(x) for x in wilson(0, 0))


def test_newcombe_matches_research_examples():
    # research/04 section 3.4: 3/10 -> 7/10 is +40pp, interval about [-3, +67]: inconclusive
    d, lo, hi = newcombe_diff(7, 10, 3, 10)
    assert d == pytest.approx(0.40)
    assert lo == pytest.approx(-0.029, abs=0.005) and hi == pytest.approx(0.672, abs=0.005)
    # 2/10 -> 8/10 is +60pp, interval about [+16, +80]: conclusive
    d, lo, hi = newcombe_diff(8, 10, 2, 10)
    assert lo > 0.15 and hi == pytest.approx(0.80, abs=0.01)


def test_cluster_bootstrap_basic():
    mean, lo, hi = cluster_bootstrap([(5, 5), (0, 5), (3, 5), (2, 5)], iters=500, seed=1)
    assert mean == pytest.approx(0.5)
    assert 0 <= lo < mean < hi <= 1


def test_cluster_bootstrap_is_wider_than_naive_when_prompts_differ():
    cells = [(5, 5)] * 5 + [(0, 5)] * 5  # each prompt always or never: runs are fully correlated
    _, lo, hi = cluster_bootstrap(cells, iters=1000, seed=2)
    naive_lo, naive_hi = wilson(25, 50)
    assert (hi - lo) > (naive_hi - naive_lo)


def test_cluster_bootstrap_empty_and_deterministic():
    assert all(math.isnan(x) for x in cluster_bootstrap([]))
    assert all(math.isnan(x) for x in cluster_bootstrap([(0, 0)]))
    a = cluster_bootstrap([(1, 5), (4, 5), (2, 5)], iters=300, seed=7)
    assert a == cluster_bootstrap([(1, 5), (4, 5), (2, 5)], iters=300, seed=7)


def test_jaccard():
    assert jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)
    assert jaccard(set(), set()) == 1.0
    assert jaccard({"a"}, set()) == 0.0
    assert mean_pairwise_jaccard([{"a"}, {"a"}, {"b"}]) == pytest.approx(1 / 3)
    assert math.isnan(mean_pairwise_jaccard([{"a"}]))
