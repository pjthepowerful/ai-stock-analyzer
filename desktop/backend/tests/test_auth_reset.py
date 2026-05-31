"""Tests for the password-reset flow in auth.py.

Uses an isolated temp database so it never touches paula.db.

Run directly:  python3 desktop/backend/tests/test_auth_reset.py
Or via pytest: pytest desktop/backend/tests/test_auth_reset.py
"""
import os
import sys
import time
import tempfile

# Make the backend dir importable.
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import auth  # noqa: E402

# Point auth at a throwaway DB BEFORE creating any data.
_TMP_DB = os.path.join(tempfile.mkdtemp(), "test_paula.db")
auth.DB_PATH = _TMP_DB
auth.init_db()

EMAIL = "pj@trader.io"
USERNAME = "PJ"
OLD_PW = "oldpass123"
NEW_PW = "newpass456"


def _fresh_user(email=EMAIL):
    """Ensure a known user exists; ignore 'already exists'."""
    auth.signup(USERNAME, OLD_PW, email)


def test_create_token_for_real_email():
    _fresh_user()
    info = auth.create_reset_token(EMAIL)
    assert info is not None, "should return token info for a real account"
    assert info["token"] and len(info["token"]) > 20
    assert info["email"] == EMAIL


def test_create_token_unknown_email_returns_none():
    assert auth.create_reset_token("nobody@nowhere.com") is None
    assert auth.create_reset_token("") is None


def test_email_lookup_is_case_insensitive():
    info = auth.create_reset_token(EMAIL.upper())
    assert info is not None, "uppercase email should still match"


def test_full_reset_changes_password():
    info = auth.create_reset_token(EMAIL)
    res = auth.reset_password(info["token"], NEW_PW)
    assert res["ok"] is True
    # Old password no longer works; new one does.
    assert auth.login(EMAIL, OLD_PW)["ok"] is False
    assert auth.login(EMAIL, NEW_PW)["ok"] is True
    # Restore for independence of other tests.
    auth.reset_password(auth.create_reset_token(EMAIL)["token"], OLD_PW)


def test_token_is_single_use():
    info = auth.create_reset_token(EMAIL)
    first = auth.reset_password(info["token"], "temppass789")
    assert first["ok"] is True
    second = auth.reset_password(info["token"], "anotherpass")
    assert second["ok"] is False, "a used token must be rejected"
    # Restore.
    auth.reset_password(auth.create_reset_token(EMAIL)["token"], OLD_PW)


def test_new_token_invalidates_prior_outstanding_token():
    first = auth.create_reset_token(EMAIL)
    second = auth.create_reset_token(EMAIL)  # should invalidate `first`
    assert auth.reset_password(first["token"], "shouldfail123")["ok"] is False
    assert auth.reset_password(second["token"], OLD_PW)["ok"] is True


def test_expired_token_rejected():
    info = auth.create_reset_token(EMAIL)
    # Force expiry by stamping the row into the past.
    db = auth._get_db()
    db.execute("UPDATE password_resets SET expires_at = ? WHERE token_hash = ?",
               (int(time.time()) - 10, auth._hash_token(info["token"])))
    db.commit()
    db.close()
    res = auth.reset_password(info["token"], "whatever123")
    assert res["ok"] is False and "expired" in res["error"].lower()


def test_bad_token_rejected():
    assert auth.reset_password("not-a-real-token", NEW_PW)["ok"] is False
    assert auth.reset_password("", NEW_PW)["ok"] is False


def test_short_password_rejected():
    info = auth.create_reset_token(EMAIL)
    res = auth.reset_password(info["token"], "abc")
    assert res["ok"] is False and "6 characters" in res["error"]


def test_raw_token_not_stored():
    info = auth.create_reset_token(EMAIL)
    db = auth._get_db()
    rows = db.execute("SELECT token_hash FROM password_resets").fetchall()
    db.close()
    stored = [r["token_hash"] for r in rows]
    assert info["token"] not in stored, "raw token must never be stored"
    assert auth._hash_token(info["token"]) in stored, "hashed token should be stored"
    auth.reset_password(info["token"], OLD_PW)  # cleanup


def test_mixed_case_signup_email_is_resettable_and_loginable():
    # Regression: signup used to store email verbatim while reset/login
    # lowercased it, so a mixed-case signup could never reset or log in by email.
    mixed = "Casey@Example.com"
    auth.signup("Casey", OLD_PW, mixed)
    # Reset lookup (lowercased) must still find the account.
    assert auth.create_reset_token(mixed) is not None
    assert auth.create_reset_token(mixed.lower()) is not None
    # Login by email in either case must work.
    assert auth.login(mixed, OLD_PW)["ok"] is True
    assert auth.login(mixed.lower(), OLD_PW)["ok"] is True


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
        except Exception as e:
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    print(f"auth reset tests (temp db: {_TMP_DB})")
    sys.exit(0 if _run() else 1)
