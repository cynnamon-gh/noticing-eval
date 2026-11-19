"""Cluster bootstrap (SPEC FR-20; used by BUILD_PLAN M6.1 and M6.4).

Answers to the same core prompt are not independent: its voice versions and repeats tend to score
alike. So a confidence interval resamples whole core prompts (clusters), with replacement, and
keeps every answer of each drawn prompt. Resampling single answers would treat 3 versions x 2
repeats of one prompt as 6 independent data points and give intervals that are too narrow.

The interval is the 2.5th and 97.5th percentile of the statistic over the resamples (95%).
A statistic may return None when it is undefined for a resample (for example kappa when every
rating is the same); those resamples are dropped and counted.
"""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Callable, Sequence


def _percentile(sorted_vals: list[float], q: float) -> float:
    """Linear interpolation between closest ranks (the numpy default)."""
    pos = (len(sorted_vals) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def cluster_bootstrap(rows: Sequence[dict], cluster_key: str, stat: Callable[[list], float | None],
                      n: int = 10_000, seed: int = 20261119, return_draws: bool = False,
                      return_dropped: bool = False):
    """Return (low, high) of the 95% interval for stat(rows), resampling clusters.

    With return_draws / return_dropped, also return the list of statistic values and the number
    of resamples dropped because the statistic was undefined.
    """
    clusters: dict = defaultdict(list)
    for r in rows:
        clusters[r[cluster_key]].append(r)
    keys = sorted(clusters)
    rng = random.Random(seed)
    draws, dropped = [], 0
    for _ in range(n):
        sample = [r for k in rng.choices(keys, k=len(keys)) for r in clusters[k]]
        v = stat(sample)
        if v is None:
            dropped += 1
        else:
            draws.append(v)
    if not draws:
        raise ValueError("the statistic was undefined in every resample")
    s = sorted(draws)
    out = (_percentile(s, 0.025), _percentile(s, 0.975))
    if return_draws:
        out = (*out, draws)
    if return_dropped:
        out = (*out, dropped)
    return out
