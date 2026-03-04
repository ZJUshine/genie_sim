# Copyright (c) 2023-2026, AgiBot Inc. All Rights Reserved.
# Author: Genie Sim Team
# License: Mozilla Public License Version 2.0

"""
GenieSim Scene Auto-Generation Script (Playwright Browser Automation)

Automates the scene generation workflow in Open WebUI by:
1. Chatting with "GenieSim Assistant" to retrieve relevant assets
2. Chatting with "GenieSim Generator" to generate scene code
3. Clicking "Save Code to File" to persist the result
4. Copying output to the specified directory

Usage:
    python geniesim_scene_gen.py --prompt "一个圆桌上的丰盛餐点"  --visible --verbose
    python geniesim_scene_gen.py --prompt "场景描述" --output-dir ./my_output

Requirements:
    pip install playwright && playwright install chromium
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import time
from pathlib import Path
from typing import Optional
from playwright.sync_api import sync_playwright
logger = logging.getLogger("geniesim_scene_gen")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WEBUI_URL = "http://localhost:8080"
ASSISTANT_MODEL = "GenieSim Assistant"
GENERATOR_MODEL = "GenieSim Generator"

DEFAULT_TIMEOUT_ASSISTANT = 180  # seconds
DEFAULT_TIMEOUT_GENERATOR = 180  # seconds
STABILITY_WAIT = 2.0  # seconds for content stability check (fallback)
POLL_INTERVAL = 1.0  # seconds between stability polls

# Default LLM_RESULT output path (matches save_to_local.py default)
DEFAULT_LLM_RESULT_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# PlaywrightAutomator — browser automation core
# ---------------------------------------------------------------------------

class PlaywrightAutomator:
    """Drive Open WebUI through Playwright to generate scenes."""

    def __init__(
        self,
        webui_url: str = WEBUI_URL,
        headless: bool = True,
        timeout_assistant: int = DEFAULT_TIMEOUT_ASSISTANT,
        timeout_generator: int = DEFAULT_TIMEOUT_GENERATOR,
        verbose: bool = False,
    ) -> None:
        self.webui_url = webui_url.rstrip("/")
        self.headless = headless
        self.timeout_assistant = timeout_assistant
        self.timeout_generator = timeout_generator
        self.verbose = verbose

        # Playwright objects — initialised in launch()
        self._playwright = None
        self._browser = None
        self._context = None
        self.page = None

    # -- lifecycle -----------------------------------------------------------

    def launch(self) -> None:
        """Start browser and open a new page."""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="en-US",
        )
        self.page = self._context.new_page()
        self.page.set_default_timeout(60_000)  # 60 s default for locators
        logger.info("Browser launched (headless=%s)", self.headless)

    def close(self) -> None:
        """Tear down browser resources."""
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        logger.info("Browser closed")

    # -- navigation ----------------------------------------------------------

    def navigate_to_chat(self) -> None:
        """Navigate to the Open WebUI chat page."""
        self.page.goto(self.webui_url, wait_until="networkidle")
        self.page.wait_for_timeout(500)
        logger.debug("Current URL after navigation: %s", self.page.url)


    def select_model(self, model_display_name: str) -> None:
        """
        Open the model selector dropdown and choose *model_display_name*.
        """
        page = self.page
        logger.info("Selecting model: %s", model_display_name)

        # Click the model selector button
        selector_btn = page.locator("button[aria-label='Select a model']")

        selector_btn.first.click()
        page.wait_for_timeout(500)

        # Type in the search box inside the dropdown (if any)
        search_input = page.locator("input[aria-label='Search in Models']")
        
        if search_input.count() > 0:
            search_input.first.fill(model_display_name)
            page.wait_for_timeout(500)

        # Click the matching model item
        model_item = page.locator(f"button[aria-label='{model_display_name}']")
        model_item.first.click()
        page.wait_for_timeout(500)
        logger.info("Model '%s' selected", model_display_name)

    def send_message(self, text: str) -> None:
        """Type *text* into the chat input and press Send."""
        page = self.page
        logger.info("Sending message (length=%d)…", len(text))

        # Locate chat input
        chat_input = page.locator("div[id='chat-input']")
        # Use type() to simulate real keyboard input
        chat_input.first.fill(text)
        page.wait_for_timeout(500)

        # Send via Enter key
        send_message_btn = page.locator("button[id='send-message-button']")
        send_message_btn.last.click()
        logger.debug("Pressed Enter to send")

    def wait_for_response(self, timeout: int) -> None:
        """
        Wait for the assistant's streaming response to complete.
        """
        page = self.page
        logger.info("Waiting for response (timeout=%ds)…", timeout)

        baseline = getattr(self, "_msg_count_before_send", 0)
        deadline = time.time() + timeout

        # ── Wait for send button to reappear ──────────────────────
        logger.debug("Waiting for send button to reappear…")
        remaining_ms = max(int((deadline - time.time()) * 1000), 5000)
        ready_btn = page.locator("button[aria-label='Voice mode']")
        ready_btn.first.wait_for(state="visible", timeout=remaining_ms)
        logger.info("Assistant response complete")

    def get_last_response_text(self) -> str:
        """Return the text content of the last assistant message."""
        text = self._get_raw_last_message_text()
        if text is None:
            raise RuntimeError("No assistant message found on page")
        return text

    def _get_raw_last_message_text(self) -> Optional[str]:
        """Extract raw text from the last message element."""
        page = self.page
        # Open WebUI wraps assistant messages in elements with id="message-*"
        messages = page.locator("[id^='message-']")
        count = messages.count()
        if count == 0:
            return None
        last_msg = messages.nth(count - 1)
        return last_msg.inner_text()

    def click_save_code_action(self) -> bool:
        """
        Click the "Save Code to File" action button and handle the
        confirmation dialog.  Returns True on success.
        """
        page = self.page
        logger.info("Clicking 'Save Code to File' action…")

        # Locate the button by its aria-label attribute
        save_btn = page.locator("button[aria-label='Save Code to File']")
        save_btn.last.wait_for(state="visible", timeout=60_000)
        save_btn.last.click()
        page.wait_for_timeout(500)

        # Handle confirmation dialog (if auto_confirm is False in save_to_local.py)
        confirm_btn = page.locator("button:has-text('Confirm'):visible")
        if confirm_btn.count() > 0:
            confirm_btn.last.click()
            page.wait_for_timeout(500)

        return True


# ---------------------------------------------------------------------------
# Orchestrator — ties everything together
# ---------------------------------------------------------------------------


def run_scene_generation(
    prompt: str,
    output_dir: Optional[str] = None,
    webui_url: str = WEBUI_URL,
    headless: bool = True,
    timeout_assistant: int = DEFAULT_TIMEOUT_ASSISTANT,
    timeout_generator: int = DEFAULT_TIMEOUT_GENERATOR,
    verbose: bool = False,
) -> Path:
    """
    End-to-end scene generation.

    1. Chat with GenieSim Assistant → asset list
    2. Chat with GenieSim Generator → scene code
    3. Click Save Codes to File
    4. Copy LLM_RESULT.py to *output_dir*

    Returns the path to the output directory.
    """
    output_path = Path(output_dir) if output_dir else Path.cwd() / "geniesim_output"
    output_path.mkdir(parents=True, exist_ok=True)

    automator = PlaywrightAutomator(
        webui_url=webui_url,
        headless=headless,
        timeout_assistant=timeout_assistant,
        timeout_generator=timeout_generator,
        verbose=verbose,
    )

    try:
        # ── Launch browser ──────────────────────────────────────────
        automator.launch()

        # ── Navigate to chat page ──────────────────────────────────
        automator.navigate_to_chat()

        # ── Step 1: GenieSim Assistant (asset retrieval) ───────────
        logger.info("═" * 60)
        logger.info("Step 1: Chatting with %s", ASSISTANT_MODEL)
        logger.info("═" * 60)

        automator.select_model(ASSISTANT_MODEL)
        automator.send_message(prompt)
        automator.wait_for_response(timeout_assistant)

        assistant_response = automator.get_last_response_text()
        logger.info("Assistant response length: %d chars", len(assistant_response))

        # Save assistant response
        (output_path / "assistant_response.txt").write_text(assistant_response, encoding="utf-8")
        logger.info("Saved assistant_response.txt")

        # ── Step 2: GenieSim Generator (code generation) ──────────
        # Stay in the same chat window so the Generator can see the
        # Assistant's response as conversation context.
        logger.info("═" * 60)
        logger.info("Step 2: Chatting with %s (same window)", GENERATOR_MODEL)
        logger.info("═" * 60)

        automator.select_model(GENERATOR_MODEL)
        
        automator.send_message("generate the scene")
        automator.wait_for_response(timeout_generator)

        generator_response = automator.get_last_response_text()
        logger.info("Generator response length: %d chars", len(generator_response))

        # Save generator response
        (output_path / "generator_response.txt").write_text(generator_response, encoding="utf-8")
        logger.info("Saved generator_response.txt")

        # ── Step 3: Save code via UI button ───────────────────────
        logger.info("═" * 60)
        logger.info("Step 3: Saving code to file")
        logger.info("═" * 60)

        save_ok = automator.click_save_code_action()

        # ── Step 4: Copy LLM_RESULT.py to output directory ────────
        logger.info("═" * 60)
        logger.info("Step 4: Copying output files")
        logger.info("═" * 60)

        # The save_to_local.py action writes to DEFAULT_LLM_RESULT_DIR / LLM_RESULT.py
        llm_result_src = DEFAULT_LLM_RESULT_DIR / "LLM_RESULT.py"
        llm_result_dst = output_path / "LLM_RESULT.py"

        if llm_result_src.exists():
            shutil.copy2(str(llm_result_src), str(llm_result_dst))
            logger.info("Copied LLM_RESULT.py → %s", llm_result_dst)
        else:
            logger.error("LLM_RESULT.py not found at %s — save action may have failed", llm_result_src)

        if save_ok:
            logger.info("✓ Scene generation completed successfully!")
        else:
            logger.warning("Scene generation completed, but Save action may not have succeeded")

        logger.info("Output directory: %s", output_path)
        return output_path

    finally:
        automator.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GenieSim Scene Auto-Generation (Playwright browser automation)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="一个圆桌上的丰盛餐点",
        help="Scene description prompt.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(Path(__file__).resolve().parent / "output"),
        help="Directory to store output files (default: source/geniesim/harmful-behavior/output)",
    )
    parser.add_argument(
        "--webui-url",
        type=str,
        default=WEBUI_URL,
        help=f"Open WebUI base URL (default: {WEBUI_URL})",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        default=True,
        help="Show browser window (non-headless mode) for debugging",
    )
    parser.add_argument(
        "--timeout-assistant",
        type=int,
        default=DEFAULT_TIMEOUT_ASSISTANT,
        help=f"Timeout in seconds for Assistant response (default: {DEFAULT_TIMEOUT_ASSISTANT})",
    )
    parser.add_argument(
        "--timeout-generator",
        type=int,
        default=DEFAULT_TIMEOUT_GENERATOR,
        help=f"Timeout in seconds for Generator response (default: {DEFAULT_TIMEOUT_GENERATOR})",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Enable verbose (DEBUG) logging",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Get prompt interactively if not provided
    prompt = args.prompt
    logger.info("Scene prompt: %s", prompt)

    try:
        output_path = run_scene_generation(
            prompt=prompt,
            output_dir=args.output_dir,
            webui_url=args.webui_url,
            headless=not args.visible,
            timeout_assistant=args.timeout_assistant,
            timeout_generator=args.timeout_generator,
            verbose=args.verbose,
        )
        print(f"\n{'='*60}")
        print(f"Scene generation complete!")
        print(f"Output directory: {output_path}")
        print(f"{'='*60}")
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception:
        logger.exception("Scene generation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
