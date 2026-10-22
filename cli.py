#!/usr/bin/env python3
"""
CLI entrypoint for Gemini Web UI Automation (Python / Playwright).

Usage:
  python cli.py --prompt "un chat mignon style 3d" --out "./output.png"
  python cli.py --image "./input.png" --out "./output.png"
  python cli.py --image "./input.png" --prompt "transforme en style anime" --out "./output.png"
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def run_cli(args):
    from app.browser_manager import browser_manager
    from app.config import settings
    from app.gemini_automation import ask_gemini, ensure_gemini_ready
    prompt = args.prompt
    image = args.image
    output_path = Path(args.out)

    if not prompt and not image:
        print("Error: Please provide at least --prompt, --image, or both.", file=sys.stderr)
        sys.exit(1)

    files = [str(Path(image).resolve())] if image else None

    # Configure headless
    if args.headless is not None:
        settings.headless = args.headless

    print("=" * 60)
    print("Gemini Web Automation CLI")
    print("=" * 60)
    if prompt:
        print(f"[+] Prompt: {prompt}")
    if image:
        print(f"[+] Image input: {image}")
    print(f"[+] Output target: {output_path}")
    print()

    try:
        await browser_manager.start()
        page = await browser_manager.get_page()

        print("[+] Connecting to Gemini session...")
        await ensure_gemini_ready(page)

        print("[+] Processing request (Case 1, 2, or 3)...")
        response_text, model_used, fallback, image_bytes = await ask_gemini(
            page=page,
            prompt=prompt or "",
            model=args.model or settings.default_model,
            fallback_to_flash=settings.fallback_to_flash,
            files=files,
            output_image_path=str(output_path)
        )

        if image_bytes:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)
            print(f"[✓] Image successfully generated & saved to: {output_path.resolve()}")
        elif response_text:
            print("[✓] Gemini response:")
            print("-" * 50)
            print(response_text)
            print("-" * 50)

    except Exception as e:
        print(f"[x] Error during execution: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await browser_manager.stop()


def main():
    parser = argparse.ArgumentParser(description="Gemini Web Automation CLI (Playwright)")
    parser.add_argument("--prompt", "-p", type=str, default=None, help="Text prompt")
    parser.add_argument("--image", "-i", type=str, default=None, help="Input image file path")
    parser.add_argument("--out", "-o", type=str, default="./output.png", help="Output file path (default: ./output.png)")
    parser.add_argument("--model", "-m", type=str, default="gemini-2.5-flash", help="Model name")
    parser.add_argument("--headful", action="store_false", dest="headless", default=None, help="Run browser visibly")
    parser.add_argument("--headless", action="store_true", dest="headless", default=None, help="Run browser headlessly")

    args = parser.parse_args()
    asyncio.run(run_cli(args))


if __name__ == "__main__":
    main()
