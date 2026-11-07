"""Explicitly opted-in Meshy multi-image adapter. Never invoked by default or live in CI."""

import base64
import json
import struct
import time
from collections.abc import Callable
from urllib.parse import quote, urlsplit

import httpx

from app.common.config import get_settings
from app.common.storage import Storage, get_storage
from app.modules.generation.providers import GenerationResult

API = "https://api.meshy.ai/openapi/v1/multi-image-to-3d"
MAX_GLB_BYTES = 32 * 1024 * 1024


class ProviderError(RuntimeError):
    """Only controlled error codes cross the provider boundary."""


def validate_glb(data: bytes) -> None:
    if len(data) < 28 or len(data) > MAX_GLB_BYTES:
        raise ProviderError("INVALID_GLB")
    magic, version, length, size, kind = struct.unpack_from("<5I", data)
    if (
        magic != 0x46546C67
        or version != 2
        or length != len(data)
        or kind != 0x4E4F534A
        or size > 4 * 1024 * 1024
        or size % 4
        or 20 + size > length
    ):
        raise ProviderError("INVALID_GLB")
    try:
        document = json.loads(data[20 : 20 + size])
        if document.get("asset", {}).get("version") != "2.0" or not document.get("meshes"):
            raise ValueError("Missing GLB content")
        for resource in document.get("buffers", []) + document.get("images", []):
            # Never let the browser resolve provider-controlled external resources.
            if "uri" in resource:
                raise ValueError("Only embedded GLB resources are accepted")
    except (ValueError, TypeError, AttributeError) as exc:
        raise ProviderError("INVALID_GLB") from exc
    offset = 12
    while offset < length:
        if offset + 8 > length:
            raise ProviderError("INVALID_GLB")
        chunk_size = struct.unpack_from("<I", data, offset)[0]
        offset += 8 + chunk_size
        if chunk_size % 4 or offset > length:
            raise ProviderError("INVALID_GLB")


def select_views(images) -> list:
    """Front first, then distinct seller-labelled directions, then original-order extras."""
    ordered = sorted(images, key=lambda image: image.sort_order)
    front = next((image for image in ordered if image.view_tag == "front"), ordered[0])
    chosen, labels = [front], {front.view_tag}
    for image in ordered:
        if image not in chosen and image.view_tag not in labels | {"unspecified"}:
            chosen.append(image)
            labels.add(image.view_tag)
    chosen.extend(image for image in ordered if image not in chosen)
    return chosen[:4]


class MeshyProvider:
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

    def generate(
        self, image_keys: list[str], *, existing_task_id: str | None = None
    ) -> GenerationResult:
        settings = self.settings
        if (
            settings.ai_provider != "meshy"
            or not settings.meshy_api_key
            or settings.meshy_daily_request_limit < 1
        ):
            raise ProviderError("PROVIDER_NOT_CONFIGURED")
        if existing_task_id is None and not 2 <= len(image_keys) <= 4:
            raise ProviderError("INVALID_PROVIDER_INPUT")
        images = (
            [
                "data:image/png;base64," + base64.b64encode(self.storage.get(key)).decode("ascii")
                for key in image_keys
            ]
            if existing_task_id is None
            else []
        )
        owned = self.client is None
        client = self.client or httpx.Client(timeout=30, follow_redirects=False, trust_env=False)
        headers = {"Authorization": f"Bearer {settings.meshy_api_key}"}
        try:
            task_id = existing_task_id
            if task_id is None:
                # Submission is deliberately never retried: an ambiguous timeout may be billable.
                response = client.post(
                    API,
                    headers=headers,
                    json={
                        "image_urls": images,
                        "ai_model": "meshy-7.1",
                        "target_formats": ["glb"],
                    },
                )
                response.raise_for_status()
                task_id = response.json().get("result")
                if not isinstance(task_id, str) or not task_id or len(task_id) > 200:
                    raise ProviderError("INVALID_PROVIDER_RESPONSE")
                self.submitted(task_id)
            deadline = time.monotonic() + settings.meshy_timeout_seconds
            attempts = settings.meshy_timeout_seconds // settings.meshy_poll_seconds + 1
            for _ in range(attempts):
                if time.monotonic() >= deadline:
                    break
                response = client.get(f"{API}/{quote(task_id, safe='')}", headers=headers)
                response.raise_for_status()
                task = response.json()
                status = task.get("status")
                if status in {"FAILED", "CANCELED", "CANCELLED", "EXPIRED"}:
                    raise ProviderError("PROVIDER_GENERATION_FAILED")
                raw_progress = task.get("progress", 0)
                self.progress(max(15, min(85, int(raw_progress or 0) * 70 // 100 + 15)))
                if status == "SUCCEEDED":
                    url = task.get("model_urls", {}).get("glb")
                    data = self._download(client, url)
                    validate_glb(data)
                    return GenerationResult(
                        data,
                        {
                            "provider": "meshy",
                            "provider_task_id": task_id,
                            "ai_model": "meshy-7.1",
                            "source_image_count": len(image_keys),
                            "request_count": 0 if existing_task_id else 1,
                            "fidelity_evaluated": False,
                        },
                    )
                if status not in {"PENDING", "IN_PROGRESS", "PROCESSING"}:
                    raise ProviderError("INVALID_PROVIDER_RESPONSE")
                self.sleep(settings.meshy_poll_seconds)
            raise ProviderError("PROVIDER_TIMEOUT")
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
            or parsed.hostname != "assets.meshy.ai"
            or parsed.port not in {None, 443}
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise ProviderError("UNSAFE_PROVIDER_ASSET")
        # No API authorization header is sent to storage; redirects are never followed.
        with client.stream("GET", url, follow_redirects=False) as response:
            if response.status_code != 200:
                raise ProviderError("PROVIDER_DOWNLOAD_FAILED")
            data = bytearray()
            for chunk in response.iter_bytes(64 * 1024):
                data.extend(chunk)
                if len(data) > MAX_GLB_BYTES:
                    raise ProviderError("PROVIDER_ASSET_TOO_LARGE")
            return bytes(data)
