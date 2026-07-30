from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

GenerationMode = Literal["hybrid", "full_ai"]


class CardIdentifier(BaseModel):
    """
    A card can be identified in any ONE of these ways:
      - a full Scryfall card URL, e.g. https://scryfall.com/card/war/270/jace-arcane-strategist
      - a set code + collector number, e.g. set="war", collector_number="270"
      - a fuzzy card name, e.g. name="Jace, Arcane Strategist"
    """

    scryfall_url: Optional[str] = Field(default=None, examples=["https://scryfall.com/card/war/270/jace-arcane-strategist"])
    set: Optional[str] = Field(default=None, description="Scryfall set code, e.g. 'war'")
    collector_number: Optional[str] = Field(default=None, description="Collector number within the set, e.g. '270'")
    name: Optional[str] = Field(default=None, description="Card name for fuzzy search")

    @model_validator(mode="after")
    def _ensure_one_identifier(self):
        has_url = bool(self.scryfall_url)
        has_set_and_number = bool(self.set and self.collector_number)
        has_name = bool(self.name)
        if not (has_url or has_set_and_number or has_name):
            raise ValueError(
                "Provide one of: scryfall_url, (set + collector_number), or name"
            )
        return self


class ScryfallCardData(BaseModel):
    """Normalized subset of the Scryfall card object that we actually use."""

    scryfall_id: str
    name: str
    mana_cost: str = ""
    cmc: float = 0
    type_line: str = ""
    oracle_text: str = ""
    flavor_text: Optional[str] = None
    power: Optional[str] = None
    toughness: Optional[str] = None
    loyalty: Optional[str] = None
    colors: List[str] = Field(default_factory=list)
    rarity: str = ""
    set_code: str = ""
    collector_number: str = ""
    original_image_url: Optional[str] = None
    scryfall_permalink: Optional[str] = None


class GenerateCardRequest(BaseModel):
    identifier: CardIdentifier
    mode: GenerationMode = "hybrid"
    style_prompt: Optional[str] = Field(
        default=None,
        description="Optional art style override, e.g. 'Jerry from Rick and Morty as the character'",
        examples=["cyberpunk neon style", "Jerry Smith from Rick and Morty as the human warrior"],
    )


class BatchGenerateRequest(BaseModel):
    cards: List[CardIdentifier]
    mode: GenerationMode = "hybrid"
    style_prompt: Optional[str] = None


class GenerateCardResponse(BaseModel):
    success: bool
    card_name: str
    mode_used: GenerationMode
    source_card: ScryfallCardData
    prompt_used: str
    image_path: str
    image_url: str
    generation_time_ms: int
    error: Optional[str] = None


class BatchGenerateResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: List[GenerateCardResponse]
