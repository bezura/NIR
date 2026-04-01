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
