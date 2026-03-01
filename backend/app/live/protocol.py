"""Message protocol definitions for the Vista AI WebSocket.

This module defines helper functions and constants for encoding and
decoding messages exchanged over the client WebSocket connection.  A
client message includes audio or image data, or a confirmation of
completed actions.  A server message may contain model audio, text,
status updates, or final summaries.

These helpers are optional.  They exist to document the expected
structure of messages and to provide helper functions if desired.
"""

from dataclasses import dataclass
from typing import List, Optional


# Types of events sent by the client
CLIENT_INIT = "client.init"
CLIENT_AUDIO = "client.audio"
CLIENT_VIDEO = "client.video"
CLIENT_CONFIRM = "client.confirm"
CLIENT_STOP = "client.stop"

# Types of events sent by the server
SERVER_AUDIO = "server.audio"
SERVER_TEXT = "server.text"
SERVER_STATUS = "server.status"
SERVER_SUMMARY = "server.summary"
SERVER_ERROR = "server.error"


@dataclass
class ClientInit:
    """Represents the initial websocket auth + session bootstrap message."""

    token: str
    session_id: str
    mode: str


@dataclass
class ClientAudio:
    """Represents an audio chunk from the client.

    The `pcm16k` field contains raw 16-bit PCM audio at 16 kHz.  The
    `mime` can be used by the server if it needs to differentiate
    between audio formats (e.g. `audio/pcm;rate=16000`).
    """

    pcm16k: bytes
    mime: str = "audio/pcm;rate=16000"


@dataclass
class ClientVideo:
    """Represents a JPEG image frame from the client."""

    jpeg: bytes
    mime: str = "image/jpeg"


@dataclass
class ClientConfirm:
    """Represents a confirmation from the client that an instruction has been completed."""

    pass


@dataclass
class ServerAudio:
    """Represents an audio chunk from the model to be played by the client."""

    pcm24k: bytes
    mime: str = "audio/pcm;rate=24000"


@dataclass
class ServerText:
    """Represents a textual response or transcript from the model."""

    text: str


@dataclass
class ServerStatus:
    """Represents a status update for the client (e.g. connected, caution, refused)."""

    state: str
    mode: str
    skill: Optional[str] = None


@dataclass
class ServerSummary:
    """Represents a final summary of the session."""

    scenario: str
    bullets: List[str]


@dataclass
class ServerError:
    """Represents an error message to the client."""

    message: str
