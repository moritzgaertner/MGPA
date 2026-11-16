"""Single-user login: argon2 password hash, signed session cookie, simple brute-force lockout.

Set or change the login (writes AUTH_USERNAME, AUTH_PASSWORD_HASH and, if missing,
SESSION_SECRET into the repo's .env):

    uv run python -m mgpa_backend.auth
"""

import getpass
import re
import secrets
import time
from collections import defaultdict, deque
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, status

from mgpa_backend.config import REPO_ROOT, get_settings

_hasher = PasswordHasher()

# An argon2 hash of a random password: verified against when the username is wrong, so a
# wrong username takes as long as a wrong password (no timing hint about valid usernames).
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def check_credentials(username: str, password: str) -> bool:
    settings = get_settings()
    username_ok = secrets.compare_digest(username.encode(), settings.auth_username.encode())
    stored = settings.auth_password_hash.get_secret_value() if username_ok else _DUMMY_HASH
    password_ok = verify_password(stored, password)
    return username_ok and password_ok


class LoginLimiter:
    """At most `max_failures` failed logins per client within `window` seconds."""

    def __init__(self, max_failures: int = 5, window: float = 15 * 60) -> None:
        self.max_failures = max_failures
        self.window = window
        self._failures: defaultdict[str, deque[float]] = defaultdict(deque)

    def _recent(self, client: str) -> deque[float]:
        attempts = self._failures[client]
        while attempts and attempts[0] < time.monotonic() - self.window:
            attempts.popleft()
        return attempts

    def blocked(self, client: str) -> bool:
        return len(self._recent(client)) >= self.max_failures

    def record_failure(self, client: str) -> None:
        self._recent(client).append(time.monotonic())

    def reset(self, client: str) -> None:
        self._failures.pop(client, None)


login_limiter = LoginLimiter()


def require_user(request: Request) -> str:
    """Dependency for every protected endpoint: the session must belong to the configured user."""
    user = request.session.get("user")
    if not isinstance(user, str) or user != get_settings().auth_username:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")
    return user


CurrentUser = Annotated[str, Depends(require_user)]


# --- CLI: set the login in .env ----------------------------------------------------------------


def _set_env_values(values: dict[str, str]) -> None:
    """Update or append KEY='value' lines in the repo's .env. Single quotes keep the "$" signs of
    the argon2 hash literal for both pydantic-settings and Docker Compose."""
    env_path = REPO_ROOT / ".env"
    text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    lines = text.splitlines()
    for key, value in values.items():
        new_line = f"{key}='{value}'"
        positions = [i for i, line in enumerate(lines) if line.startswith(f"{key}=")]
        if positions:
            lines[positions[0]] = new_line
        else:
            lines.append(new_line)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    print("Set the MGPA login. The password is stored only as an argon2 hash in .env.")
    username = input("Username: ").strip()
    if not username:
        raise SystemExit("Username must not be empty.")
    password = getpass.getpass("Password (min. 12 characters): ")
    if len(password) < 12:
        raise SystemExit("Password too short — use at least 12 characters.")
    if getpass.getpass("Repeat password: ") != password:
        raise SystemExit("Passwords do not match.")

    values = {"AUTH_USERNAME": username, "AUTH_PASSWORD_HASH": hash_password(password)}
    env_text = (
        (REPO_ROOT / ".env").read_text(encoding="utf-8") if (REPO_ROOT / ".env").exists() else ""
    )
    if not re.search(r"^SESSION_SECRET=.+$", env_text, re.MULTILINE):
        values["SESSION_SECRET"] = secrets.token_urlsafe(48)
    _set_env_values(values)
    print(f"Saved to {REPO_ROOT / '.env'}. Restart the backend to apply.")


if __name__ == "__main__":
    main()
