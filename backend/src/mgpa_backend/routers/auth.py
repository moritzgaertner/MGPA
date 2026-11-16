"""Login, logout and "who am I" for the single user."""

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from mgpa_backend.auth import CurrentUser, check_credentials, login_limiter

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class Me(BaseModel):
    username: str


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
async def login(body: LoginRequest, request: Request) -> Response:
    client = request.client.host if request.client else "unknown"
    if login_limiter.blocked(client):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts. Try again in 15 minutes."
        )
    # argon2 is deliberately slow (~50 ms): run it in a thread so the server stays responsive.
    if not await run_in_threadpool(check_credentials, body.username, body.password):
        login_limiter.record_failure(client)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password")
    login_limiter.reset(client)
    request.session.clear()  # fresh session on login
    request.session["user"] = body.username
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(user: CurrentUser) -> Me:
    return Me(username=user)
