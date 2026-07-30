"""
Turns Scryfall card data into prompts for the image generation model.

Two builders are provided, matching the two generation modes:
  - build_artwork_prompt: describes ONLY the scene/character for the card's
    art box (used in hybrid mode, where text is composited separately and
    therefore always accurate).
  - build_full_card_prompt: describes the entire card, frame and text
    included (used in full_ai mode). AI text rendering is inherently less
    reliable, which is exactly the tradeoff worth showing the client.
"""
from app.models.schemas import ScryfallCardData


def _style_clause(style_prompt: str | None) -> str:
    if not style_prompt:
        return ""
    return f" Reimagine the subject as: {style_prompt}."


def build_artwork_prompt(card: ScryfallCardData, style_prompt: str | None = None) -> str:
    subject = card.flavor_text or card.oracle_text or card.type_line or card.name
    return (
        f"Fantasy trading-card illustration for a card named '{card.name}', "
        f"a {card.type_line.lower()}. "
        f"Scene/subject inspiration: {subject}. "
        f"Painterly fantasy art style, dramatic lighting, high detail, "
        f"framed as a rectangular card-art illustration with no text or borders in the image."
        f"{_style_clause(style_prompt)}"
    )


def build_full_card_prompt(card: ScryfallCardData, style_prompt: str | None = None) -> str:
    pt_line = f" Power/Toughness {card.power}/{card.toughness}." if card.power and card.toughness else ""
    loyalty_line = f" Starting loyalty {card.loyalty}." if card.loyalty else ""
    return (
        f"A complete trading card game card in the style of Magic: The Gathering, "
        f"full card layout including frame, title bar, mana cost symbols, art box, "
        f"type line, and rules text box. "
        f"Card name: '{card.name}'. Mana cost: '{card.mana_cost}'. "
        f"Type line: '{card.type_line}'. "
        f"Rules text to render exactly: \"{card.oracle_text}\"."
        f"{pt_line}{loyalty_line} "
        f"Clean, legible typography, professional trading-card production quality."
        f"{_style_clause(style_prompt)}"
    )


def build_prompt(card: ScryfallCardData, mode: str, style_prompt: str | None = None) -> str:
    if mode == "full_ai":
        return build_full_card_prompt(card, style_prompt)
    return build_artwork_prompt(card, style_prompt)
