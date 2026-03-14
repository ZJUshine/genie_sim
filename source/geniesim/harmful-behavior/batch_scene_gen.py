#!/usr/bin/env python3

# Copyright (c) 2023-2026, AgiBot Inc. All Rights Reserved.
# Author: Genie Sim Team
# License: Mozilla Public License Version 2.0

"""
Batch scene generation script.

Reads harmful_instances.json and harmless_instances.json, then calls
geniesim_scene_gen.py for each instance to generate scenes.

Usage:
    # Run all instances (harmful + harmless)
    python batch_scene_gen.py

    # Run only harmful instances
    python batch_scene_gen.py --type harmful

    # Run only harmless instances
    python batch_scene_gen.py --type harmless 

    # Resume from a specific index (e.g., skip first 10 harmful instances)
    python batch_scene_gen.py --type harmful --start-index 10

    # Limit number of instances to process
    python batch_scene_gen.py --type harmful --limit 5
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
import sys
import time
from pathlib import Path

from geniesim_scene_gen import run_scene_generation

logger = logging.getLogger("batch_scene_gen")

SCRIPT_DIR = Path(__file__).resolve().parent
HARMFUL_JSON = SCRIPT_DIR / "harmful_instances.json"
HARMLESS_JSON = SCRIPT_DIR / "harmless_instances.json"
OUTPUT_ROOT = SCRIPT_DIR / "output"


def load_instances(json_path: Path) -> list[dict]:
    """Load instances from a JSON file."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_object_field(obj_str: str) -> list[str]:
    """Parse the object field string like \"['knife', 'cup']\" into a list."""
    try:
        return ast.literal_eval(obj_str)
    except (ValueError, SyntaxError):
        return [obj_str]


def build_prompt(instance: dict) -> str:
    """Build a scene generation prompt from an instance."""
    scene = instance["scene"]
    objects = parse_object_field(instance["object"])
    objects_str = ", ".join(objects)
    return f"A {scene} with {objects_str}"


def run_batch(
    instance_type: str,
    instances: list[dict],
    start_index: int = 0,
    limit: int | None = None,
    webui_url: str = "http://localhost:8080",
    headless: bool = False,
    timeout_assistant: int = 180,
    timeout_generator: int = 180,
    verbose: bool = True,
) -> None:
    """Run scene generation for a batch of instances."""
    end_index = len(instances) if limit is None else min(start_index + limit, len(instances))
    total = end_index - start_index

    logger.info("=" * 70)
    logger.info("Batch: %s | Total: %d | Range: [%d, %d)", instance_type, total, start_index, end_index)
    logger.info("=" * 70)

    results = {"success": [], "failed": []}

    for i in range(start_index, end_index):
        instance = instances[i]
        prompt = build_prompt(instance)
        output_dir = OUTPUT_ROOT / instance_type / f"{i:04d}"

        progress = f"[{i - start_index + 1}/{total}]"
        logger.info("%s Processing %s instance %d: %s", progress, instance_type, i, prompt)

        # Save instance metadata
        output_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = output_dir / "instance.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump({"index": i, "type": instance_type, **instance}, f, indent=2, ensure_ascii=False)

        try:
            run_scene_generation(
                prompt=prompt,
                output_dir=str(output_dir),
                webui_url=webui_url,
                headless=headless,
                timeout_assistant=timeout_assistant,
                timeout_generator=timeout_generator,
                verbose=verbose,
            )
            results["success"].append(i)
            logger.info("%s Instance %d completed successfully", progress, i)
        except KeyboardInterrupt:
            logger.warning("Interrupted by user at instance %d", i)
            results["failed"].append(i)
            break
        except Exception:
            logger.exception("%s Instance %d failed", progress, i)
            results["failed"].append(i)

        # Brief pause between requests
        time.sleep(2)

    # Summary
    logger.info("=" * 70)
    logger.info("Batch %s complete: %d success, %d failed", instance_type, len(results["success"]), len(results["failed"]))
    if results["failed"]:
        logger.info("Failed indices: %s", results["failed"])
    logger.info("=" * 70)

    # Save results summary
    summary_path = OUTPUT_ROOT / instance_type / "batch_results.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch scene generation from harmful/harmless instance data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--type",
        type=str,
        choices=["harmful", "harmless", "all"],
        default="all",
        help="Which instance set to process (default: all)",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Start from this instance index (default: 0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of instances to process per type (default: all)",
    )
    parser.add_argument(
        "--webui-url",
        type=str,
        default="http://localhost:8080",
        help="Open WebUI base URL (default: http://localhost:8080)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode",
    )
    parser.add_argument(
        "--timeout-assistant",
        type=int,
        default=180,
        help="Timeout for assistant response in seconds (default: 180)",
    )
    parser.add_argument(
        "--timeout-generator",
        type=int,
        default=180,
        help="Timeout for generator response in seconds (default: 180)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Enable verbose logging",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    common_kwargs = dict(
        webui_url=args.webui_url,
        headless=args.headless,
        timeout_assistant=args.timeout_assistant,
        timeout_generator=args.timeout_generator,
        verbose=args.verbose,
        start_index=args.start_index,
        limit=args.limit,
    )

    if args.type in ("harmful", "all"):
        harmful_instances = load_instances(HARMFUL_JSON)
        logger.info("Loaded %d harmful instances", len(harmful_instances))
        run_batch("harmful", harmful_instances, **common_kwargs)

    if args.type in ("harmless", "all"):
        harmless_instances = load_instances(HARMLESS_JSON)
        logger.info("Loaded %d harmless instances", len(harmless_instances))
        run_batch("harmless", harmless_instances, **common_kwargs)


if __name__ == "__main__":
    main()
