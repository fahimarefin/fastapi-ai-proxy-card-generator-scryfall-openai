import logging
import re
import time
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.models.schemas import CardIdentifier, GenerateCardResponse, ScryfallCardData
from app.services.ai_image_service import get_image_provider
from app.services.card_renderer import render_hybrid_card
from app.services.scryfall_service import ScryfallService
from app.utils.prompt_builder import build_prompt

logger = logging.getLogger(__name__)

_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9\-_]+")


def _safe_filename(name: str) -> str:
    return _SAFE_NAME_RE.sub("-", name).strip("-").lower()


class CardGeneratorService:
    def __init__(self):
        self._settings = get_settings()
        self._scryfall = ScryfallService()
        self._image_provider = get_image_provider(self._settings)
        self._output_dir = Path(self._settings.OUTPUT_DIR)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    async def generate(
        self,
        identifier: CardIdentifier,
        mode: str = "hybrid",
        style_prompt: str | None = None,
    ) -> GenerateCardResponse:
        start = time.perf_counter()

        card: ScryfallCardData = await self._scryfall.get_card(identifier)
        prompt = build_prompt(card, mode=mode, style_prompt=style_prompt)

        logger.info("Generating '%s' in %s mode. Prompt: %s", card.name, mode, prompt)
        raw_image_bytes = await self._image_provider.generate_image(prompt)

        if mode == "hybrid":
            final_image_bytes = render_hybrid_card(card, raw_image_bytes)
        else:
            final_image_bytes = raw_image_bytes

        filename = f"{_safe_filename(card.name)}-{mode}-{uuid.uuid4().hex[:8]}.png"
        output_path = self._output_dir / filename
        output_path.write_bytes(final_image_bytes)

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return GenerateCardResponse(
            success=True,
            card_name=card.name,
            mode_used=mode,
            source_card=card,
            prompt_used=prompt,
            image_path=str(output_path),
            image_url=f"/outputs/{filename}",
            generation_time_ms=elapsed_ms,
        )
