"""Remote half of the UC09 bench. Runs in its own OS process on 127.0.0.1.

Start it through common.start_server(), or directly for debugging:

    UC09_REMOTE_MODE=normal .venv/bin/python src/remote_server.py

The caller process never imports this module. That is the boundary under test.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn  # noqa: E402
from strands.multiagent.a2a.server import A2AServer  # noqa: E402

from common import HOST, PORT, remote_agent  # noqa: E402

mode = os.environ.get("UC09_REMOTE_MODE", "normal")
port = int(os.environ.get("UC09_PORT") or PORT)

server = A2AServer(agent=remote_agent(mode), host=HOST, port=port)
uvicorn.run(server.to_starlette_app(), host=HOST, port=port, log_level="warning")
