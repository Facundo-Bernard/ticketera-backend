from dataclasses import dataclass, field
from datetime import timedelta
from typing import List, Optional
from fastapi import Request, Response
from ...config.settings import settings
from ..auth.security import create_access_token, decode_access_token

REQUESTER_SESSION_COOKIE = "coopya_requester_session"
REQUESTER_TICKETS_COOKIE = "coopya_requester_tickets"
REQUESTER_SESSION_EXPIRE_DAYS = 365
REQUESTER_SESSION_MAX_AGE = REQUESTER_SESSION_EXPIRE_DAYS * 86400
MAX_TRACKED_LOCAL_TICKETS = 40


@dataclass
class RequesterContext:
    email: Optional[str] = None
    local_ticket_ids: List[str] = field(default_factory=list)

    @property
    def has_any_access(self) -> bool:
        return bool(self.email or self.local_ticket_ids)


def create_requester_session_token(email: str) -> str:
    return create_access_token(
        data={
            "sub": email.strip().lower(),
            "scope": "requester_session",
        },
        expires_delta=timedelta(days=REQUESTER_SESSION_EXPIRE_DAYS),
    )


def decode_requester_session_token(token: str) -> Optional[str]:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except Exception:
        return None
    if payload.get("scope") != "requester_session":
        return None
    sub = payload.get("sub")
    if isinstance(sub, str) and "@" in sub:
        return sub.strip().lower()
    return None


def create_requester_tickets_token(ticket_ids: List[str]) -> str:
    unique_ids: List[str] = []
    seen = set()
    for tid in ticket_ids:
        clean = str(tid).strip()
        if clean and clean not in seen:
            seen.add(clean)
            unique_ids.append(clean)

    trimmed = unique_ids[-MAX_TRACKED_LOCAL_TICKETS:]
    return create_access_token(
        data={
            "ticket_ids": trimmed,
            "scope": "requester_tickets",
        },
        expires_delta=timedelta(days=REQUESTER_SESSION_EXPIRE_DAYS),
    )


def decode_requester_tickets_token(token: str) -> List[str]:
    if not token:
        return []
    try:
        payload = decode_access_token(token)
    except Exception:
        return []
    if payload.get("scope") != "requester_tickets":
        return []
    raw_ids = payload.get("ticket_ids")
    if not isinstance(raw_ids, list):
        return []
    return [str(tid).strip() for tid in raw_ids if isinstance(tid, str) and tid.strip()]


def extract_requester_context(request: Request) -> RequesterContext:
    session_cookie = request.cookies.get(REQUESTER_SESSION_COOKIE) or ""
    tickets_cookie = request.cookies.get(REQUESTER_TICKETS_COOKIE) or ""

    return RequesterContext(
        email=decode_requester_session_token(session_cookie),
        local_ticket_ids=decode_requester_tickets_token(tickets_cookie),
    )


def _is_secure_request(request: Request) -> bool:
    return bool(
        settings.COOKIE_SECURE
        or request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https"
    )


def set_requester_session_cookie(
    response: Response,
    email: str,
    request: Request,
) -> None:
    token = create_requester_session_token(email)
    response.set_cookie(
        key=REQUESTER_SESSION_COOKIE,
        value=token,
        httponly=True,
        max_age=REQUESTER_SESSION_MAX_AGE,
        expires=REQUESTER_SESSION_MAX_AGE,
        samesite="lax",
        secure=_is_secure_request(request),
        path="/",
    )


def clear_requester_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        key=REQUESTER_SESSION_COOKIE,
        httponly=True,
        samesite="lax",
        secure=_is_secure_request(request),
        path="/",
    )


def append_ticket_to_requester_cookie(
    request: Request,
    response: Response,
    ticket_id: str,
) -> None:
    existing_ids = decode_requester_tickets_token(
        request.cookies.get(REQUESTER_TICKETS_COOKIE) or ""
    )
    updated_ids = [*existing_ids, str(ticket_id)]
    token = create_requester_tickets_token(updated_ids)
    response.set_cookie(
        key=REQUESTER_TICKETS_COOKIE,
        value=token,
        httponly=True,
        max_age=REQUESTER_SESSION_MAX_AGE,
        expires=REQUESTER_SESSION_MAX_AGE,
        samesite="lax",
        secure=_is_secure_request(request),
        path="/",
    )
