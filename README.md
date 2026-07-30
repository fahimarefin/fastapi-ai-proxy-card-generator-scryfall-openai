# AI MTG Proxy Card Generator

FastAPI service that recreates Magic: The Gathering-style cards using AI-generated
artwork, with card data (name, mana cost, rules text) pulled live from
[Scryfall](https://scryfall.com). Built as a demo/proof-of-concept to validate
the AI generation approach before the full platform build.

## How it works

1. You give it a card (Scryfall URL, or set+number, or a fuzzy name).
2. It fetches the ground-truth card data from the Scryfall API.
3. It generates artwork via a pluggable AI image provider (OpenAI by default).
4. Depending on the mode:
   - **`hybrid`** (default, recommended) — the AI generates only the artwork;
     the name, mana cost, type line, and rules text are composited on top
     programmatically using the real Scryfall data. Text is always 100%
     accurate.
   - **`full_ai`** — a single prompt asks the AI to generate the entire card,
     frame and text included, like the reference site. Closer to that
     look-and-feel, but text accuracy depends entirely on the model and will
     occasionally drift — useful to demo side-by-side so the client can see
     the tradeoff for themselves.

## Project structure

```
mtg-proxy-generator/
├── app/
│   ├── main.py                    # FastAPI app, routes, static file mount
│   ├── core/
│   │   ├── config.py               # env-based settings
│   │   ├── exceptions.py           # typed app errors -> HTTP status codes
│   │   └── logging.py
│   ├── api/v1/
│   │   ├── router.py
│   │   └── endpoints/
│   │       ├── cards.py            # /generate, /generate-batch, /demo/client-cards
│   │       └── health.py
│   ├── models/schemas.py           # Pydantic request/response models
│   ├── services/
│   │   ├── scryfall_service.py     # Scryfall API client
│   │   ├── ai_image_service.py     # OpenAI / Stability provider abstraction
│   │   ├── card_renderer.py        # Pillow-based hybrid-mode compositor
│   │   └── card_generator.py       # orchestrates the full pipeline
│   └── utils/prompt_builder.py     # builds prompts from card data
├── demo/generate_demo_cards.py     # CLI script -> generates the client's 5 cards
├── tests/                          # pytest unit tests (no network required)
├── assets/fonts/                   # drop a .ttf here for nicer hybrid-mode text
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Quick start (Docker)

```bash
cp .env.example .env
# edit .env and set OPENAI_API_KEY=sk-...

docker compose up --build
```

The API is now live at `http://localhost:8000`. Interactive docs: `http://localhost:8000/docs`.

## Generating the 5 client demo cards

These are the exact cards the client asked us to recreate:

- https://scryfall.com/card/tfdn/18/goblin
- https://scryfall.com/card/m10/163/warp-world
- https://scryfall.com/card/war/270/jace-arcane-strategist
- https://scryfall.com/card/dsc/28/spiked-corridor-torture-pit
- https://scryfall.com/card/shm/28/advice-from-the-fae

**Option A — one API call:**

```bash
curl -X POST "http://localhost:8000/api/v1/cards/demo/client-cards?mode=hybrid"
```

**Option B — CLI script (nicer output):**

```bash
pip install httpx
python demo/generate_demo_cards.py --mode hybrid
python demo/generate_demo_cards.py --mode full_ai   # for side-by-side comparison
```

Generated images are saved to `./outputs/` and served at
`http://localhost:8000/outputs/<filename>.png` — you can drop those links
straight into the Fiverr chat.

## Generating a single custom card

```bash
curl -X POST http://localhost:8000/api/v1/cards/generate \
  -H "Content-Type: application/json" \
  -d '{
        "identifier": {"scryfall_url": "https://scryfall.com/card/war/270/jace-arcane-strategist"},
        "mode": "hybrid",
        "style_prompt": "Jerry Smith from Rick and Morty as the character"
      }'
```

## Running locally without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # add your API key
uvicorn app.main:app --reload
```

## Running tests

```bash
pytest
```

Tests cover URL parsing and prompt construction and don't require network
access or API keys.

## Configuration reference

See `.env.example` for all variables. Key ones:

| Variable | Purpose |
|---|---|
| `AI_PROVIDER` | `openai` or `stability` |
| `OPENAI_API_KEY` / `STABILITY_API_KEY` | credentials for the chosen provider |
| `DEFAULT_GENERATION_MODE` | `hybrid` or `full_ai` |
| `OUTPUT_DIR` | where generated PNGs are written |

## Notes / things to flag to the client

- **Text accuracy**: `full_ai` mode text will not be 100% reliable — this is
  a known limitation of current image models, not a bug. `hybrid` mode solves
  this by compositing real text over AI art, which is what we recommended
  in the proposal.
- **Card frame / trade dress**: the hybrid renderer currently draws a
  generic, simplified card frame rather than a pixel-perfect copy of the
  official Magic: The Gathering frame, to keep this demo clear of Wizards of
  the Coast's trade dress/trademark. Worth a quick conversation with the
  client about how close they want the final frame styling to get.
- **Cost control**: each generation call = one AI image request. For the
  full platform, add per-user rate limiting/credits before opening this up
  publicly (already flagged to the client in the running-cost discussion).
