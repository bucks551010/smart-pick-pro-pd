"""Fix the race condition: don't render cookie component inside _set_logged_in.
Instead store token in session_state and render it on the NEXT run when
is_logged_in() is True, so no st.rerun() races with the JS execution."""
import ast

path = "utils/auth_gate.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

# ── 1. In _set_logged_in: save token to session_state, don't render component
old_write_call = (
    "    # Write a persistent session token to localStorage so the user stays\n"
    "    # logged in across F5 reloads.\n"
    "    if _write_storage:\n"
    "        try:\n"
    "            _tok = secrets.token_urlsafe(32)\n"
    "            _save_login_session(_tok, user)\n"
    "            _write_session_to_storage(_tok)\n"
    "        except Exception:\n"
    "            pass"
)

new_write_call = (
    "    # Save a session token to session_state so require_login can write the\n"
    "    # cookie on the NEXT Streamlit run (after st.rerun()).  Rendering the JS\n"
    "    # component here then calling st.rerun() causes a race — the JS never\n"
    "    # executes before the rerun discards the render.\n"
    "    if _write_storage:\n"
    "        try:\n"
    "            _tok = secrets.token_urlsafe(32)\n"
    "            _save_login_session(_tok, user)\n"
    "            st.session_state[\"_pending_cookie_token\"] = _tok\n"
    "        except Exception:\n"
    "            pass"
)

print("write_call old found:", old_write_call in content)
content = content.replace(old_write_call, new_write_call, 1)

# ── 2. In require_login, when is_logged_in() is True: flush pending cookie ──
old_logged_in_block = (
    "    if is_logged_in():\n"
    "        # Clean any stale auth/token params from the URL after login.\n"
    "        try:\n"
    "            _qp = st.query_params\n"
    "            if _qp.get(\"auth\") or _qp.get(\"_st\"):\n"
    "                _qp.pop(\"auth\", None)\n"
    "                _qp.pop(\"_st\", None)\n"
    "        except Exception:\n"
    "            pass\n"
    "        return True"
)

new_logged_in_block = (
    "    if is_logged_in():\n"
    "        # Flush any pending cookie token.  This runs on the run AFTER login\n"
    "        # (post-st.rerun()), so no st.rerun() follows — the JS executes cleanly.\n"
    "        _pending = st.session_state.pop(\"_pending_cookie_token\", None)\n"
    "        if _pending:\n"
    "            _write_session_to_storage(_pending)\n"
    "        # Clean any stale auth/token params from the URL.\n"
    "        try:\n"
    "            _qp = st.query_params\n"
    "            if _qp.get(\"auth\") or _qp.get(\"_st\"):\n"
    "                _qp.pop(\"auth\", None)\n"
    "                _qp.pop(\"_st\", None)\n"
    "        except Exception:\n"
    "            pass\n"
    "        return True"
)

print("logged_in_block old found:", old_logged_in_block in content)
content = content.replace(old_logged_in_block, new_logged_in_block, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("written")

try:
    ast.parse(content)
    print("SYNTAX OK")
except SyntaxError as e:
    print(f"SYNTAX ERROR: {e}")
