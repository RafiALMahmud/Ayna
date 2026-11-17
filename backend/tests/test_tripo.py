"""Tripo tests simulate HTTP only; they never create a paid provider task."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from app.common.config import Settings, get_settings
from app.modules.generation.meshy import ProviderError
from app.modules.generation.providers import dummy_glb
from app.modules.generation.tripo import (
    FILES_API,
    GENERATE_API,
    TripoProvider,
    select_tripo_views,
)


def adapter(monkeypatch, handler):
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_provider", "tripo")
    monkeypatch.setattr(settings, "tripo_api_key", "not-a-real-test-key")
    monkeypatch.setattr(settings, "tripo_daily_request_limit", 1)
    storage = Mock()
    storage.get.return_value = b"sanitized PNG fixture"
    return TripoProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        storage=storage,
        sleep=lambda _: None,
    )


def test_tripo_configuration_requires_key_cap_and_rq():
    for kwargs in [
        {},
        {"tripo_api_key": "test"},
        {"tripo_api_key": "test", "tripo_daily_request_limit": 1, "queue_mode": "inline"},
    ]:
        with pytest.raises(ValueError):
            Settings(ai_provider="tripo", **kwargs)


def test_tripo_requires_front_and_a_second_named_view():
    images = [
        SimpleNamespace(storage_key="a", sort_order=0, view_tag="front"),
        SimpleNamespace(storage_key="b", sort_order=1, view_tag="unspecified"),
    ]
    with pytest.raises(ProviderError, match="TRIPO_REQUIRES_FRONT_AND_NAMED_VIEW"):
        select_tripo_views(images)
    images[1].view_tag = "right"
    assert select_tripo_views(images) == [("front", "a"), ("right", "b")]


def test_tripo_uploads_named_views_submits_once_polls_and_downloads(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if str(request.url) == FILES_API:
            assert request.headers["authorization"] == "Bearer not-a-real-test-key"
            return httpx.Response(
                200,
                json={"code": 0, "data": {"file_token": f"file-{len(calls)}"}},
            )
        if str(request.url) == GENERATE_API:
            payload = json.loads(request.content)
            assert payload["inputs"] == [{"front": "file-1"}, {"right": "file-2"}]
            assert payload["model"] == "v3.1-20260211"
            assert payload["face_limit"] == 50_000
            return httpx.Response(200, json={"code": 0, "data": {"task_id": "task-1"}})
        if request.url.host == "cdn.tripo3d.ai":
            assert "authorization" not in request.headers
            return httpx.Response(200, content=dummy_glb())
        state = "running" if sum(request.method == "GET" for request in calls) == 1 else "success"
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "status": state,
                    "progress": 50,
                    "credits_consumed": 20,
                    "output": {"model_url": "https://cdn.tripo3d.ai/output/model.glb"},
                },
            },
        )

    provider = adapter(monkeypatch, handler)
    submitted = Mock()
    provider.submitted = submitted
    result = provider.generate([("front", "front-key"), ("right", "right-key")])
    assert result.glb == dummy_glb()
    assert result.metadata["provider_task_id"] == "task-1"
    assert result.metadata["credits_consumed"] == 20
    assert result.metadata["fidelity_evaluated"] is False
    assert sum(request.method == "POST" for request in calls) == 3
    submitted.assert_called_once_with("task-1")


def test_tripo_reconciles_known_task_without_upload_or_new_submission(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.host == "cdn.tripo3d.ai":
            return httpx.Response(200, content=dummy_glb())
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "status": "success",
                    "progress": 100,
                    "output": {"model_url": "https://cdn.tripo3d.ai/output/model.glb"},
                },
            },
        )

    result = adapter(monkeypatch, handler).generate([], existing_task_id="known-task")
    assert result.glb == dummy_glb()
    assert all(request.method == "GET" for request in calls)
    assert result.metadata["request_count"] == 0


@pytest.mark.parametrize(
    "url",
    [
        "http://cdn.tripo3d.ai/model.glb",
        "https://127.0.0.1/model.glb",
        "https://cdn.tripo3d.ai.evil.example/model.glb",
        "https://x@cdn.tripo3d.ai/model.glb",
    ],
)
def test_tripo_rejects_unsafe_output_urls(monkeypatch, url):
    def handler(request):
        if str(request.url) == FILES_API:
            return httpx.Response(200, json={"code": 0, "data": {"file_token": "file"}})
        if str(request.url) == GENERATE_API:
            return httpx.Response(200, json={"code": 0, "data": {"task_id": "task"}})
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {"status": "success", "output": {"model_url": url}},
            },
        )

    with pytest.raises(ProviderError, match="UNSAFE_PROVIDER_ASSET"):
        adapter(monkeypatch, handler).generate([("front", "a"), ("left", "b")])


def test_tripo_does_not_retry_ambiguous_submission(monkeypatch):
    submissions = 0

    def handler(request):
        nonlocal submissions
        if str(request.url) == FILES_API:
            return httpx.Response(200, json={"code": 0, "data": {"file_token": "file"}})
        submissions += 1
        raise httpx.ReadTimeout("simulated ambiguous provider submission")

    with pytest.raises(ProviderError, match="PROVIDER_REQUEST_FAILED"):
        adapter(monkeypatch, handler).generate([("front", "a"), ("left", "b")])
    assert submissions == 1
