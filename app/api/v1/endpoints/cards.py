import logging

from fastapi import APIRouter, HTTPException

from app.core.exceptions import AppError
from app.models.schemas import (
    BatchGenerateRequest,
    BatchGenerateResponse,
    CardIdentifier,
    GenerateCardRequest,
    GenerateCardResponse,
)
from app.services.card_generator import CardGeneratorService

logger = logging.getLogger(__name__)
router = APIRouter()

# The 5 example cards the client (harry49328) sent as the quality bar for
# the demo. Kept here so the demo endpoint/script always matches exactly
# what he asked to see recreated.
CLIENT_DEMO_CARD_URLS = [
    "https://scryfall.com/card/tfdn/18/goblin",
    "https://scryfall.com/card/m10/163/warp-world",
    "https://scryfall.com/card/war/270/jace-arcane-strategist",
    "https://scryfall.com/card/dsc/28/spiked-corridor-torture-pit",
    "https://scryfall.com/card/shm/28/advice-from-the-fae",
]


def _service() -> CardGeneratorService:
    # Constructed per-request (cheap: just wires up config + httpx clients
    # lazily) so a bad provider API key doesn't crash the whole app at import time.
    return CardGeneratorService()


@router.post("/generate", response_model=GenerateCardResponse, tags=["cards"])
async def generate_card(request: GenerateCardRequest):
    try:
        return await _service().generate(
            identifier=request.identifier,
            mode=request.mode,
            style_prompt=request.style_prompt,
        )
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/generate-batch", response_model=BatchGenerateResponse, tags=["cards"])
async def generate_batch(request: BatchGenerateRequest):
    service = _service()
    results: list[GenerateCardResponse] = []

    for identifier in request.cards:
        try:
            result = await service.generate(
                identifier=identifier,
                mode=request.mode,
                style_prompt=request.style_prompt,
            )
            results.append(result)
        except AppError as exc:
            logger.warning("Generation failed for %s: %s", identifier, exc.message)
            results.append(
                GenerateCardResponse(
                    success=False,
                    card_name=identifier.name or identifier.scryfall_url or "unknown",
                    mode_used=request.mode,
                    source_card=_empty_card(),
                    prompt_used="",
                    image_path="",
                    image_url="",
                    generation_time_ms=0,
                    error=exc.message,
                )
            )

    succeeded = sum(1 for r in results if r.success)
    return BatchGenerateResponse(
        total=len(results),
        succeeded=succeeded,
        failed=len(results) - succeeded,
        results=results,
    )


@router.post("/demo/client-cards", response_model=BatchGenerateResponse, tags=["demo"])
async def generate_client_demo_cards(mode: str = "hybrid", style_prompt: str | None = None):
    """
    Convenience endpoint: generates the exact 5 cards the client sent as the
    quality benchmark, in one call. Equivalent to POST /generate-batch with
    CLIENT_DEMO_CARD_URLS.
    """
    request = BatchGenerateRequest(
        cards=[CardIdentifier(scryfall_url=url) for url in CLIENT_DEMO_CARD_URLS],
        mode=mode,  # type: ignore[arg-type]
        style_prompt=style_prompt,
    )
    return await generate_batch(request)


def _empty_card():
    from app.models.schemas import ScryfallCardData

    return ScryfallCardData(scryfall_id="", name="unknown")
