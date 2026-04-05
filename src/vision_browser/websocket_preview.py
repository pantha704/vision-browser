"""WebSocket live preview -- real-time browser state streaming."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class WebSocketPreview:
    """Streams browser state updates via WebSocket for live debugging.

    Provides:
    - Screenshot updates at configurable intervals
    - Navigation, click, fill, and error events
    - Simple web dashboard for viewing the stream
    """

    def __init__(self, port: int = 8765, interval_ms: int = 1000):
        self.port = port
        self.interval_ms = interval_ms
        self._clients: list[Callable] = []
        self._server = None

    def broadcast(self, event: str, data: dict[str, Any]) -> int:
        """Broadcast an event to all connected clients.

        Args:
            event: Event type (screenshot, navigate, click, fill, error).
            data: Event payload.

        Returns:
            Number of clients that received the event.
        """
        message = json.dumps({"event": event, "data": data})
        sent = 0
        for client in self._clients:
            try:
                client(message)
                sent += 1
            except Exception as e:
                logger.debug(f"Failed to send to client: {e}")
        return sent

    def send_screenshot(self, image_path: str) -> int:
        """Send a screenshot update to all clients.

        Args:
            image_path: Path to the screenshot image.

        Returns:
            Number of clients that received the screenshot.
        """
        try:
            image_data = Path(image_path).read_bytes()
            b64 = base64.b64encode(image_data).decode()
            return self.broadcast("screenshot", {
                "image": b64,
                "format": "png",
                "size": len(image_data),
            })
        except Exception as e:
            logger.warning(f"Failed to send screenshot: {e}")
            return 0

    def send_navigation(self, url: str, title: str) -> int:
        """Send navigation event."""
        return self.broadcast("navigate", {"url": url, "title": title})

    def send_action(self, action_type: str, details: dict) -> int:
        """Send action event (click, fill, etc.)."""
        return self.broadcast("action", {"type": action_type, **details})

    def send_error(self, message: str) -> int:
        """Send error event."""
        return self.broadcast("error", {"message": message})

    def connect(self, client_callback: Callable) -> None:
        """Register a client callback for receiving messages.

        Args:
            client_callback: Function to call with JSON message strings.
        """
        self._clients.append(client_callback)
        logger.debug(f"Client connected. Total: {len(self._clients)}")

    def disconnect(self, client_callback: Callable) -> None:
        """Remove a client callback."""
        if client_callback in self._clients:
            self._clients.remove(client_callback)
            logger.debug(f"Client disconnected. Total: {len(self._clients)}")

    @property
    def client_count(self) -> int:
        """Number of connected clients."""
        return len(self._clients)

    def generate_dashboard_html(self) -> str:
        """Generate a simple HTML dashboard for live preview."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Vision Browser Live Preview</title>
    <style>
        body {{ font-family: monospace; margin: 20px; background: #1a1a2e; color: #eee; }}
        #screenshot {{ max-width: 100%; border: 2px solid #333; }}
        #events {{ height: 200px; overflow-y: auto; background: #0f0f23; padding: 10px; margin-top: 10px; }}
        .event {{ margin: 2px 0; font-size: 12px; }}
        .event-navigate {{ color: #4fc3f7; }}
        .event-click {{ color: #81c784; }}
        .event-fill {{ color: #ffb74d; }}
        .event-error {{ color: #e57373; }}
        h2 {{ color: #7c4dff; }}
    </style>
</head>
<body>
    <h2>Vision Browser Live Preview</h2>
    <img id="screenshot" alt="Live preview" />
    <div id="events"></div>
    <script>
        const ws = new WebSocket('ws://localhost:{self.port}');
        const events = document.getElementById('events');
        const img = document.getElementById('screenshot');

        ws.onmessage = (msg) => {{
            const data = JSON.parse(msg.data);
            if (data.event === 'screenshot') {{
                img.src = 'data:image/png;base64,' + data.data.image;
            }}
            const div = document.createElement('div');
            div.className = 'event event-' + data.event;
            div.textContent = '[' + data.event + '] ' + JSON.stringify(data.data);
            events.prepend(div);
        }};

        ws.onopen = () => {{
            events.innerHTML = '<div class="event">Connected to Vision Browser</div>';
        }};

        ws.onerror = () => {{
            events.innerHTML = '<div class="event event-error">Connection failed</div>';
        }};
    </script>
</body>
</html>"""
