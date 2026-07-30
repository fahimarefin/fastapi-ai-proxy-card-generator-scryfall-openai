from app.models.schemas import ScryfallCardData
from app.utils.prompt_builder import build_artwork_prompt, build_full_card_prompt, build_prompt

CARD = ScryfallCardData(
    scryfall_id="abc123",
    name="Jace, Arcane Strategist",
    mana_cost="{2}{U}",
    type_line="Legendary Planeswalker — Jace",
    oracle_text="Whenever you draw your second card each turn, put a loyalty counter on Jace.",
    loyalty="5",
)


def test_build_artwork_prompt_excludes_text_rendering_instructions():
    prompt = build_artwork_prompt(CARD)
    assert "Jace" in prompt
    assert "no text or borders" in prompt


def test_build_full_card_prompt_includes_rules_text():
    prompt = build_full_card_prompt(CARD)
    assert "Whenever you draw your second card" in prompt
    assert "{2}{U}" in prompt
    assert "Starting loyalty 5" in prompt


def test_build_prompt_dispatches_by_mode():
    assert build_prompt(CARD, mode="hybrid") == build_artwork_prompt(CARD)
    assert build_prompt(CARD, mode="full_ai") == build_full_card_prompt(CARD)


def test_style_prompt_is_appended():
    prompt = build_artwork_prompt(CARD, style_prompt="Jerry from Rick and Morty")
    assert "Jerry from Rick and Morty" in prompt
