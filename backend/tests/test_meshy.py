"""All hosted-provider tests use HTTP simulation; no real task is created or billed."""

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
import pytest

from app.common.config import Settings, get_settings
from app.common.storage import get_storage
from app.modules.generation.meshy import (
    API,
    MeshyProvider,
    ProviderError,
    select_views,
    validate_glb,
)
from app.modules.generation.providers import dummy_glb


def adapter(monkeypatch, handler):
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_provider", "meshy")
    monkeypatch.setattr(settings, "meshy_api_key", "not-a-real-test-key")
    monkeypatch.setattr(settings, "meshy_daily_request_limit", 1)
    storage = Mock()
    storage.get.return_value = b"sanitized photo fixture"
    return MeshyProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        storage=storage,
        sleep=lambda _: None,
    )


def test_hosted_configuration_requires_explicit_key_cap_and_queue():
    for kwargs in [
        {},
        {"meshy_api_key": "test"},
        {"meshy_api_key": "test", "meshy_daily_request_limit": 1, "queue_mode": "inline"},
    ]:
        with pytest.raises(ValueError):
            Settings(ai_provider="meshy", **kwargs)


def test_meshy_front_first_and_four_of_five_preserves_source_list():
    images = [
        SimpleNamespace(id=i, storage_key=str(i), sort_order=i, view_tag=tag)
        for i, tag in enumerate(["unspecified", "left", "front", "back", "right"])
    ]
    chosen = select_views(images)
    assert [image.view_tag for image in chosen] == ["front", "left", "back", "right"]
    assert len(images) == 5


def test_meshy_submits_once_polls_and_downloads_embedded_glb(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if request.method == "POST":
            assert str(request.url) == API
            assert request.headers["authorization"] == "Bearer not-a-real-test-key"
            payload = json.loads(request.content)
            assert len(payload["image_urls"]) == 2
            assert payload["image_urls"][0].startswith("data:image/png;base64,")
            return httpx.Response(202, json={"result": "opaque-task-id"})
        if request.url.host == "assets.meshy.ai":
            assert "authorization" not in request.headers
            return httpx.Response(200, content=dummy_glb())
        state = "IN_PROGRESS" if len(calls) == 2 else "SUCCEEDED"
        return httpx.Response(
            200,
            json={
                "status": state,
                "progress": 50,
                "model_urls": {"glb": "https://assets.meshy.ai/output/model.glb"},
            },
        )

    provider = adapter(monkeypatch, handler)
    submitted, progress = Mock(), Mock()
    provider.submitted, provider.progress = submitted, progress
    result = provider.generate(["front", "left"])
    assert result.glb == dummy_glb()
    assert result.metadata["provider_task_id"] == "opaque-task-id"
    assert result.metadata["fidelity_evaluated"] is False
    assert sum(request.method == "POST" for request in calls) == 1
    submitted.assert_called_once_with("opaque-task-id")
    assert progress.call_count == 2


@pytest.mark.parametrize(
    "url",
    [
        "http://assets.meshy.ai/model.glb",
        "https://127.0.0.1/model.glb",
        "https://assets.meshy.ai.evil.example/model.glb",
        "https://x@assets.meshy.ai/model.glb",
    ],
)
def test_meshy_rejects_untrusted_download_urls(monkeypatch, url):
    def handler(request):
        if request.method == "POST":
            return httpx.Response(202, json={"result": "task"})
        return httpx.Response(200, json={"status": "SUCCEEDED", "model_urls": {"glb": url}})

    with pytest.raises(ProviderError, match="UNSAFE_PROVIDER_ASSET"):
        adapter(monkeypatch, handler).generate(["front", "side"])


@pytest.mark.parametrize(
    "status,models,error",
    [
        ("FAILED", {}, "PROVIDER_GENERATION_FAILED"),
        ("SUCCEEDED", {}, "MISSING_PROVIDER_GLB"),
        ("SURPRISE", {}, "INVALID_PROVIDER_RESPONSE"),
    ],
)
def test_meshy_handles_failed_or_incomplete_provider_output(monkeypatch, status, models, error):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "result": "task",
                "status": status,
                "model_urls": models,
            },
        )

    with pytest.raises(ProviderError, match=error):
        adapter(monkeypatch, handler).generate(["front", "side"])


def test_meshy_does_not_retry_an_ambiguous_submission(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("simulated private provider response")

    with pytest.raises(ProviderError, match="PROVIDER_REQUEST_FAILED"):
        adapter(monkeypatch, handler).generate(["front", "side"])
    assert len(calls) == 1


def test_meshy_reconciles_known_task_without_resubmission(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.host == "assets.meshy.ai":
            return httpx.Response(200, content=dummy_glb())
        return httpx.Response(
            200,
            json={
                "status": "SUCCEEDED",
                "progress": 100,
                "model_urls": {"glb": "https://assets.meshy.ai/output/model.glb"},
            },
        )

    result = adapter(monkeypatch, handler).generate(
        ["front", "left"], existing_task_id="known-task"
    )
    assert result.glb == dummy_glb()
    assert all(request.method == "GET" for request in calls)
    assert result.metadata["request_count"] == 0


def test_meshy_bounds_polling_and_rejects_redirects(monkeypatch):
    def pending(request):
        return httpx.Response(200, json={"result": "task", "status": "PENDING"})

    provider = adapter(monkeypatch, pending)
    monkeypatch.setattr(get_settings(), "meshy_timeout_seconds", 1)
    with pytest.raises(ProviderError, match="PROVIDER_TIMEOUT"):
        provider.generate(["front", "side"])
    redirect = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})
        )
    )
    with pytest.raises(ProviderError, match="PROVIDER_DOWNLOAD_FAILED"):
        MeshyProvider._download(redirect, "https://assets.meshy.ai/output/model.glb")


def test_provider_glb_validation_refuses_truncation_and_invalid_content():
    validate_glb(dummy_glb())
    for data in [b"glTF", dummy_glb()[:-1], b"<html>not a model</html>"]:
        with pytest.raises(ProviderError, match="INVALID_GLB"):
            validate_glb(data)


def test_real_adapter_worker_boundary_and_global_request_cap(client, owner, monkeypatch):
    from test_workflow import create

    from app.modules.generation.tasks import process_job

    products = [create(client, owner), create(client, owner)]
    provider = adapter(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            content=dummy_glb() if request.url.host == "assets.meshy.ai" else None,
            json=None
            if request.url.host == "assets.meshy.ai"
            else {
                "result": "simulated-task",
                "status": "SUCCEEDED",
                "model_urls": {"glb": "https://assets.meshy.ai/model.glb"},
            },
        ),
    )
    provider.storage = get_storage()
    monkeypatch.setattr(get_settings(), "queue_mode", "rq")
    headers = {**owner, "Idempotency-Key": "simulated-hosted-task"}
    path = f"/api/v1/products/{products[0]['id']}/generation-jobs"
    with patch("app.modules.generation.routes.queue", return_value=Mock()):
        response = client.post(path, headers=headers)
        assert response.status_code == 202
        assert client.post(path, headers=headers).json()["id"] == response.json()["id"]
        assert (
            client.post(
                f"/api/v1/products/{products[1]['id']}/generation-jobs", headers=headers
            ).status_code
            == 429
        )
    # Simulate execution by a separate worker without needing Redis for this unit test.
    with patch("app.modules.generation.tasks.MeshyProvider", return_value=provider):
        process_job(response.json()["id"])
    job = client.get(f"/api/v1/generation-jobs/{response.json()['id']}", headers=owner).json()
    assert job["status"] == "succeeded"
    assert "not a scan" in job["disclosure"]
    assert client.get(job["model_asset_url"]).content == dummy_glb()
    assert (
        client.get(f"/api/v1/products/{products[0]['id']}/quality", headers=owner).json()["status"]
        == "not_evaluated"
    )
    assert client.get(f"/api/v1/store/products/{products[0]['id']}").status_code == 404
