"""Fix cookie setting (iframe vs parent) and cookie reading (headers vs st.context.cookies)."""
import ast

path = "utils/auth_gate.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

# ── 1. Fix _write_session_to_storage: use window.parent.document.cookie ──────
old_write = (
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
    "  // Clean the URL \u2014 remove ?auth=login and any other stale params.\n"
    "  var cleanUrl = window.parent.location.origin + window.parent.location.pathname;\n"
    '  window.parent.history.replaceState(null, "", cleanUrl);\n'
    "}})();\n"
    "</script>\n"
    '""", height=0)'
)

new_write = (
    "def _write_session_to_storage(token: str) -> None:\n"
    '    """Write the session token as an HTTP cookie on the PARENT page."""\n'
    "    import streamlit.components.v1 as _components\n"
    '    _components.html(f"""\n'
    "<script>\n"
    "(function() {{\n"
    "  // Set on the parent page (not the sandboxed iframe) so the browser\n"
    "  // sends it with every request including F5 / new tab.\n"
    "  try {{\n"
    '    window.parent.document.cookie = "spp_session={token}; path=/; max-age=604800; SameSite=Lax";\n'
    "  }} catch(e) {{\n"
    '    document.cookie = "spp_session={token}; path=/; max-age=604800; SameSite=Lax";\n'
    "  }}\n"
    '  try {{ window.parent.localStorage.setItem("{_LS_KEY}", "{token}"); }} catch(e) {{}}\n'
    "  // Strip ?auth= and ?_st= from the address bar.\n"
    "  try {{\n"
    "    var cleanUrl = window.parent.location.origin + window.parent.location.pathname;\n"
    '    window.parent.history.replaceState(null, "", cleanUrl);\n'
    "  }} catch(e) {{}}\n"
    "}})();\n"
    "</script>\n"
    '""", height=0)'
)

print("write old found:", old_write in content)
content = content.replace(old_write, new_write, 1)

# ── 2. Fix _clear_session_from_storage: use window.parent.document.cookie ────
old_clear = (
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

new_clear = (
    "def _clear_session_from_storage() -> None:\n"
    '    """Expire the session cookie and clear localStorage."""\n'
    "    import streamlit.components.v1 as _components\n"
    '    _components.html(f"""\n'
    "<script>\n"
    "(function() {{\n"
    "  try {{\n"
    '    window.parent.document.cookie = "spp_session=; path=/; max-age=0; SameSite=Lax";\n'
    "  }} catch(e) {{\n"
    '    document.cookie = "spp_session=; path=/; max-age=0; SameSite=Lax";\n'
    "  }}\n"
    '  try {{ window.parent.localStorage.removeItem("{_LS_KEY}"); }} catch(e) {{}}\n'
    "  try {{\n"
    "    var cleanUrl = window.parent.location.origin + window.parent.location.pathname;\n"
    '    window.parent.history.replaceState(null, "", cleanUrl);\n'
    "  }} catch(e) {{}}\n"
    "}})();\n"
    "</script>\n"
    '""", height=0)'
)

print("clear old found:", old_clear in content)
content = content.replace(old_clear, new_clear, 1)

# ── 3. Fix _get_session_cookie: use st.context.cookies (Streamlit 1.55 API) ──
old_cookie_fn = (
    "def _get_session_cookie() -> str:\n"
    '    """Read the spp_session cookie from request headers (works on every F5)."""\n'
    "    try:\n"
    '        cookie_header = st.context.headers.get("Cookie", "")\n'
    '        for _part in cookie_header.split(";"):\n'
    "            _part = _part.strip()\n"
    '            if _part.startswith("spp_session="):\n'
    '                return _part[len("spp_session="):]\n'
    "    except Exception:\n"
    "        pass\n"
    '    return ""\n'
)

new_cookie_fn = (
    "def _get_session_cookie() -> str:\n"
    '    """Read the spp_session cookie (works on every F5 / new tab)."""\n'
    "    # Primary: Streamlit 1.44+ proper cookie API\n"
    "    try:\n"
    '        return st.context.cookies.get("spp_session", "") or ""\n'
    "    except Exception:\n"
    "        pass\n"
    "    # Fallback: parse Cookie header manually\n"
    "    try:\n"
    '        cookie_header = st.context.headers.get("Cookie", "")\n'
    '        for _part in cookie_header.split(";"):\n'
    "            _part = _part.strip()\n"
    '            if _part.startswith("spp_session="):\n'
    '                return _part[len("spp_session="):]\n'
    "    except Exception:\n"
    "        pass\n"
    '    return ""\n'
)

print("cookie_fn old found:", old_cookie_fn in content)
content = content.replace(old_cookie_fn, new_cookie_fn, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("written")

try:
    ast.parse(content)
    print("SYNTAX OK")
except SyntaxError as e:
    print(f"SYNTAX ERROR: {e}")
