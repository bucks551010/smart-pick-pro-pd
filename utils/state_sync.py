"""utils/state_sync.py — Zero-Data-Loss helpers for Smart Pick Pro.

Three independent utilities that together provide "desktop-app" UX:

┌──────────────────────────────────────────────────────────────────────────────┐
│  1. URL State Sync   sync_to_url / hydrate_from_url                          │
│     Writes filter/view state into the URL so F5 returns the exact view.     │
│                                                                              │
│  2. Local-First Auto-Save  inject_page_persistence                           │
│     Saves URL params to localStorage with a 2-s debounce.  On return,       │
│     silently restores the saved state without any login prompt.              │
│     Attaches a beforeunload guard to prevent accidental tab closures.        │
│                                                                              │
│  3. JWT Fetch Interceptor  inject_fetch_interceptor                          │
│     Patches window.fetch on the parent page to add Authorization headers     │
│     automatically.  Handles 401 → silent JWT refresh → retry transparently. │
└──────────────────────────────────────────────────────────────────────────────┘

Typical page usage
------------------
    import utils.state_sync as state_sync

    # ① Restore state from URL / localStorage on every load
    view = state_sync.hydrate_from_url({
        "sport": "NBA", "date": "", "sort": "safe_desc", "tier": "all"
    })

    # ... page logic using st.session_state ...

    # ② Sync back to URL (call ONCE at the end of page logic)
    state_sync.sync_to_url(["sport", "date", "sort", "tier"])

    # ③ Auto-save + nav guard (call ONCE near the top)
    state_sync.inject_page_persistence("qam_dashboard")

    # ④ JWT interceptor — only on authenticated pages
    state_sync.inject_fetch_interceptor()
"""

from __future__ import annotations

import streamlit as st
from utils.logger import get_logger

_logger = get_logger(__name__)
_DRAFT_PREFIX = "spp_draft_"


# ══════════════════════════════════════════════════════════════════════════════
# 1. URL State Sync
# ══════════════════════════════════════════════════════════════════════════════

def sync_to_url(keys: list[str]) -> None:
    """Write selected ``st.session_state`` keys to ``st.query_params``.

    Only JSON-safe scalar values (str, int, float, bool) are written.
    ``None`` values remove the corresponding param from the URL.

    Call at the END of page logic, after all state mutations, so the URL
    always reflects the current view.

    Example::

        state_sync.sync_to_url(["sport", "date", "tier", "sort_by"])
    """
    try:
        qp = st.query_params
        for key in keys:
            val = st.session_state.get(key)
            if val is None:
                qp.pop(key, None)
            else:
                qp[key] = str(val)
    except Exception as exc:
        _logger.debug("sync_to_url failed: %s", exc)


def hydrate_from_url(defaults: dict) -> dict:
    """Read ``st.query_params`` into ``st.session_state`` on page init.

    Only keys present in ``defaults`` are processed.  Each raw string value
    is coerced to the same type as the corresponding default:

    - ``bool``  → ``"true"``/``"1"``/``"yes"`` → True, else False
    - ``int``   → ``int(raw)``
    - ``float`` → ``float(raw)``
    - ``str``   → raw string

    Keys absent from the URL keep their current ``session_state`` value
    (or the provided default if they are also absent from session_state).

    Returns a dict of the resolved values (URL param or default).

    Example::

        filters = state_sync.hydrate_from_url({
            "sport": "NBA",
            "page":  1,
            "show_premium": False,
        })
    """
    result: dict = {}
    try:
        qp = st.query_params
        for key, default in defaults.items():
            if key in qp:
                raw = qp[key]
                try:
                    if isinstance(default, bool):
                        val: object = raw.lower() in ("true", "1", "yes")
                    elif isinstance(default, int):
                        val = int(raw)
                    elif isinstance(default, float):
                        val = float(raw)
                    else:
                        val = raw
                    st.session_state[key] = val
                    result[key] = val
                except (ValueError, TypeError):
                    result[key] = st.session_state.get(key, default)
            else:
                result[key] = st.session_state.get(key, default)
    except Exception as exc:
        _logger.debug("hydrate_from_url failed: %s", exc)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 2. Local-First Auto-Save + Navigation Guard
# ══════════════════════════════════════════════════════════════════════════════

def inject_page_persistence(
    page_key: str,
    debounce_ms: int = 2000,
    *,
    nav_guard: bool = True,
) -> None:
    """Inject localStorage auto-save, draft hydration, and navigation guard.

    Auto-save
    ~~~~~~~~~
    A ``setInterval`` on the parent page polls for URL changes every 500 ms.
    When a change is detected, it schedules a ``localStorage.setItem`` after
    ``debounce_ms`` ms.  This means filter changes are durably saved within
    ~2.5 seconds without blocking the UI.

    Draft hydration
    ~~~~~~~~~~~~~~~
    On load, if the current URL has no page-specific query params but
    ``localStorage`` contains a saved draft, the script replays the saved
    search string into the URL and triggers a page reload so Streamlit sees
    the restored params via ``st.query_params``.

    Navigation guard
    ~~~~~~~~~~~~~~~~
    If ``nav_guard=True``, a ``beforeunload`` listener warns the user when
    they attempt to close the tab while unsaved state exists.  The flag
    ``window.parent._sppHasDraft`` controls whether the warning fires.

    Parameters
    ----------
    page_key:
        Unique slug for this page (e.g. ``"qam_dashboard"``).  Used as the
        ``localStorage`` key: ``spp_draft_<page_key>``.
    debounce_ms:
        Milliseconds to wait after the last URL change before writing to
        ``localStorage``.  Default 2000 ms.
    nav_guard:
        Attach the ``beforeunload`` warning.  Default ``True``.
    """
    import streamlit.components.v1 as _components

    draft_key = f"{_DRAFT_PREFIX}{page_key}"
    guard_js = (
        """
  if (!win._sppNavGuardAttached) {
    win._sppNavGuardAttached = true;
    win.addEventListener('beforeunload', function(e) {
      if (win._sppHasDraft) {
        e.preventDefault();
        e.returnValue = 'You have unsaved changes. Leave anyway?';
        return e.returnValue;
      }
    });
  }
"""
        if nav_guard
        else ""
    )

    _components.html(
        f"""
<script>
(function(win) {{
  var DRAFT_KEY   = "{draft_key}";
  var DEBOUNCE_MS = {debounce_ms};
  var _timer      = null;

  // ── Navigation guard ──────────────────────────────────────────────────
  {guard_js}

  // ── Auto-save: debounce on URL change ─────────────────────────────────
  function _save() {{
    try {{
      var qs = win.location.search;
      // Only save meaningful state — skip pure auth/session params.
      var meaningful = qs && qs.length > 1 &&
                       !qs.match(/^\\?(_st=|auth=)/);
      if (meaningful) {{
        win.localStorage.setItem(DRAFT_KEY, qs);
        win._sppHasDraft = true;
      }}
    }} catch(e) {{}}
  }}

  if (!win._sppUrlWatcher) {{
    var _last = win.location.href;
    win._sppUrlWatcher = setInterval(function() {{
      var now = win.location.href;
      if (now !== _last) {{
        _last = now;
        clearTimeout(_timer);
        _timer = setTimeout(_save, DEBOUNCE_MS);
      }}
    }}, 500);
  }}

  // ── Draft hydration: restore saved state on clean load ────────────────
  (function() {{
    try {{
      var qs = win.location.search;
      // Treat the page as "clean" if there are no recognisable state params.
      var hasState = qs && qs.match(/sport=|date=|page=|sort=|tier=|view=|filter=/);
      var isAuth   = qs && qs.match(/_st=|auth=/);
      if (!hasState && !isAuth) {{
        var saved = "";
        try {{ saved = win.localStorage.getItem(DRAFT_KEY) || ""; }} catch(e) {{}}
        if (saved && saved.length > 1) {{
          var restored = win.location.origin + win.location.pathname + saved;
          win.history.replaceState(null, "", restored);
          win.location.reload();
        }}
      }}
    }} catch(e) {{}}
  }})();
}})(window.parent);
</script>
""",
        height=0,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 3. JWT Fetch Interceptor
# ══════════════════════════════════════════════════════════════════════════════

def inject_fetch_interceptor() -> None:
    """Inject the JWT fetch interceptor into the parent page (once per tab).

    How it works
    ~~~~~~~~~~~~
    1. **Acquire** — On load, calls ``POST /api/auth/token`` (which reads the
       HttpOnly ``spp_session_hi`` cookie automatically).  The server
       validates the long-lived refresh token and returns a 60-minute JWT.

    2. **Intercept** — Monkey-patches ``window.parent.fetch`` to:
       - Add ``Authorization: Bearer <jwt>`` to every ``/api/*`` request
         (excluding ``/api/auth/*`` and ``/api/session/*`` which manage
         tokens themselves).
       - On a **401** response: discard the cached JWT, silently re-acquire,
         and retry the original request once.

    3. **Proactive refresh** — A ``setInterval`` fires every 55 minutes
       (5 min before the 60-min JWT expiry) to pre-acquire a fresh token,
       ensuring in-flight requests never race against expiry.

    Security properties
    ~~~~~~~~~~~~~~~~~~~
    - The JWT lives exclusively in a **JS closure** (memory variable).  It is
      never written to ``localStorage``, ``sessionStorage``, or a cookie.
    - An XSS attacker who can execute arbitrary JS can read the in-memory token
      (this is unavoidable for any memory-resident credential), but it expires
      within 60 minutes and cannot be refreshed without the HttpOnly cookie.
    - The refresh token itself (``spp_session_hi``) is ``HttpOnly`` and is
      never readable by JS at all.

    Idempotency
    ~~~~~~~~~~~
    The injection is no-oped on subsequent calls within the same tab via the
    ``window.parent._sppInterceptorInstalled`` guard.  Safe to call on every
    Streamlit page load.
    """
    import streamlit.components.v1 as _components

    _components.html(
        """
<script>
(function(win) {
  if (win._sppInterceptorInstalled) return;
  win._sppInterceptorInstalled = true;

  // ── In-memory token store — NEVER persisted to any storage ────────────
  var _jwt          = null;   // Current access token string
  var _jwtExpiry    = 0;      // Epoch-ms expiry (30 s before actual exp)
  var _inflight     = null;   // Pending acquisition Promise

  // ── Acquire a fresh JWT from the server ───────────────────────────────
  function _acquire() {
    if (_inflight) return _inflight;
    _inflight = win.fetch('/api/auth/token', {
      method:      'POST',
      credentials: 'include',    // Sends HttpOnly spp_session_hi cookie
      headers:     { 'Content-Type': 'application/json' }
    })
    .then(function(r) { return r.ok ? r.json() : { ok: false }; })
    .then(function(data) {
      _inflight = null;
      if (data && data.ok && data.access_token) {
        _jwt       = data.access_token;
        // Expire 30 s early to avoid race conditions on in-flight requests
        _jwtExpiry = Date.now() + ((data.expires_in || 3600) - 30) * 1000;
      } else {
        // Refresh token expired or absent — clear stale state
        _jwt = null; _jwtExpiry = 0;
      }
      return _jwt;
    })
    .catch(function() { _inflight = null; return null; });
    return _inflight;
  }

  // ── Get token (cached or fresh) ───────────────────────────────────────
  function _getJWT() {
    return (_jwt && Date.now() < _jwtExpiry)
      ? Promise.resolve(_jwt)
      : _acquire();
  }

  // ── Decide whether a URL needs auth headers ───────────────────────────
  function _needsAuth(url) {
    if (typeof url !== 'string') return false;
    return url.startsWith('/api/')
      && !url.startsWith('/api/auth/')
      && !url.startsWith('/api/session/');
  }

  // ── Patch fetch ───────────────────────────────────────────────────────
  var _orig = win.fetch;
  win.fetch = function(url, opts) {
    opts = Object.assign({}, opts || {});
    if (!_needsAuth(url)) return _orig.call(win, url, opts);

    return _getJWT().then(function(tok) {
      if (tok) {
        opts.headers = Object.assign({}, opts.headers || {},
                                     { 'Authorization': 'Bearer ' + tok });
      }
      return _orig.call(win, url, opts).then(function(resp) {
        if (resp.status !== 401) return resp;

        // 401 → silent refresh + single retry
        _jwt = null; _jwtExpiry = 0;
        return _acquire().then(function(newTok) {
          if (!newTok) return resp;   // Surface 401 to caller — user must re-login
          var retryOpts = Object.assign({}, opts, {
            headers: Object.assign({}, opts.headers || {},
                                   { 'Authorization': 'Bearer ' + newTok })
          });
          return _orig.call(win, url, retryOpts);
        });
      });
    });
  };

  // ── Proactive refresh every 55 min (5 min before 60-min JWT expiry) ───
  setInterval(_acquire, 55 * 60 * 1000);

  // ── Kick off initial acquisition immediately ──────────────────────────
  _acquire();

})(window.parent);
</script>
""",
        height=0,
    )
