"""FastAPI application: routes, authentication, validation, and error envelope.

Routes stay thin; each workflow lives in its own module (monitoring, assistant,
handoff, feedback) behind repository, policy, AI, and customer adapters.
"""
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Annotated, Literal, Optional

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from . import __version__
from .ai import AIAdapter
from .assistant import Assistant
from .config import Settings, load_settings
from .customer_adapter import CustomerAdapter
from .errors import ApiError, envelope
from .feedback import Feedback
from .handoff import Handoff
from .monitoring import Monitoring
from .policy import Policy
from .repository import Repository
from .security import issue_token, read_token, verify_password
from .seed import seed

UUID_RE = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
UUIDStr = Annotated[str, StringConstraints(pattern=UUID_RE)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class TokenIn(Strict):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class ReadingIn(Strict):
    reading_id: UUIDStr
    observed_at: str
    temperature_c: float
    ph: float
    water_level_pct: float


class MessageIn(Strict):
    message_id: UUIDStr
    conversation_id: UUIDStr
    text: str = Field(min_length=1, max_length=2000)


class CaseIn(Strict):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class ReplyIn(Strict):
    reply_id: UUIDStr
    text: str = Field(min_length=1, max_length=4000)
    close_case: bool


class FeedbackIn(Strict):
    helpful: bool
    comment: Optional[str] = Field(default=None, max_length=1000)


def create_app(settings: Settings | None = None, ai_provider=None) -> FastAPI:
    settings = settings or load_settings()
    repo = Repository(settings.database_path)
    seed(repo)
    policy = Policy()
    monitoring = Monitoring(repo, policy)
    if ai_provider:
        ai = AIAdapter(ai_provider, settings.ai_deadline_seconds)
    else:
        ai = AIAdapter(deadline=settings.ai_deadline_seconds)
    assistant = Assistant(repo, policy, monitoring, ai, CustomerAdapter(repo))
    handoff = Handoff(repo, policy)
    feedback = Feedback(repo)
    chat_hits: dict[str, deque] = defaultdict(deque)

    app = FastAPI(title="AquaGuard API", version=__version__)
    app.state.repo, app.state.policy, app.state.ai, app.state.feedback = repo, policy, ai, feedback

    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError):
        return JSONResponse(envelope(exc.code, exc.message, exc.fields), status_code=exc.status,
                            headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        errors = exc.errors()
        if any(e.get("type") == "json_invalid" for e in errors):
            return JSONResponse(envelope("malformed_json", "Malformed JSON"), status_code=400)
        fields = [{"field": ".".join(str(p) for p in e["loc"][1:]) or "body", "issue": e["msg"]}
                  for e in errors]
        return JSONResponse(envelope("validation_error", "Invalid input", fields), status_code=422)

    def principal(authorization: Annotated[Optional[str], Header()] = None) -> dict:
        if not authorization or not authorization.startswith("Bearer "):
            raise ApiError(401, "unauthorized", "Missing or invalid token")
        claims = read_token(authorization[7:], settings.token_secret)
        if claims is None:
            raise ApiError(401, "unauthorized", "Missing or invalid token")
        return claims

    Principal = Annotated[dict, Depends(principal)]

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "version": __version__, "model_version": "aq-v1"}

    @app.post("/api/v1/auth/token")
    def token(body: TokenIn):
        user = repo.one("SELECT * FROM users WHERE username = ?", (body.username,))
        if user is None or not verify_password(body.password, user["password_hash"]):
            raise ApiError(401, "invalid_credentials", "Invalid username or password")
        scopes = [r["client_id"] for r in
                  repo.all("SELECT client_id FROM agent_scopes WHERE user_id = ?", (user["user_id"],))]
        claims = {"user_id": user["user_id"], "username": user["username"], "role": user["role"],
                  "client_id": user["client_id"], "scopes": scopes}
        return {"access_token": issue_token(claims, settings.token_secret, settings.token_ttl_seconds),
                "token_type": "bearer", "expires_in": settings.token_ttl_seconds}

    @app.get("/api/v1/me")
    def me(p: Principal):
        tanks = []
        if p["role"] == "customer":
            tanks = [dict(r) for r in repo.all(
                "SELECT tank_id, name FROM tanks WHERE client_id = ? ORDER BY name", (p["client_id"],))]
        elif p["role"] == "agent" and p["scopes"]:
            marks = ",".join("?" * len(p["scopes"]))
            tanks = [dict(r) for r in repo.all(
                f"SELECT tank_id, name FROM tanks WHERE client_id IN ({marks}) ORDER BY name",
                tuple(p["scopes"]))]
        return {"username": p["username"], "role": p["role"], "tanks": tanks}

    @app.post("/api/v1/tanks/{tank_id}/readings")
    def ingest(tank_id: str, body: ReadingIn, p: Principal):
        status, out = monitoring.ingest(p, tank_id, body.model_dump())
        return JSONResponse(out, status_code=status)

    @app.get("/api/v1/tanks/{tank_id}/readings")
    def history(tank_id: str, p: Principal, limit: Annotated[int, Query(ge=1, le=500)] = 100,
                cursor: Optional[str] = None):
        return monitoring.history(p, tank_id, limit, cursor)

    @app.post("/api/v1/tanks/{tank_id}/messages")
    def message(tank_id: str, body: MessageIn, p: Principal):
        hits = chat_hits[p["user_id"]]
        now = time.monotonic()
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= settings.chat_limit_per_minute:
            raise ApiError(429, "rate_limited", "Too many chat requests", headers={"Retry-After": "10"})
        hits.append(now)
        status, out = assistant.respond(p, tank_id, body.model_dump())
        return JSONResponse(out, status_code=status)

    @app.post("/api/v1/conversations/{conversation_id}/cases")
    def open_case(conversation_id: str, body: CaseIn, p: Principal):
        if p["role"] != "customer":
            raise ApiError(403, "forbidden", "Role not permitted")
        status, out = handoff.open(p, conversation_id, body.reason)
        return JSONResponse(out, status_code=status)

    @app.get("/api/v1/cases")
    def cases(p: Principal, status: Literal["open", "closed"] = "open",
              limit: Annotated[int, Query(ge=1, le=100)] = 50):
        return handoff.queue(p, status, limit)

    @app.get("/api/v1/conversations/{conversation_id}/messages")
    def transcript(conversation_id: str, p: Principal, limit: Annotated[int, Query(ge=1, le=100)] = 50):
        return handoff.transcript(p, conversation_id, limit)

    @app.post("/api/v1/cases/{case_id}/replies")
    def reply(case_id: str, body: ReplyIn, p: Principal):
        status, out = handoff.reply(p, case_id, body.model_dump())
        return JSONResponse(out, status_code=status)

    @app.post("/api/v1/messages/{message_id}/feedback")
    def give_feedback(message_id: str, body: FeedbackIn, p: Principal):
        if p["role"] != "customer":
            raise ApiError(403, "forbidden", "Role not permitted")
        status, out = feedback.submit(p, message_id, body.model_dump(exclude_none=True))
        return JSONResponse(out, status_code=status)

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(static_dir / "index.html")

    return app
