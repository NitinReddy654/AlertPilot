from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .cache import OptionalRedisCache
from .config import Settings
from .database import Database
from .observability import ALERTS_DEDUPLICATED, INCIDENTS_CREATED, JsonRequestLogger, configure_logging, prometheus_response
from .schemas import (
    AlertIn,
    IncidentActionResponse,
    IncidentDetail,
    IncidentOut,
    LoginRequest,
    ServiceIn,
    ServiceOut,
    SummaryResponse,
    TokenResponse,
    UserContext,
)
from .security import AuthError, create_token, verify_password, verify_token
from .triage import IncidentService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.ensure_runtime_dirs()
    configure_logging(settings.log_level)

    db = Database(settings)
    db.initialize()
    incidents = IncidentService(db)

    app = FastAPI(
        title="AlertPilot Incident Triage API",
        version="1.0.0",
        description="Production-style alert ingestion, incident deduplication, and escalation service.",
    )
    app.state.settings = settings
    app.state.db = db
    app.state.incidents = incidents
    app.state.cache = OptionalRedisCache(settings.enable_redis, settings.redis_url)
    app.add_middleware(JsonRequestLogger)

    static_dir = Path(__file__).resolve().parent.parent / "static"
    app.mount("/assets", StaticFiles(directory=static_dir), name="assets")

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(static_dir / "dashboard.html")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    @app.get("/ready")
    def ready(request: Request) -> dict[str, str]:
        request.app.state.db.query_one("SELECT 1 AS ok")
        return {"status": "ready"}

    @app.post("/v1/auth/login", response_model=TokenResponse)
    def login(request: Request, payload: LoginRequest) -> TokenResponse:
        user = request.app.state.db.query_one("SELECT * FROM users WHERE email = ?", (payload.email,))
        if user is None or not verify_password(payload.password, user["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        token = create_token(
            {"sub": user["email"], "role": user["role"]},
            request.app.state.settings.token_secret,
            request.app.state.settings.token_ttl_seconds,
        )
        request.app.state.db.audit(user["email"], "auth.login", user["email"])
        return TokenResponse(access_token=token, expires_in=request.app.state.settings.token_ttl_seconds)

    def current_user(
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
    ) -> UserContext:
        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
        token = authorization.removeprefix("Bearer ").strip()
        try:
            claims = verify_token(token, request.app.state.settings.token_secret)
        except AuthError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
        user = request.app.state.db.query_one("SELECT * FROM users WHERE email = ?", (claims["sub"],))
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
        return UserContext(email=user["email"], role=user["role"])

    @app.get("/v1/services", response_model=list[ServiceOut])
    def list_services(request: Request, _: UserContext = Depends(current_user)):
        return request.app.state.incidents.list_services()

    @app.post("/v1/services", response_model=ServiceOut)
    def upsert_service(
        request: Request,
        payload: ServiceIn,
        user: UserContext = Depends(current_user),
    ):
        if user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
        return request.app.state.incidents.upsert_service(payload)

    @app.post("/v1/alerts", response_model=IncidentOut, status_code=status.HTTP_201_CREATED)
    def ingest_alert(
        request: Request,
        payload: AlertIn,
        user: UserContext = Depends(current_user),
    ):
        request.app.state.cache.increment("alerts_received")
        before = request.app.state.incidents.summary().total_occurrences
        incident = request.app.state.incidents.ingest(payload, user.email)
        after_summary = request.app.state.incidents.summary()
        if after_summary.total_occurrences == before + 1 and incident.occurrences == 1:
            INCIDENTS_CREATED.inc()
        else:
            ALERTS_DEDUPLICATED.inc()
        return incident

    @app.get("/v1/incidents", response_model=list[IncidentOut])
    def list_incidents(
        request: Request,
        _: UserContext = Depends(current_user),
        status_filter: Annotated[str | None, Query(alias="status")] = None,
        limit: int = Query(50, ge=1, le=250),
    ):
        return request.app.state.incidents.list_incidents(status_filter, limit)

    @app.get("/v1/incidents/{incident_id}", response_model=IncidentDetail)
    def get_incident(
        request: Request,
        incident_id: str,
        _: UserContext = Depends(current_user),
    ):
        try:
            return IncidentDetail(**request.app.state.incidents.get_detail(incident_id))
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found") from exc

    @app.post("/v1/incidents/{incident_id}/ack", response_model=IncidentActionResponse)
    def acknowledge_incident(
        request: Request,
        incident_id: str,
        user: UserContext = Depends(current_user),
    ):
        try:
            incident = request.app.state.incidents.acknowledge(incident_id, user.email)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found") from exc
        return IncidentActionResponse(incident=incident, message="Incident acknowledged")

    @app.post("/v1/incidents/{incident_id}/resolve", response_model=IncidentActionResponse)
    def resolve_incident(
        request: Request,
        incident_id: str,
        user: UserContext = Depends(current_user),
    ):
        try:
            incident = request.app.state.incidents.resolve(incident_id, user.email)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found") from exc
        return IncidentActionResponse(incident=incident, message="Incident resolved")

    @app.get("/v1/summary", response_model=SummaryResponse)
    def summary(request: Request, _: UserContext = Depends(current_user)):
        return request.app.state.incidents.summary()

    @app.get("/metrics")
    def metrics():
        return prometheus_response()

    return app


app = create_app()

