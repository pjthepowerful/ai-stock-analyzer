"""
Keeps scan pre-screen data warm while people are scanning.

Yahoo throttles bulk downloads, and a big scan used to make the user wait on
that (one took 6 minutes). trading.warm_scan_cache refreshes only the tickers
users scanned in the last two hours, only during market hours, so the next
scan reads warm data and spends its time on scoring and the live re-check of
the picks it shows.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor

from ..bridge import engine  # noqa: F401  loads trading.py with its shims

INTERVAL_S = 4 * 60

# One worker: a refresh must never overlap the next one or crowd out the
# request thread pool.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scan-warm")


async def keep_warm():
    import trading

    loop = asyncio.get_running_loop()
    while True:
        await asyncio.sleep(INTERVAL_S)
        try:
            n = await loop.run_in_executor(_executor, trading.warm_scan_cache)
            if n:
                print(f"[scan-warm] refreshed {n} tickers", flush=True)
        except Exception as e:
            print(f"[scan-warm] refresh failed: {e!r}", flush=True)
