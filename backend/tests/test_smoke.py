"""Smoke test so the test suite is never empty (pytest exits non-zero on zero tests)."""

import mgpa_backend


def test_package_imports() -> None:
    assert mgpa_backend.__doc__
