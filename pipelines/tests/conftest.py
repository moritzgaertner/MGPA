"""Pipeline tests run against the backend's separate test database (never real data)."""

from collections.abc import Iterator
from pathlib import Path

from mgpa_backend.testing import use_test_credentials, use_test_database

use_test_credentials()
use_test_database()

import pytest  # noqa: E402
from mgpa_backend.config import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def documents_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setattr(get_settings(), "documents_dir", tmp_path)
    yield tmp_path
