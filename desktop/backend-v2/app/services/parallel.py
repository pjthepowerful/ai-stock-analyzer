"""
Run a per-ticker function across many tickers concurrently.

The repo-root rank()/verdict loops call one ticker at a time, and every call
is several network round trips (Yahoo, EDGAR, news) — so a 40-name ranking
spent almost all of its ~60s waiting. The work is I/O-bound, so a small
thread pool gives a near-linear speedup without touching the tuned modules.

Worker count is deliberately modest: SEC EDGAR's fair-use limit is 10
requests/second and each research row can make a couple of EDGAR calls.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, Optional, TypeVar

T = TypeVar("T")
R = TypeVar("R")

DEFAULT_WORKERS = 6


def pmap(
    fn: Callable[[T], R],
    items: Iterable[T],
    workers: int = DEFAULT_WORKERS,
    progress: Optional[Callable[[int, int, str], None]] = None,
) -> list[R]:
    """fn over items concurrently. Items whose call raises are dropped (same
    contract as the sequential rank() loops). Results come back in input
    order; progress(done, total, label) fires as each one finishes."""
    items = list(items)
    total = len(items)
    results: dict[int, R] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, min(workers, total or 1))) as pool:
        futures = {pool.submit(fn, item): i for i, item in enumerate(items)}
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                results[i] = fut.result()
            except Exception:
                pass
            done += 1
            if progress:
                try:
                    progress(done, total, str(items[i]).upper())
                except Exception:
                    pass
    return [results[i] for i in sorted(results)]
