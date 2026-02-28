"""Gemini Live API bridge (stub).

This module defines a class `GeminiLiveBridge` that is responsible for
translating WebSocket messages between the client and the Vertex
Gemini Live API.  The implementation details are deliberately
abstracted behind the class interface so that the rest of the
application remains decoupled from the underlying API specifics.

To complete the integration, implement the following methods:

* `connect()`: Establish a connection to the Gemini Live API using
  the appropriate client library or WebSocket protocol.  Use the
  configured model (e.g. `gemini-live-2.5-flash-native-audio`) and
  region.
* `close()`: Close the connection when the session ends.
* `send_audio(pcm16k_bytes)`: Stream audio from the client to the
  model.
* `send_image_jpeg(jpeg_bytes)`: Send JPEG frames (typically at
  1 FPS) to the model.
* `receive()`: An asynchronous iterator that yields events from the
  model (e.g. audio responses, transcripts, or other structured
  outputs).  These events are defined in `protocol.py`.

Implementers should throttle image transmission to minimise cost and
adhere to the Live API limits (one frame per second is typical).  See
Google’s documentation for the Vertex AI Gemini Live API for more
details.
"""

from typing import AsyncIterator, Dict, Any


class GeminiLiveBridge:
    """Skeleton for bridging between client and Gemini Live API."""

    def __init__(self, model_id: str, location: str, system_prompt: str) -> None:
        self.model_id = model_id
        self.location = location
        self.system_prompt = system_prompt
        # internal client / connection would be initialised in connect()
        self._connected = False

    async def connect(self) -> None:
        """Open a session with the Gemini Live API.

        You should use the Vertex AI GenAI SDK or a direct WebSocket
        client to initiate the connection.  After connecting, send
        any required configuration messages to set the system
        instructions (constitution) and prepare the model for audio/video.
        """
        self._connected = True
        # TODO: implement the actual connection logic

    async def close(self) -> None:
        """Close the session with the model."""
        if self._connected:
            # TODO: gracefully close the connection
            self._connected = False

    async def send_audio(self, pcm16k_bytes: bytes) -> None:
        """Send raw PCM audio (16 kHz, 16-bit) to the model."""
        if not self._connected:
            raise RuntimeError("GeminiLiveBridge is not connected")
        # TODO: forward audio bytes to the model

    async def send_image_jpeg(self, jpeg_bytes: bytes) -> None:
        """Send a JPEG image frame to the model (1 FPS recommended)."""
        if not self._connected:
            raise RuntimeError("GeminiLiveBridge is not connected")
        # TODO: forward image bytes to the model

    async def receive(self) -> AsyncIterator[Dict[str, Any]]:
        """Yield events from the model.

        Each event is a dictionary representing one of the supported
        message types defined in `protocol.py`.  This might include
        audio responses (`model.audio`), transcript events
        (`model.transcript`), or other structured outputs.  The loop
        should run until the session ends or the connection is closed.
        """
        if not self._connected:
            raise RuntimeError("GeminiLiveBridge is not connected")
        # TODO: read events from the model's WebSocket and yield them
        while self._connected:
            # Placeholder: nothing to yield
            break
        return