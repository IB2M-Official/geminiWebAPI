"""Core Gemini UI automation logic using Playwright."""

import asyncio
import base64
import logging
import os
import re
from pathlib import Path
from typing import Optional, Tuple, List
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from app.config import settings

logger = logging.getLogger(__name__)


class GeminiAutomationError(Exception):
    """Base exception for Gemini automation errors."""
    pass


class SessionExpiredError(GeminiAutomationError):
    """Raised when Gemini session has expired."""
    pass


class QuotaExceededError(GeminiAutomationError):
    """Raised when Pro quota is exceeded."""
    pass


class UnexpectedUIStateError(GeminiAutomationError):
    """Raised when UI is not in expected state."""
    pass


class AutomationTimeoutError(GeminiAutomationError):
    """Raised when automation times out."""
    pass


# DOM Selectors based on Gemini Web UI
SELECTORS = {
    # Model selection
    "model_pill": '[data-test-id="bard-mode-menu-button"]',
    "desktop_menu": '[data-test-id="desktop-nested-mode-menu"]',
    "mobile_menu": '[data-test-id="mobile-nested-mode-menu"]',
    "model_pro": '[data-test-id="bard-mode-option-2.5pro"]',
    "model_flash": '[data-test-id="bard-mode-option-2.5flash"]',

    # Text input
    "text_editor": 'div.ql-editor.textarea.new-input-ui[aria-label="Enter a prompt here"], div.ql-editor[contenteditable="true"], textarea[aria-label*="prompt" i], div[contenteditable="true"]',

    # File upload
    "upload_button": 'button[aria-label*="Upload" i], button[aria-label*="Importer" i], button[aria-label="Open upload file menu"], button[mattooltip*="Upload" i]',
    "upload_card": '[data-test-id="upload-file-card-container"]',
    "upload_files_button": '[data-test-id="local-images-files-uploader-button"], button[aria-label*="Upload" i]',
    "hidden_file_selector": '.hidden-local-file-image-selector-button[xapfileselectortrigger], input[type="file"]',

    # Send message
    "send_button": 'button[aria-label*="Send" i], button[aria-label*="Envoyer" i], button[data-test-id="send-button"]',

    # Response
    "message_container": 'message-content',
    "response_content": 'model-response-text, .model-response, message-content',
}


# Quota error patterns
QUOTA_ERROR_PATTERNS = [
    r"reached your limit",
    r"usage limit",
    r"Gemini Advanced",
    r"try again later",
    r"upgrade to continue",
    r"temporarily unavailable",
]


def is_quota_error(text: str) -> bool:
    """Check if response text indicates Pro quota exceeded."""
    text_lower = text.lower()
    for pattern in QUOTA_ERROR_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            logger.warning(f"Quota error detected: matched pattern '{pattern}'")
            return True
    return False


async def ensure_gemini_ready(page: Page) -> None:
    """Ensure we're on Gemini chat screen and logged in."""
    logger.info("Ensuring Gemini is ready...")

    try:
        await page.goto(settings.gemini_url, wait_until="domcontentloaded", timeout=settings.page_load_timeout)
    except Exception as e:
        logger.error(f"Failed to navigate to Gemini: {e}")
        raise UnexpectedUIStateError(f"Failed to load Gemini: {e}")

    await asyncio.sleep(1.5)

    current_url = page.url
    if "accounts.google.com" in current_url or "login" in current_url.lower() or "signin" in current_url.lower():
        logger.error("Detected login page - session expired")
        raise SessionExpiredError(
            "Detected Google login page at gemini.google.com; please run 'python login_helper.py' or 'node index.js --login' to authenticate."
        )

    # Check for prompt input area
    try:
        await page.wait_for_selector(SELECTORS["text_editor"], timeout=8000, state="visible")
        logger.info("Gemini chat interface ready")
    except PlaywrightTimeout:
        logger.error("Text editor not found - unexpected UI state")
        raise UnexpectedUIStateError(
            "Text editor not found. Gemini UI may have changed or session may be invalid."
        )


async def select_model(page: Page, model: str) -> None:
    """Select the specified model (Pro or Flash) if the menu exists."""
    logger.info(f"Selecting model: {model}")

    model_selector = (
        SELECTORS["model_pro"]
        if "pro" in model.lower()
        else SELECTORS["model_flash"]
    )

    try:
        pill = page.locator(SELECTORS["model_pill"]).first
        if not await pill.is_visible(timeout=2000):
            logger.info("Model pill selector not found, skipping explicit model switch")
            return

        await pill.click()
        await asyncio.sleep(0.5)

        target = page.locator(model_selector).first
        if await target.is_visible(timeout=2000):
            await target.click()
            logger.info(f"Selected model: {model}")
        await asyncio.sleep(0.5)
    except Exception as e:
        logger.debug(f"Model selection skipped or handled: {e}")


async def upload_files(page: Page, file_paths: List[str]) -> None:
    """
    Upload files to Gemini via file chooser or synthetic paste fallback.
    Supports Case 2 (Image seule) and Case 3 (Image + Prompt).
    """
    logger.info(f"Uploading {len(file_paths)} file(s)...")

    for file_path in file_paths:
        path_obj = Path(file_path).resolve()
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {path_obj}")

        uploaded = False

        # Attempt 1: Hidden file input if directly present
        file_inputs = page.locator('input[type="file"]')
        if await file_inputs.count() > 0:
            try:
                await file_inputs.first.set_input_files(str(path_obj))
                uploaded = True
                logger.info(f"Uploaded via direct file input: {path_obj.name}")
            except Exception as e:
                logger.debug(f"Direct file input upload failed: {e}")

        # Attempt 2: Click upload button to reveal file chooser
        if not uploaded:
            try:
                upload_btn = page.locator(SELECTORS["upload_button"]).first
                if await upload_btn.is_visible(timeout=3000):
                    async with page.expect_file_chooser(timeout=4000) as fc_info:
                        await upload_btn.click()
                    file_chooser = await fc_info.value
                    await file_chooser.set_files(str(path_obj))
                    uploaded = True
                    logger.info(f"Uploaded via file chooser: {path_obj.name}")
            except Exception as e:
                logger.debug(f"File chooser upload failed: {e}")

        # Attempt 3: Clipboard paste injection fallback
        if not uploaded:
            logger.info("Injecting image file via paste event...")
            raw_bytes = path_obj.read_bytes()
            b64_data = base64.b64encode(raw_bytes).decode("utf-8")
            ext = path_obj.suffix.lower()
            mime = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"

            paste_js = """
            async ({ b64, mime, filename }) => {
                const editor = document.querySelector('div.ql-editor, textarea, [contenteditable="true"]');
                if (!editor) return;
                editor.focus();
                const binary = atob(b64);
                const bytes = new Uint8Array(binary.length);
                for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
                const blob = new Blob([bytes], { type: mime });
                const file = new File([blob], filename, { type: mime });
                const dt = new DataTransfer();
                dt.items.add(file);
                const event = new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true });
                editor.dispatchEvent(event);
            }
            """
            await page.evaluate(paste_js, {"b64": b64_data, "mime": mime, "filename": path_obj.name})
            uploaded = True

        # Wait for preview indicator
        await asyncio.sleep(2.5)


async def send_prompt(page: Page, prompt: Optional[str] = None) -> None:
    """
    Type prompt and send message.
    If prompt is empty or None (Case 2: Image only), sends directly without typing.
    """
    has_text = prompt is not None and len(prompt.strip()) > 0

    try:
        editor = page.locator(SELECTORS["text_editor"]).first

        if has_text:
            logger.info(f"Typing prompt (length: {len(prompt)})")
            await editor.click()
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await editor.fill(prompt)
            await asyncio.sleep(0.5)
        else:
            logger.info("No prompt text provided (Image-only mode).")

        # Click send button
        send_btn = page.locator(SELECTORS["send_button"]).first
        if await send_btn.is_visible(timeout=3000) and await send_btn.is_enabled():
            await send_btn.click()
            logger.info("Send button clicked")
        else:
            # Fallback Enter key
            await editor.focus()
            await page.keyboard.press("Enter")
            logger.info("Sent via Enter key")

    except PlaywrightTimeout as e:
        logger.error(f"Timeout while sending prompt: {e}")
        raise UnexpectedUIStateError(f"Failed to send prompt: {e}")
    except Exception as e:
        logger.error(f"Error while sending prompt: {e}")
        raise UnexpectedUIStateError(f"Prompt sending error: {e}")


async def extract_generated_image(page: Page) -> Optional[bytes]:
    """Search response area for generated images and return raw bytes."""
    candidate_selectors = [
        "model-response-text img",
        "message-content img",
        ".model-response img",
        "img.image-node"
    ]

    for sel in candidate_selectors:
        images = await page.locator(sel).all()
        for img in images:
            try:
                if not await img.is_visible():
                    continue
                box = await img.bounding_box()
                if box and box["width"] > 150 and box["height"] > 150:
                    test_id = await img.get_attribute("data-test-id") or ""
                    aria_label = await img.get_attribute("aria-label") or ""
                    if test_id == "image-preview" or "preview" in aria_label.lower():
                        continue

                    # Attempt to download via src
                    src = await img.get_attribute("src")
                    if src and src.startswith("http"):
                        try:
                            resp = await page.request.get(src)
                            return await resp.body()
                        except Exception:
                            pass
                    elif src and src.startswith("data:image"):
                        data_part = src.split(",", 1)[1]
                        return base64.b64decode(data_part)

                    # High-fidelity fallback screenshot
                    return await img.screenshot()
            except Exception:
                continue

    return None


async def wait_for_response(page: Page, timeout_ms: int = None) -> Tuple[str, str, Optional[bytes]]:
    """Wait for response, stream stabilization, and any generated image."""
    timeout_ms = timeout_ms or settings.response_timeout
    logger.info(f"Waiting for response (timeout: {timeout_ms}ms)...")

    await asyncio.sleep(3)
    response_selector = SELECTORS["response_content"]

    try:
        await page.wait_for_selector(response_selector, timeout=timeout_ms, state="visible")

        prev_text = ""
        stable_count = 0
        max_iterations = timeout_ms // 1500
        image_bytes = None

        for _ in range(max_iterations):
            # Check for generated image
            image_bytes = await extract_generated_image(page)
            if image_bytes:
                logger.info("Detected generated image in Gemini response!")
                break

            response_elements = page.locator(response_selector)
            count = await response_elements.count()
            if count == 0:
                await asyncio.sleep(1.5)
                continue

            last_response = response_elements.nth(count - 1)
            current_text = await last_response.inner_text()

            if current_text == prev_text and len(current_text) > 0:
                stable_count += 1
                if stable_count >= 2:
                    logger.info("Response text stabilized")
                    break
            else:
                stable_count = 0

            prev_text = current_text
            await asyncio.sleep(1.5)

        # Final extraction
        response_elements = page.locator(response_selector)
        count = await response_elements.count()
        response_text = ""
        raw_html = ""

        if count > 0:
            last_response = response_elements.nth(count - 1)
            response_text = await last_response.inner_text()
            raw_html = await last_response.inner_html()

        if not image_bytes:
            image_bytes = await extract_generated_image(page)

        return response_text, raw_html, image_bytes

    except PlaywrightTimeout:
        logger.error("Timeout waiting for response")
        raise AutomationTimeoutError(f"No response received within {timeout_ms}ms")
    except Exception as e:
        logger.error(f"Error extracting response: {e}")
        raise UnexpectedUIStateError(f"Failed to extract response: {e}")


async def ask_gemini(
    page: Page,
    prompt: Optional[str] = None,
    model: str = "gemini-2.5-pro",
    fallback_to_flash: bool = True,
    files: Optional[List[str]] = None,
    output_image_path: Optional[str] = None
) -> Tuple[str, str, bool, Optional[bytes]]:
    """
    High-level universal function handling all 3 cases:
      - Case 1: Prompt alone (Text -> Image or Text)
      - Case 2: Image alone (Image upload -> Response/Image)
      - Case 3: Image + Prompt (Image upload + Instruction -> Modified Image)
    """
    await ensure_gemini_ready(page)
    await select_model(page, model)

    if files:
        await upload_files(page, files)

    await send_prompt(page, prompt)

    response_text, raw_html, image_bytes = await wait_for_response(page)

    # Check for quota
    if is_quota_error(response_text) and model == "gemini-2.5-pro" and fallback_to_flash:
        logger.info("Quota exceeded on Pro, retrying with Flash...")
        await select_model(page, "gemini-2.5-flash")
        await send_prompt(page, prompt)
        response_text, raw_html, image_bytes = await wait_for_response(page)
        return response_text, "gemini-2.5-flash", True, image_bytes

    if image_bytes and output_image_path:
        out_p = Path(output_image_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(image_bytes)
        logger.info(f"Saved generated image to: {out_p}")

    return response_text, model, False, image_bytes
