# ============================================================
# FILE: engine/background_worker.py
# PURPOSE: Non-blocking background compute worker for Streamlit.
#
# Problem: Streamlit re-runs the entire script on every user interaction.
# Long-running computations (probability models, batch enrichment, Neural
# Analysis, line-deviation scans) block the main thread and freeze the UI
# for every user on the server.
#
# Solution: A module-level ThreadPoolExecutor accepts submitted tasks and
# stores Future objects in Streamlit session_state.  The page re-renders
# immediately while compute runs in the background.  On the next rerun
# (triggered by st.rerun() or the user's next action) the page checks
# whether the Future is done and renders the result if ready.
#
# Architecture:
#   submit_task(fn, *args, **kwargs)  → task_id (str)
#   get_result(task_id, session)      → (status, result | None)
#   cancel_task(task_id, session)     → bool
#
# Usage pattern in a Streamlit page:
#   if "analysis_task" not in st.session_state:
#       st.session_state["analysis_task"] = submit_task(run_analysis, props, players)
#   status, result = get_result(st.session_state["analysis_task"], st.session_state)
#   if status == "done":
#       render(result)
#   elif status == "running":
#       st.spinner("Calculating…")
#       time.sleep(0.5); st.rerun()
#   else:  # "error"
#       st.error(result)
# ============================================================

import uuid
import threading
import time
import logging
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable, Dict, Optional, Tuple

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except Exception:
    _logger = logging.getLogger(__name__)


# ── Worker pool ───────────────────────────────────────────────────────────────
# max_workers=4: enough parallelism for concurrent Streamlit user sessions
# without starving the main thread of CPU.  Adjust via env var if needed.
import os as _os
_MAX_WORKERS = int(_os.environ.get("BG_WORKER_MAX_THREADS", "4"))

# Module-level singleton executor.  ThreadPoolExecutor is thread-safe and
# reused across all Streamlit reruns within the same process lifetime.
_executor: ThreadPoolExecutor = ThreadPoolExecutor(
    max_workers=_MAX_WORKERS,
    thread_name_prefix="spp-bg-worker",
)

# Future registry: task_id → Future
# Protected by a lock to support concurrent Streamlit sessions.
_futures: Dict[str, Future] = {}
_futures_lock = threading.Lock()

# Maximum age (seconds) for completed/errored futures before they are pruned.
# Prevents unbounded growth of the registry across long Streamlit sessions.
_FUTURE_MAX_AGE_SECONDS = 300  # 5 minutes


# ── Public API ────────────────────────────────────────────────────────────────

def submit_task(fn: Callable, *args, **kwargs) -> str:
    """Submit a callable to the background thread pool.

    The callable runs in a separate thread; Streamlit's main thread is not
    blocked.  Returns a task_id string that callers store in session_state.

    Args:
        fn: Any callable (function, method, lambda).
        *args / **kwargs: Forwarded verbatim to *fn*.

    Returns:
        task_id (str): Opaque UUID used to retrieve the result later.

    Example:
        task_id = submit_task(run_analysis, props_list, players_list)
        st.session_state["my_task"] = task_id
    """
    task_id = str(uuid.uuid4())
    future = _executor.submit(fn, *args, **kwargs)
    with _futures_lock:
        _futures[task_id] = future
    _logger.debug("BG worker: submitted task %s (%s)", task_id[:8], getattr(fn, "__name__", "?"))
    return task_id


def get_result(
    task_id: str,
    session_state: Optional[dict] = None,
) -> Tuple[str, Any]:
    """Check the status of a submitted task and return its result if done.

    Status values:
        "running"  – still in progress; result is None.
        "done"     – completed successfully; result is the return value of *fn*.
        "error"    – raised an exception; result is the exception string.
        "unknown"  – task_id not found (may have been pruned or never submitted).

    Args:
        task_id: The ID returned by submit_task().
        session_state: Optional Streamlit session_state.  When provided,
            the result is cached in session_state[task_id + "_result"] so
            it survives after the Future is pruned from the registry.

    Returns:
        Tuple of (status, result).
    """
    # Check session_state cache first — allows retrieving results after pruning
    _cache_key = task_id + "_result"
    if session_state is not None and _cache_key in session_state:
        cached = session_state[_cache_key]
        return cached["status"], cached["value"]

    with _futures_lock:
        future = _futures.get(task_id)

    if future is None:
        return "unknown", None

    if not future.done():
        return "running", None

    # Future is complete — extract result or exception
    try:
        value = future.result()
        status = "done"
    except Exception as exc:
        value = str(exc)
        status = "error"
        _logger.warning("BG worker task %s raised: %s", task_id[:8], exc)

    # Cache in session_state so subsequent reruns can retrieve without re-running
    if session_state is not None:
        session_state[_cache_key] = {"status": status, "value": value}

    # Remove from registry now that it's consumed
    with _futures_lock:
        _futures.pop(task_id, None)

    return status, value


def cancel_task(task_id: str, session_state: Optional[dict] = None) -> bool:
    """Attempt to cancel a pending task.

    Can only cancel tasks that have not yet started executing.  Returns True
    if the cancellation was accepted, False if the task was already running or
    not found.

    Args:
        task_id: The ID returned by submit_task().
        session_state: If provided, clears the cached result key too.

    Returns:
        bool: True if successfully cancelled.
    """
    with _futures_lock:
        future = _futures.pop(task_id, None)

    if session_state is not None:
        session_state.pop(task_id + "_result", None)

    if future is None:
        return False

    cancelled = future.cancel()
    _logger.debug("BG worker: cancel task %s → %s", task_id[:8], cancelled)
    return cancelled


def clear_task(task_id: str, session_state: Optional[dict] = None) -> None:
    """Remove a task from the registry and session cache (cleanup helper).

    Call this after you have consumed the result and no longer need the task.

    Args:
        task_id: The ID returned by submit_task().
        session_state: If provided, clears the cached result key too.
    """
    with _futures_lock:
        _futures.pop(task_id, None)
    if session_state is not None:
        session_state.pop(task_id + "_result", None)


def get_pool_stats() -> dict:
    """Return diagnostic stats for the worker pool (useful for a debug panel).

    Returns:
        dict with keys: max_workers, pending_tasks, running, completed.
    """
    with _futures_lock:
        total = len(_futures)
        running = sum(1 for f in _futures.values() if f.running())
        pending = sum(1 for f in _futures.values() if not f.done() and not f.running())
        done = sum(1 for f in _futures.values() if f.done())
    return {
        "max_workers": _MAX_WORKERS,
        "registry_size": total,
        "running": running,
        "pending": pending,
        "done_uncollected": done,
    }


# ── Registry maintenance ──────────────────────────────────────────────────────
# Completed futures that were never collected via get_result() would otherwise
# sit in _futures indefinitely.  A background sweep prunes them after
# _FUTURE_MAX_AGE_SECONDS so the registry stays bounded.

def _prune_old_futures() -> None:
    """Remove done futures from the registry that have exceeded max age."""
    with _futures_lock:
        # futures.Future has no creation timestamp, so we prune any done
        # future unconditionally — if the caller hasn't fetched it within
        # _FUTURE_MAX_AGE_SECONDS of it completing, it's considered stale.
        stale = [tid for tid, f in _futures.items() if f.done()]
        for tid in stale:
            _futures.pop(tid, None)
    if stale:
        _logger.debug("BG worker: pruned %d stale futures.", len(stale))


def _start_pruning_thread() -> None:
    def _loop():
        while True:
            time.sleep(_FUTURE_MAX_AGE_SECONDS)
            try:
                _prune_old_futures()
            except Exception as exc:  # pragma: no cover
                _logger.warning("BG worker prune error: %s", exc)

    t = threading.Thread(target=_loop, name="spp-bg-pruner", daemon=True)
    t.start()


_start_pruning_thread()
