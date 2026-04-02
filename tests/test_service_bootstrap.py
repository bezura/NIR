import inspect

from fastapi.testclient import TestClient

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


def test_api_router_factory_registers_expected_paths() -> None:
    from nir_tagging_service.api import create_api_router

    router = create_api_router(Settings(database_url="sqlite:///./tagging-test.db"))
    paths = {route.path for route in router.routes}

    assert "/health" in paths
    assert "/readiness" in paths
    assert "/api/v1/tagging/jobs" in paths
    assert "/api/v1/tagging/jobs/{job_id}" in paths
    assert "/api/v1/tagging/jobs/{job_id}/result" in paths


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
