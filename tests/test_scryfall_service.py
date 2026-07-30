import pytest

from app.core.exceptions import InvalidCardIdentifierError
from app.services.scryfall_service import parse_scryfall_url


@pytest.mark.parametrize(
    "url, expected_set, expected_number",
    [
        ("https://scryfall.com/card/tfdn/18/goblin", "tfdn", "18"),
        ("https://scryfall.com/card/m10/163/warp-world", "m10", "163"),
        ("https://scryfall.com/card/war/270/jace-arcane-strategist", "war", "270"),
        ("https://scryfall.com/card/dsc/28/spiked-corridor-torture-pit", "dsc", "28"),
        ("https://scryfall.com/card/shm/28/advice-from-the-fae", "shm", "28"),
    ],
)
def test_parse_scryfall_url_valid(url, expected_set, expected_number):
    set_code, number = parse_scryfall_url(url)
    assert set_code == expected_set
    assert number == expected_number


def test_parse_scryfall_url_invalid():
    with pytest.raises(InvalidCardIdentifierError):
        parse_scryfall_url("https://example.com/not-a-scryfall-url")
