"""Process currently due retry jobs once: python -m app.workers.retry_worker --once."""

from __future__ import annotations

import argparse
import asyncio

from app.main import app
from app.services.workflow_executor import process_due_retries


async def _run_once() -> int:
    async with app.router.lifespan_context(app):
        database = app.state.database
        return process_due_retries(
            database.session_factory,
            app.state.verification_provider,
            app.state.retry_policy,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Process due FlowGuard retries once")
    parser.add_argument("--once", action="store_true", help="process due jobs once (default)")
    parser.parse_args()
    count = asyncio.run(_run_once())
    print(f"processed {count} due retry job(s)")


if __name__ == "__main__":
    main()
