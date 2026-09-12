"""Security regression tests.

Two real holes existed before v4.17.0:
  1. /api/buy, /sell, /short, /cover, /close-all took no authorization at all.
     Anyone who knew the backend URL could trade the live account.
  2. The CORS policy matched every *.vercel.app origin with allow_credentials,
     so any attacker deployment was a permitted origin.

These are static checks over the source, so they run without a live server.
"""
import os
import pathlib
import re
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SERVER = pathlib.Path(_ROOT) / "desktop" / "backend" / "server.py"

# Endpoints that may legitimately be reached without a token.
PUBLIC = {"/api/auth/signup", "/api/auth/login", "/api/auth/verify-code",
          "/api/auth/resend-code", "/api/auth/forgot", "/api/auth/reset"}

TRADING = {"/api/buy", "/api/sell", "/api/short", "/api/cover", "/api/close-all"}


def _endpoints():
    """path -> (signature, body). The signature is checked separately: a body
    mentioning `authorization` proves nothing if the parameter was never
    declared — the handler would just NameError at request time."""
    lines = SERVER.read_text().splitlines()
    out = {}
    for i, l in enumerate(lines):
        m = re.match(r'@app\.(post|delete|put)\("([^"]+)"', l.strip())
        if not m:
            continue
        sig = ""
        for j in range(i + 1, min(i + 4, len(lines))):
            if lines[j].lstrip().startswith("async def") or lines[j].lstrip().startswith("def "):
                sig = lines[j]
                while "):" not in sig and j + 1 < len(lines):
                    j += 1
                    sig += lines[j]
                break
        out[m.group(2)] = (sig, "\n".join(lines[i:i + 18]))
    return out


def test_no_state_changing_endpoint_is_unauthenticated():
    bad = [p for p, (sig, _) in _endpoints().items()
           if p not in PUBLIC and "authorization" not in sig.lower()]
    assert not bad, f"unauthenticated state-changing endpoints: {bad}"


def test_every_trading_endpoint_requires_a_trader():
    missing = []
    for p, (sig, body) in _endpoints().items():
        if p in TRADING and ("_require_trader" not in body
                             or "authorization" not in sig.lower()):
            missing.append(p)
    assert not missing, f"trading endpoints without _require_trader: {missing}"


def test_trader_guard_checks_both_identity_and_permission():
    src = SERVER.read_text()
    guard = src[src.index("def _require_trader("):]
    guard = guard[:guard.index("\n@app")]
    assert "_get_user(" in guard, "guard must resolve a user"
    assert "_can_autopilot(" in guard, "guard must check trade permission, not just login"


def test_cors_does_not_allow_arbitrary_vercel_origins():
    src = SERVER.read_text()
    m = re.search(r'allow_origin_regex=(.*?),\n\s*allow_credentials', src, re.DOTALL)
    assert m, "could not locate the CORS origin policy"
    block = m.group(1)
    # Pull the default regex out of the os.environ.get(...) fallback.
    literals = re.findall(r'r"([^"]+)"', block)
    rx = "".join(literals)
    assert rx, "no regex literal found"
    for evil in ("https://totally-evil-attacker.vercel.app",
                 "https://paula-clone.vercel.app",
                 "https://evil.com"):
        assert not re.fullmatch(rx, evil), f"CORS still permits {evil}"
    for ok in ("https://ai-stock-analyzer-six.vercel.app", "http://localhost:5173"):
        assert re.fullmatch(rx, ok), f"CORS now blocks legitimate origin {ok}"


def test_no_hardcoded_credentials_in_source():
    pats = [r"wzJ5v31[A-Za-z0-9_-]+", r"gsk_[A-Za-z0-9]{30,}",
            r"PK[A-Z0-9]{14,}", r"sk-[A-Za-z0-9]{20,}",
            r"github_pat_[A-Za-z0-9_]{30,}"]
    offenders = []
    root = pathlib.Path(_ROOT)
    for f in list(root.rglob("*.py")) + list(root.rglob("*.jsx")):
        if "node_modules" in str(f) or f.name == "test_security.py":
            continue
        txt = f.read_text(errors="ignore")
        for pat in pats:
            if re.search(pat, txt):
                offenders.append(f"{f.relative_to(root)} ~ {pat}")
    assert not offenders, f"credentials in source: {offenders}"


def test_jwt_secret_is_not_hardcoded():
    auth = (pathlib.Path(_ROOT) / "desktop" / "backend" / "auth.py").read_text()
    m = re.search(r'JWT_SECRET\s*=\s*os\.environ\.get\("JWT_SECRET"(?:,\s*"([^"]*)")?\)', auth)
    assert m, "JWT_SECRET must come from the environment"
    assert not m.group(1), "JWT_SECRET must not have a hardcoded default"


def main():
    tests = [(n, o) for n, o in sorted(globals().items())
             if n.startswith("test_") and callable(o)]
    print("security tests")
    failed = 0
    for name, fn in tests:
        try:
            fn(); print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1; print(f"  FAIL  {name}: {e}")
        except Exception as e:
            failed += 1; print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
