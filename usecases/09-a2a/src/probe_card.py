"""E1: what the caller can learn before it sends a single token.

Fetches the remote agent's public card from the other process and records the
fields verbatim. No model call.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    CARD_PATH,
    PORT,
    base,
    emit,
    fetch_card,
    reset_receipts,
    start_server,
    stop_server,
)


def main() -> None:
    reset_receipts()
    proc = start_server("normal", PORT + 1)
    try:
        card = fetch_card(PORT + 1)
        record = base("card", PORT + 1)
        record.update(
            {
                "card_path": CARD_PATH,
                "card": card,
                "card_keys": sorted(card.keys()),
                "skills": card.get("skills"),
                "capabilities": card.get("capabilities"),
                "url": card.get("url"),
            }
        )
        emit("a2a-card", record)
    finally:
        stop_server(proc)


if __name__ == "__main__":
    main()
