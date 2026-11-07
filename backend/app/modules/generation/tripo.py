"""Explicit Tripo v3 multiview adapter; disabled by default and simulated in tests."""

import time
from collections.abc import Callable
from urllib.parse import quote, urlsplit

import httpx

from app.common.config import get_settings
from app.common.storage import Storage, get_storage
from app.modules.generation.meshy import MAX_GLB_BYTES, ProviderError, validate_glb
from app.modules.generation.providers import GenerationResult

BASE_API = "https://openapi.tripo3d.ai/v3"
FILES_API = f"{BASE_API}/files"
GENERATE_API = f"{BASE_API}/generation/multiview-to-model"
VIEW_ORDER = ("front", "left", "back", "right")


def select_tripo_views(images) -> list[tuple[str, str]]:
    """Return Tripo's defensible named views; front plus one other view are mandatory."""
    selected: dict[str, str] = {}
    for image in sorted(images, key=lambda item: item.sort_order):
        if image.view_tag in VIEW_ORDER and image.view_tag not in selected:
            selected[image.view_tag] = image.storage_key
    if "front" not in selected or len(selected) < 2:
        raise ProviderError("TRIPO_REQUIRES_FRONT_AND_NAMED_VIEW")
    return [(view, selected[view]) for view in VIEW_ORDER if view in selected]


class TripoProvider:
    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        storage: Storage | None = None,
        submitted: Callable[[str], None] = lambda _: None,
        progress: Callable[[int], None] = lambda _: None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.settings = get_settings()
        self.client = client
        self.storage = storage or get_storage()
        self.submitted, self.progress, self.sleep = submitted, progress, sleep

    @staticmethod
    def _data(response: httpx.Response) -> dict:
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("code") != 0:
            raise ProviderError("PROVIDER_REQUEST_FAILED")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ProviderError("INVALID_PROVIDER_RESPONSE")
        return data

    def generate(
        self,
        views: list[tuple[str, str]],
        *,
        existing_task_id: str | None = None,
    ) -> GenerationResult:
        settings = self.settings
        if (
            settings.ai_provider != "tripo"
            or not settings.tripo_api_key
            or settings.tripo_daily_request_limit < 1
        ):
            raise ProviderError("PROVIDER_NOT_CONFIGURED")
        if existing_task_id is None:
            labels = [view for view, _ in views]
            if (
                not 2 <= len(views) <= 4
                or "front" not in labels
                or len(labels) != len(set(labels))
                or any(view not in VIEW_ORDER for view in labels)
            ):
                raise ProviderError("INVALID_PROVIDER_INPUT")

        owned = self.client is None
        client = self.client or httpx.Client(timeout=30, follow_redirects=False, trust_env=False)
        headers = {"Authorization": f"Bearer {settings.tripo_api_key}"}
        uploaded = 0
        try:
            task_id = existing_task_id
            if task_id is None:
                inputs = []
                for view, key in views:
                    photo = self.storage.get(key)
                    token = self._data(
                        client.post(
                            FILES_API,
                            headers=headers,
                            files={"file": (f"{view}.png", photo, "image/png")},
                        )
                    ).get("file_token")
                    if not isinstance(token, str) or not token or len(token) > 300:
                        raise ProviderError("INVALID_PROVIDER_RESPONSE")
                    inputs.append({view: token})
                    uploaded += 1
                # Never retry submission: a timeout can represent a billable accepted task.
                data = self._data(
                    client.post(
                        GENERATE_API,
                        headers={**headers, "Content-Type": "application/json"},
                        json={
                            "inputs": inputs,
                            "model": "v3.1-20260211",
                            "texture": True,
                            "pbr": True,
                            "texture_alignment": "original_image",
                            "orientation": "align_image",
                            "face_limit": 50_000,
                            "export_uv": True,
                        },
                    )
                )
                task_id = data.get("task_id")
                if not isinstance(task_id, str) or not task_id or len(task_id) > 300:
                    raise ProviderError("INVALID_PROVIDER_RESPONSE")
                self.submitted(task_id)

            deadline = time.monotonic() + settings.tripo_timeout_seconds
            attempts = settings.tripo_timeout_seconds // settings.tripo_poll_seconds + 1
            for _ in range(attempts):
                if time.monotonic() >= deadline:
                    break
                task = self._data(
                    client.get(f"{BASE_API}/tasks/{quote(task_id, safe='')}", headers=headers)
                )
                status = task.get("status")
                if status in {"failed", "cancelled", "banned", "expired"}:
                    raise ProviderError("PROVIDER_GENERATION_FAILED")
                raw_progress = task.get("progress", 0)
                self.progress(max(15, min(85, int(raw_progress or 0) * 70 // 100 + 15)))
                if status == "success":
                    output = task.get("output")
                    url = output.get("model_url") if isinstance(output, dict) else None
                    model = self._download(client, url)
                    validate_glb(model)
                    credits = task.get("credits_consumed")
                    return GenerationResult(
                        model,
                        {
                            "provider": "tripo",
                            "provider_task_id": task_id,
                            "api_version": "v3",
                            "ai_model": "v3.1-20260211",
                            "source_image_count": len(views),
                            "uploaded_file_count": uploaded,
                            "request_count": 0 if existing_task_id else 1,
                            "credits_consumed": credits
                            if isinstance(credits, (int, float))
                            else None,
                            "fidelity_evaluated": False,
                        },
                    )
                if status not in {"queued", "running", "unknown"}:
                    raise ProviderError("INVALID_PROVIDER_RESPONSE")
                self.sleep(settings.tripo_poll_seconds)
            raise ProviderError("PROVIDER_TIMEOUT")
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
            raise ProviderError("PROVIDER_REQUEST_FAILED") from exc
        finally:
            if owned:
                client.close()

    @staticmethod
    def _download(client: httpx.Client, url) -> bytes:
        if not isinstance(url, str):
            raise ProviderError("MISSING_PROVIDER_GLB")
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "cdn.tripo3d.ai"
            or parsed.port not in {None, 443}
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise ProviderError("UNSAFE_PROVIDER_ASSET")
        with client.stream("GET", url, follow_redirects=False) as response:
            if response.status_code != 200:
                raise ProviderError("PROVIDER_DOWNLOAD_FAILED")
            data = bytearray()
            for chunk in response.iter_bytes(64 * 1024):
                data.extend(chunk)
                if len(data) > MAX_GLB_BYTES:
                    raise ProviderError("PROVIDER_ASSET_TOO_LARGE")
            return bytes(data)
