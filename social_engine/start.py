"""Railway entry-point: reads $PORT from env and starts uvicorn.

Using a Python entry-point (rather than shell expansion in startCommand)
avoids Railway's uncertain shell-vs-exec CMD handling for ${PORT:-N} syntax.
"""
import os
import uvicorn

port = int(os.environ.get("PORT", 8000))
uvicorn.run("webhook.api:app", host="0.0.0.0", port=port, log_level="info")
