import inspect
from importlib import import_module

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nir_tagging_service.config import Settings


def test_health_endpoint_reports_service_liveness() -> None:
    from nir_tagging_service.app import create_app

    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "tagging-subsystem",
    }


def test_readiness_endpoint_reports_service_readiness(tmp_path) -> None:
    from nir_tagging_service.app import create_app

    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-readiness.db'}")

    with TestClient(create_app(settings=settings)) as client:
        response = client.get("/readiness")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "tagging-subsystem",
    }


def test_cors_preflight_allows_local_demo_frontend(tmp_path) -> None:
    from nir_tagging_service.app import create_app

    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-cors.db'}")

    with TestClient(create_app(settings=settings)) as client:
        response = client.options(
            "/api/v1/tagging/jobs",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] in {"http://localhost:5173", "*"}
    assert "POST" in response.headers["access-control-allow-methods"]


def test_api_router_factory_registers_expected_paths() -> None:
    from nir_tagging_service.api import create_api_router

    router = create_api_router(Settings(database_url="sqlite:///./tagging-test.db"))
    paths = {route.path for route in router.routes}

    assert "/health" in paths
    assert "/readiness" in paths
    assert "/api/v1/tagging/jobs" in paths
    assert "/api/v1/tagging/jobs/{job_id}" in paths
    assert "/api/v1/tagging/jobs/{job_id}/result" in paths


def test_target_module_layout_exists() -> None:
    assert import_module("nir_tagging_service.bootstrap")
    assert import_module("nir_tagging_service.pipeline")
    assert import_module("nir_tagging_service.api")
    assert import_module("nir_tagging_service.api.system")
    assert import_module("nir_tagging_service.api.jobs")


def test_registered_http_handlers_are_async(tmp_path) -> None:
    from nir_tagging_service.app import create_app

    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-async.db'}")
    app = create_app(settings=settings)
    target_paths = {
        "/health",
        "/readiness",
        "/api/v1/tagging/jobs",
        "/api/v1/tagging/jobs/{job_id}",
        "/api/v1/tagging/jobs/{job_id}/result",
    }

    route_map = {
        route.path: route.endpoint
        for route in app.routes
        if getattr(route, "path", None) in target_paths
    }

    assert route_map.keys() == target_paths
    assert all(inspect.iscoroutinefunction(endpoint) for endpoint in route_map.values())


def test_app_exposes_async_session_factory(tmp_path) -> None:
    from nir_tagging_service.app import create_app

    settings = Settings(database_url=f"sqlite:///{tmp_path / 'tagging-async-session.db'}")
    app = create_app(settings=settings)

    assert isinstance(app.state.session_factory, async_sessionmaker)
    assert app.state.session_factory.class_ is AsyncSession
