"""
Pluggable AI image-generation providers.

Swap providers by changing AI_PROVIDER in the environment - the rest of the
app only depends on the ImageGenerationProvider interface below, so adding a
new provider (e.g. Midjourney via a third-party API, a local Stable Diffusion
server, etc.) means writing one new class here.
"""
import base64
import logging
from abc import ABC, abstractmethod

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import ImageGenerationError, UnsupportedProviderError

logger = logging.getLogger(__name__)


class ImageGenerationProvider(ABC):
    @abstractmethod
    async def generate_image(self, prompt: str) -> bytes:
        """Return raw PNG/JPEG bytes for the generated image."""
        raise NotImplementedError


class OpenAIImageProvider(ImageGenerationProvider):
    _ENDPOINT = "https://api.openai.com/v1/images/generations"

    def __init__(self, settings: Settings):
        if not settings.OPENAI_API_KEY:
            raise ImageGenerationError("OPENAI_API_KEY is not configured.")
        self._api_key = settings.OPENAI_API_KEY
        self._model = settings.OPENAI_IMAGE_MODEL
        self._size = settings.OPENAI_IMAGE_SIZE
        self._timeout = settings.REQUEST_TIMEOUT_SECONDS

    async def generate_image(self, prompt: str) -> bytes:
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        payload = {"model": self._model, "prompt": prompt, "size": self._size, "n": 1}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(self._ENDPOINT, headers=headers, json=payload)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error("OpenAI image generation failed: %s", exc.response.text)
                raise ImageGenerationError(f"OpenAI image generation failed: {exc.response.text}") from exc
            except httpx.TransportError as exc:
                logger.error("Could not reach OpenAI: %s", exc)
                raise ImageGenerationError(f"Could not reach OpenAI: {exc}") from exc

        data = response.json()["data"][0]
        if "b64_json" in data:
            return base64.b64decode(data["b64_json"])
        if "url" in data:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                image_response = await client.get(data["url"])
                image_response.raise_for_status()
                return image_response.content
        raise ImageGenerationError("OpenAI response did not include image data.")


class StabilityImageProvider(ImageGenerationProvider):
    _ENDPOINT_TEMPLATE = "https://api.stability.ai/v1/generation/{model}/text-to-image"

    def __init__(self, settings: Settings):
        if not settings.STABILITY_API_KEY:
            raise ImageGenerationError("STABILITY_API_KEY is not configured.")
        self._api_key = settings.STABILITY_API_KEY
        self._model = settings.STABILITY_MODEL
        self._timeout = settings.REQUEST_TIMEOUT_SECONDS

    async def generate_image(self, prompt: str) -> bytes:
        url = self._ENDPOINT_TEMPLATE.format(model=self._model)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {"text_prompts": [{"text": prompt}], "samples": 1}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error("Stability image generation failed: %s", exc.response.text)
                raise ImageGenerationError(f"Stability image generation failed: {exc.response.text}") from exc
            except httpx.TransportError as exc:
                logger.error("Could not reach Stability AI: %s", exc)
                raise ImageGenerationError(f"Could not reach Stability AI: {exc}") from exc

        artifact = response.json()["artifacts"][0]
        return base64.b64decode(artifact["base64"])


def get_image_provider(settings: Settings | None = None) -> ImageGenerationProvider:
    settings = settings or get_settings()
    if settings.AI_PROVIDER == "openai":
        return OpenAIImageProvider(settings)
    if settings.AI_PROVIDER == "stability":
        return StabilityImageProvider(settings)
    raise UnsupportedProviderError(f"Unknown AI_PROVIDER: {settings.AI_PROVIDER}")
