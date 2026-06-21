"""Entry points: `uv run aggregator-run [--dry-run]` / `uv run aggregator-publish-sns [--dry-run]`."""

from __future__ import annotations

import argparse
import logging

from dotenv import load_dotenv

from .pipeline import run_collect, run_publish_sns


def main() -> None:
    load_dotenv()  # loads ./.env if present; no-op (and no error) otherwise

    parser = argparse.ArgumentParser(description="Run the anime premiere-event collection pipeline.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and extract, but skip persisting data/events.json and publishing.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Maximum number of animatetimes listing pages to crawl per run "
            "(overrides ANIMATETIMES_MAX_PAGES / the default of 30)."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    run_collect(dry_run=args.dry_run, max_pages=args.max_pages)


def main_sns() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Post pending events to X/Bluesky.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run publishers but skip persisting publish_status updates to data/events.json.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    run_publish_sns(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
