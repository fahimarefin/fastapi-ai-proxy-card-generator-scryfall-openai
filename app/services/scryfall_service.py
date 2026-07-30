"""
Fetches accurate, ground-truth card data (name, mana cost, oracle text, etc.)
from the Scryfall API. This is what keeps the generated proxy cards factually
correct, regardless of which AI image model is used for the artwork.
"""
import logging
import re
from typing import Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.exceptions import CardNotFoundError, InvalidCardIdentifierError
from app.models.schemas import CardIdentifier, ScryfallCardData

logger = logging.getLogger(__name__)

# Matches URLs like:
# https://scryfall.com/card/war/270/jace-arcane-strategist
# https://scryfall.com/card/tfdn/18/goblin
_SCRYFALL_URL_RE = re.compile(
    r"scryfall\.com/card/(?P<set>[a-zA-Z0-9]+)/(?P<number>[a-zA-Z0-9\-\u2605]+)"
)


def parse_scryfall_url(url: str) -> tuple[str, str]:
    """Extract (set_code, collector_number) from a scryfall.com/card/... URL."""
    match = _SCRYFALL_URL_RE.search(url)
    if not match:
        raise InvalidCardIdentifierError(f"Could not parse a Scryfall set/number from URL: {url}")
    return match.group("set").lower(), match.group("number")


def _normalize(raw: dict) -> ScryfallCardData:
    image_uris = raw.get("image_uris") or {}
    # Double-faced cards store images per-face instead of top-level.
    if not image_uris and raw.get("card_faces"):
        image_uris = raw["card_faces"][0].get("image_uris", {})

    return ScryfallCardData(
        scryfall_id=raw["id"],
        name=raw.get("name", ""),
        mana_cost=raw.get("mana_cost", "") or (raw.get("card_faces", [{}])[0].get("mana_cost", "") if raw.get("card_faces") else ""),
        cmc=raw.get("cmc", 0),
        type_line=raw.get("type_line", ""),
        oracle_text=raw.get("oracle_text", "") or (raw.get("card_faces", [{}])[0].get("oracle_text", "") if raw.get("card_faces") else ""),
        flavor_text=raw.get("flavor_text"),
        power=raw.get("power"),
        toughness=raw.get("toughness"),
        loyalty=raw.get("loyalty"),
        colors=raw.get("colors", []),
        rarity=raw.get("rarity", ""),
        set_code=raw.get("set", ""),
        collector_number=raw.get("collector_number", ""),
        original_image_url=image_uris.get("normal") or image_uris.get("large"),
        scryfall_permalink=raw.get("scryfall_uri"),
    )


class ScryfallService:
    def __init__(self):
        settings = get_settings()
        self._base_url = settings.SCRYFALL_API_BASE
        self._headers = {
            "User-Agent": settings.SCRYFALL_USER_AGENT,
            "Accept": "application/json",
        }
        self._timeout = settings.REQUEST_TIMEOUT_SECONDS

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type(httpx.TransportError),
    )
    async def _get(self, path: str, params: Optional[dict] = None) -> dict:
        async with httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=self._timeout) as client:
            response = await client.get(path, params=params)
            if response.status_code == 404:
                raise CardNotFoundError(f"No Scryfall card found for {path} {params or ''}")
            response.raise_for_status()
            return response.json()

    async def get_by_set_and_number(self, set_code: str, collector_number: str) -> ScryfallCardData:
        raw = await self._get(f"/cards/{set_code.lower()}/{collector_number}")
        return _normalize(raw)

    async def get_by_name(self, name: str) -> ScryfallCardData:
        raw = await self._get("/cards/named", params={"fuzzy": name})
        return _normalize(raw)

    async def get_card(self, identifier: CardIdentifier) -> ScryfallCardData:
        if identifier.scryfall_url:
            set_code, number = parse_scryfall_url(identifier.scryfall_url)
            return await self.get_by_set_and_number(set_code, number)
        if identifier.set and identifier.collector_number:
            return await self.get_by_set_and_number(identifier.set, identifier.collector_number)
        if identifier.name:
            return await self.get_by_name(identifier.name)
        raise InvalidCardIdentifierError("No usable identifier fields were provided.")
