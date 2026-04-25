"""Replace JS-bridge localStorage session with HTTP cookie approach.

Cookie is set via JS on login, read by Python from st.context.headers on every
page load (including F5). No timing race conditions, no bridge reloads.
"""
import ast

path = "utils/auth_gate.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

# ── 1. Replace _write_session_to_storage ────────────────────────────────────
_old_write = (
    "def _write_session_to_storage(token: str) -> None:\n"
    '    """Write the session token into the browser\'s localStorage."""\n'
    "    import streamlit.components.v1 as _components\n"
    '    _components.html(f"""\n'
    "<script>\n"
    "(function() {{\n"
    '  localStorage.setItem("{_LS_KEY}", "{token}");\n'
    "  // Navigate to a clean home URL with just the session token,\n"
    "  // removing ?auth=login and any other stale params from the address bar.\n"
    '  window.parent.location.href = "/?_st={token}";\n'
    "}})();\n"
    "</script>\n"
    '""", height=0)'
)

_new_write = (
    "def _write_session_to_storage(token: str) -> None:\n"
    '    """Write the session token as an HTTP cookie (read by Python on every load)."""\n'
    "    import streamlit.components.v1 as _components\n"
    '    _components.html(f"""\n'
    "<script>\n"
    "(function() {{\n"
    "  // Set a 7-day persistent session cookie.\n"
    "  // Python reads this from st.context.headers on every page load (incl. F5).\n"
    '  document.cookie = "spp_session={token}; path=/; max-age=604800; SameSite=Lax";\n'
    "  // Also keep localStorage as a fallback for environments that block cookies.\n"
    '  try {{ localStorage.setItem("{_LS_KEY}", "{token}"); }} catch(e) {{}}\n'
    "  // Clean the URL — remove ?auth=login and any other stale params.\n"
    "  var cleanUrl = window.parent.location.origin + window.parent.location.pathname;\n"
    '  window.parent.history.replaceState(null, "", cleanUrl);\n'
    "}})();\n"
    "</script>\n"
    '""", height=0)'
)

print("write old found:", _old_write in content)
content = content.replace(_old_write, _new_write, 1)

# ── 2. Replace _clear_session_from_storage ──────────────────────────────────
_old_clear = (
    "def _clear_session_from_storage() -> None:\n"
    '    """Remove the session token from the browser\'s localStorage."""\n'
    "    import streamlit.components.v1 as _components\n"
    '    _components.html(f"""\n'
    "<script>\n"
    "(function() {{\n"
    '  localStorage.removeItem("{_LS_KEY}");\n'
    '  var url = new URL(window.parent.location.href);\n'
    '  url.searchParams.delete("_st");\n'
    '  window.parent.history.replaceState(null, "", url.toString());\n'
    "}})();\n"
    "</script>\n"
    '""", height=0)'
)

_new_clear = (
    "def _clear_session_from_storage() -> None:\n"
    '    """Expire the session cookie and clear localStorage."""\n'
    "    import streamlit.components.v1 as _components\n"
    '    _components.html(f"""\n'
    "<script>\n"
    "(function() {{\n"
    '  document.cookie = "spp_session=; path=/; max-age=0; SameSite=Lax";\n'
    '  try {{ localStorage.removeItem("{_LS_KEY}"); }} catch(e) {{}}\n'
    "  var cleanUrl = window.parent.location.origin + window.parent.location.pathname;\n"
    '  window.parent.history.replaceState(null, "", cleanUrl);\n'
    "}})();\n"
    "</script>\n"
    '""", height=0)'
)

print("clear old found:", _old_clear in content)
content = content.replace(_old_clear, _new_clear, 1)

# ── 3. Add _get_session_cookie helper after _clear_session_from_storage ──────
_after_clear_marker = "\n\n# \u2500\u2500 Password hashing helpers \u2500\u2500"
_cookie_helper = (
    "\n\n"
    "def _get_session_cookie() -> str:\n"
    '    """Read the spp_session cookie from request headers (works on every F5)."""\n'
    "    try:\n"
    '        cookie_header = st.context.headers.get("Cookie", "")\n'
    "        for _part in cookie_header.split(\";\"):\n"
    "            _part = _part.strip()\n"
    '            if _part.startswith("spp_session="):\n'
    '                return _part[len("spp_session="):]\n'
    "    except Exception:\n"
    "        pass\n"
    '    return ""\n'
)

print("marker found:", _after_clear_marker in content)
content = content.replace(_after_clear_marker, _cookie_helper + _after_clear_marker, 1)

# ── 4. Replace require_login's bridge+_st block with cookie check ─────────────
_start = content.find(
    "    if is_logged_in():\n"
    "        # Clean up any stale auth/token params left in the URL after login."
)
_end = content.find(
    "\n    # \u2500\u2500 Portal routing: dedicated sign-in / sign-up view", _start
)
print("require_login block start:", _start, "end:", _end)

_new_block = (
    "    if is_logged_in():\n"
    "        # Clean any stale auth/token params from the URL after login.\n"
    "        try:\n"
    "            _qp = st.query_params\n"
    '            if _qp.get("auth") or _qp.get("_st"):\n'
    '                _qp.pop("auth", None)\n'
    '                _qp.pop("_st", None)\n'
    "        except Exception:\n"
    "            pass\n"
    "        return True\n"
    "\n"
    "    # \u2500\u2500 Cookie-based session restore (survives F5 / new tab) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
    "    # Python reads the spp_session cookie from the HTTP request headers on\n"
    "    # every page load \u2014 no JS timing issues, no bridge reloads needed.\n"
    "    _cookie_tok = _get_session_cookie()\n"
    "    if _cookie_tok:\n"
    "        _cookie_user = _load_session_by_token(_cookie_tok)\n"
    "        if _cookie_user:\n"
    "            _set_logged_in(_cookie_user, _write_storage=False)\n"
    "            try:\n"
    '                st.query_params.pop("auth", None)\n'
    '                st.query_params.pop("_st", None)\n'
    "            except Exception:\n"
    "                pass\n"
    "            return True\n"
    "        else:\n"
    "            # Cookie token expired \u2014 clear it.\n"
    "            _clear_session_from_storage()\n"
    "\n"
    "    # \u2500\u2500 Fallback: localStorage bridge for environments that block cookies \u2500\u2500\u2500\u2500\u2500\n"
    "    _render_session_bridge()\n"
    "    try:\n"
    '        _tok = st.query_params.get("_st", "")\n'
    "        if _tok:\n"
    "            _user = _load_session_by_token(_tok)\n"
    "            if _user:\n"
    "                _set_logged_in(_user, _write_storage=False)\n"
    "                try:\n"
    '                    st.query_params.pop("_st", None)\n'
    '                    st.query_params.pop("auth", None)\n'
    "                except Exception:\n"
    "                    pass\n"
    "                return True\n"
    "            else:\n"
    "                _clear_session_from_storage()\n"
    '                st.query_params.pop("_st", None)\n'
    "    except Exception:\n"
    "        pass"
)

content = content[:_start] + _new_block + content[_end:]

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("written")

try:
    ast.parse(content)
    print("SYNTAX OK")
except SyntaxError as e:
    print(f"SYNTAX ERROR: {e}")
