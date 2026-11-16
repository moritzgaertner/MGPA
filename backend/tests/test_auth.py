"""Login: protected endpoints, session cookie, wrong credentials, lockout, password hashing."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mgpa_backend import auth
from mgpa_backend.auth import LoginLimiter, hash_password, login_limiter, verify_password
from mgpa_backend.testing import TEST_PASSWORD, TEST_USERNAME


@pytest.fixture(autouse=True)
def fresh_limiter() -> Iterator[None]:
    login_limiter._failures.clear()
    yield
    login_limiter._failures.clear()


def login(client: TestClient, username: str = TEST_USERNAME, password: str = TEST_PASSWORD) -> int:
    return client.post("/auth/login", json={"username": username, "password": password}).status_code


@pytest.mark.parametrize(
    "path", ["/conversations", "/notes", "/documents", "/training/plan", "/auth/me"]
)
def test_endpoints_require_login(anonymous_client: TestClient, path: str) -> None:
    assert anonymous_client.get(path).status_code == 401


def test_chat_requires_login(anonymous_client: TestClient) -> None:
    assert anonymous_client.post("/chat", json={"message": "hi"}).status_code == 401


def test_health_stays_public(anonymous_client: TestClient) -> None:
    assert anonymous_client.get("/health").status_code == 200


def test_login_sets_a_session_that_unlocks_the_api(anonymous_client: TestClient) -> None:
    assert login(anonymous_client) == 204

    cookie = anonymous_client.cookies.get("mgpa_session")
    assert cookie and TEST_PASSWORD not in cookie  # signed session data, never the password
    assert anonymous_client.get("/auth/me").json() == {"username": TEST_USERNAME}
    assert anonymous_client.get("/notes").status_code == 200


def test_logout_ends_the_session(anonymous_client: TestClient) -> None:
    login(anonymous_client)

    assert anonymous_client.post("/auth/logout").status_code == 204
    assert anonymous_client.get("/notes").status_code == 401


def test_wrong_password_or_username_is_rejected(anonymous_client: TestClient) -> None:
    assert login(anonymous_client, password="wrong password") == 401
    assert login(anonymous_client, username="someone else") == 401
    assert anonymous_client.get("/notes").status_code == 401


def test_forged_cookie_is_rejected(anonymous_client: TestClient) -> None:
    anonymous_client.cookies.set("mgpa_session", "eyJ1c2VyIjogInRlc3RlciJ9.forged.signature")

    assert anonymous_client.get("/notes").status_code == 401


def test_too_many_failures_lock_the_login(anonymous_client: TestClient) -> None:
    for _ in range(5):
        login(anonymous_client, password="wrong")

    # Even the correct password is refused during the lockout.
    assert login(anonymous_client) == 429


def test_limiter_forgets_old_failures() -> None:
    limiter = LoginLimiter(max_failures=2, window=0)
    limiter.record_failure("1.2.3.4")
    limiter.record_failure("1.2.3.4")

    assert not limiter.blocked("1.2.3.4")  # window of 0 s: failures expired immediately


def test_env_file_update_keeps_other_lines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=x\nAUTH_USERNAME='old'\n# comment\n", encoding="utf-8")
    monkeypatch.setattr(auth, "REPO_ROOT", tmp_path)

    auth._set_env_values({"AUTH_USERNAME": "new", "AUTH_PASSWORD_HASH": "$argon2id$v=19$abc"})

    assert env.read_text(encoding="utf-8").splitlines() == [
        "DATABASE_URL=x",
        "AUTH_USERNAME='new'",
        "# comment",
        "AUTH_PASSWORD_HASH='$argon2id$v=19$abc'",
    ]


def test_password_hashing() -> None:
    stored = hash_password("secret password")

    assert stored.startswith("$argon2id$") and "secret password" not in stored
    assert verify_password(stored, "secret password")
    assert not verify_password(stored, "Secret password")
    assert not verify_password("not-a-hash", "secret password")
