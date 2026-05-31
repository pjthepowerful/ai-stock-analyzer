#!/usr/bin/env python3
"""Run all Paula backend tests. No pytest required.

Usage:  python3 desktop/backend/tests/run_all.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = ["test_signal_logic.py", "test_auth_reset.py"]


def main():
    all_ok = True
    for suite in SUITES:
        print(f"\n{'='*50}\n{suite}\n{'='*50}")
        rc = subprocess.call([sys.executable, os.path.join(HERE, suite)])
        all_ok = all_ok and rc == 0
    print(f"\n{'='*50}")
    print("ALL SUITES PASSED" if all_ok else "SOME SUITES FAILED")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
