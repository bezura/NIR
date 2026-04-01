from fastapi.testclient import TestClient


def test_health_endpoint_reports_service_liveness() -> None:
    from nir_tagging_service.app import create_app

    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "tagging-subsystem",
    }
