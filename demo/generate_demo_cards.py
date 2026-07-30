"""
Generates the exact 5 cards the client sent as the quality benchmark:

  https://scryfall.com/card/tfdn/18/goblin
  https://scryfall.com/card/m10/163/warp-world
  https://scryfall.com/card/war/270/jace-arcane-strategist
  https://scryfall.com/card/dsc/28/spiked-corridor-torture-pit
  https://scryfall.com/card/shm/28/advice-from-the-fae

Usage (with the API container already running via docker-compose):

    python demo/generate_demo_cards.py
    python demo/generate_demo_cards.py --mode full_ai
    python demo/generate_demo_cards.py --base-url http://localhost:8000 --mode hybrid

This just calls the running API's batch demo endpoint and prints a summary -
it does not talk to Scryfall/OpenAI directly, so the API container is the
only thing that needs credentials configured.
"""
import argparse
import sys

import httpx


def main():
    parser = argparse.ArgumentParser(description="Generate the client's 5 demo proxy cards.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of the running API")
    parser.add_argument("--mode", choices=["hybrid", "full_ai"], default="hybrid")
    parser.add_argument("--style-prompt", default=None, help="Optional art style override")
    args = parser.parse_args()

    params = {"mode": args.mode}
    if args.style_prompt:
        params["style_prompt"] = args.style_prompt

    url = f"{args.base_url}/api/v1/cards/demo/client-cards"
    print(f"Requesting demo generation ({args.mode} mode) from {url} ...")

    try:
        response = httpx.post(url, params=params, timeout=300)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        sys.exit(1)

    data = response.json()
    print(f"\nDone: {data['succeeded']}/{data['total']} cards generated successfully.\n")

    for result in data["results"]:
        status = "OK" if result["success"] else "FAILED"
        print(f"[{status}] {result['card_name']}")
        if result["success"]:
            print(f"        image: {args.base_url}{result['image_url']}")
            print(f"        time:  {result['generation_time_ms']} ms")
        else:
            print(f"        error: {result['error']}")


if __name__ == "__main__":
    main()
