"""Patch require_login in auth_gate.py to clean URL after login."""
import ast

path = "utils/auth_gate.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

# Find the exact block between is_logged_in check and Portal routing comment
_start = content.find("    if is_logged_in():\n        return True\n\n    # \u2500\u2500 Try")
_end = content.find("\n    # \u2500\u2500 Portal routing: dedicated sign-in / sign-up view", _start)
old = content[_start:_end]

new = (
    "    if is_logged_in():\n"
    "        # Clean up any stale auth/token params left in the URL after login.\n"
    "        try:\n"
    "            _qp = st.query_params\n"
    '            if _qp.get("auth") or _qp.get("_st"):\n'
    '                _qp.pop("auth", None)\n'
    '                _qp.pop("_st", None)\n'
    "        except Exception:\n"
    "            pass\n"
    "        return True\n"
    "\n"
    "    # \u2500\u2500 Render JS bridge to restore session from localStorage on fresh page loads \u2500\u2500\n"
    "    # Reads the token from localStorage and sets ?_st=<token> in the URL, then\n"
    "    # reloads once so Python can read it in the block below. No-op when empty.\n"
    "    _render_session_bridge()\n"
    "\n"
    "    # \u2500\u2500 Try restoring from persistent localStorage token \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
    "    # After _write_session_to_storage navigates to /?_st=<token>, or after\n"
    "    # the bridge restores it, we validate and log in here.\n"
    "    try:\n"
    '        _tok = st.query_params.get("_st", "")\n'
    "        if _tok:\n"
    "            _user = _load_session_by_token(_tok)\n"
    "            if _user:\n"
    "                _set_logged_in(_user, _write_storage=False)\n"
    "                # Clean token and auth params so the final URL is plain /\n"
    "                try:\n"
    '                    st.query_params.pop("_st", None)\n'
    '                    st.query_params.pop("auth", None)\n'
    "                except Exception:\n"
    "                    pass\n"
    "                return True\n"
    "            else:\n"
    "                # Token expired or not found \u2014 clear stale storage.\n"
    "                _clear_session_from_storage()\n"
    '                st.query_params.pop("_st", None)\n'
    "    except Exception:\n"
    "        pass\n"
    "\n"
    "    # \u2500\u2500 Portal routing: dedicated sign-in / sign-up view \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
)

new = (
    "    if is_logged_in():\n"
    "        # Clean up any stale auth/token params left in the URL after login.\n"
    "        try:\n"
    "            _qp = st.query_params\n"
    '            if _qp.get("auth") or _qp.get("_st"):\n'
    '                _qp.pop("auth", None)\n'
    '                _qp.pop("_st", None)\n'
    "        except Exception:\n"
    "            pass\n"
    "        return True\n"
    "\n"
    "    # \u2500\u2500 Render JS bridge to restore session from localStorage on fresh page loads \u2500\u2500\n"
    "    # Reads the token from localStorage and sets ?_st=<token> in the URL, then\n"
    "    # reloads once so Python can read it in the block below. No-op when empty.\n"
    "    _render_session_bridge()\n"
    "\n"
    "    # \u2500\u2500 Try restoring from persistent localStorage token \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
    "    # After _write_session_to_storage navigates to /?_st=<token>, or after\n"
    "    # the bridge restores it, we validate and log in here.\n"
    "    try:\n"
    '        _tok = st.query_params.get("_st", "")\n'
    "        if _tok:\n"
    "            _user = _load_session_by_token(_tok)\n"
    "            if _user:\n"
    "                _set_logged_in(_user, _write_storage=False)\n"
    "                # Clean token and auth params so the final URL is plain /\n"
    "                try:\n"
    '                    st.query_params.pop("_st", None)\n'
    '                    st.query_params.pop("auth", None)\n'
    "                except Exception:\n"
    "                    pass\n"
    "                return True\n"
    "            else:\n"
    "                # Token expired or not found \u2014 clear stale storage.\n"
    "                _clear_session_from_storage()\n"
    '                st.query_params.pop("_st", None)\n'
    "    except Exception:\n"
    "        pass"
)

print("old found:", old in content)
new_content = content[:_start] + new + content[_end:]
print("changed:", new_content != content)

with open(path, "w", encoding="utf-8") as f:
    f.write(new_content)
print("written")

try:
    ast.parse(new_content)
    print("SYNTAX OK")
except SyntaxError as e:
    print(f"SYNTAX ERROR: {e}")
