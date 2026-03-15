import { startTransition, useEffect, useRef, useState } from "react";

import {
  LIVE_PROTOCOL_VERSION,
  type ClientHelloEvent,
  type ClientPingEvent,
  type ClientTextInputEvent,
  type ClientTurnEndEvent,
  type LiveServerEvent,
} from "../live-protocol";
import { resolveLiveWebSocketUrl } from "../lib/api";
import type { SessionBootstrapResponse } from "../types";

export type LiveConnectionState = "idle" | "connecting" | "connected" | "error";

export interface TranscriptEntry {
  id: string;
  speaker: "learner" | "tutor" | "system";
  text: string;
  source: string;
  turnId: string | null;
  isFinal: boolean;
}

interface UseLiveAgentOptions {
  preferredResponseLanguage: string;
  session: SessionBootstrapResponse | null;
}

const MAX_TRANSCRIPT_ENTRIES = 300;

function isLiveServerEvent(payload: unknown): payload is LiveServerEvent {
  return Boolean(
    payload &&
      typeof payload === "object" &&
      "type" in payload &&
      typeof (payload as { type?: unknown }).type === "string",
  );
}

export function useLiveAgent({ preferredResponseLanguage, session }: UseLiveAgentOptions) {
  const [connectionState, setConnectionState] = useState<LiveConnectionState>("idle");
  const [connectionDetail, setConnectionDetail] = useState("Start a session to enable live tutor.");
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [transcriptEntries, setTranscriptEntries] = useState<TranscriptEntry[]>([]);

  const socketRef = useRef<WebSocket | null>(null);
  const entryCounterRef = useRef(0);
  const turnCounterRef = useRef(0);
  const intentionalCloseRef = useRef(false);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopPingLoop() {
    if (pingIntervalRef.current !== null) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  }

  function appendTranscriptEntry(entry: Omit<TranscriptEntry, "id">) {
    const id = `entry-${Date.now()}-${entryCounterRef.current++}`;
    startTransition(() => {
      setTranscriptEntries((current) => {
        const next = [...current, { ...entry, id }];
        if (next.length <= MAX_TRANSCRIPT_ENTRIES) {
          return next;
        }
        return next.slice(next.length - MAX_TRANSCRIPT_ENTRIES);
      });
    });
  }

  function disconnect() {
    intentionalCloseRef.current = true;
    stopPingLoop();
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    setConnectionState("idle");
    setConnectionDetail(session ? "Disconnected from live tutor." : "Start a session to enable live tutor.");
  }

  function connect() {
    if (!session) {
      setConnectionError("Start a tutor session before joining live.");
      return;
    }

    disconnect();
    intentionalCloseRef.current = false;
    setConnectionError(null);
    setConnectionState("connecting");
    setConnectionDetail("Connecting to live tutor...");

    const websocketUrl = resolveLiveWebSocketUrl(session.live_session.websocket_path);
    const socket = new WebSocket(websocketUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      setConnectionState("connected");
      setConnectionDetail("Connected. Sending live handshake...");

      const helloEvent: ClientHelloEvent = {
        type: "client.hello",
        protocol_version: LIVE_PROTOCOL_VERSION,
        session_id: session.session_id,
        mode: session.mode,
        target_text: session.session_state.target_text ?? undefined,
        preferred_response_language: preferredResponseLanguage,
        capabilities: {
          audio_input: true,
          audio_output: true,
          image_input: true,
          supports_barge_in: true,
        },
        client_name: "web-frontend",
      };

      socket.send(JSON.stringify(helloEvent));
    };

    socket.onmessage = (event: MessageEvent<string>) => {
      if (typeof event.data !== "string") {
        return;
      }

      let payload: unknown;
      try {
        payload = JSON.parse(event.data) as unknown;
      } catch {
        return;
      }

      if (!isLiveServerEvent(payload)) {
        return;
      }

      switch (payload.type) {
        case "server.ready":
          setConnectionDetail("Socket ready. Waiting for tutor status...");
          return;
        case "server.status":
          setConnectionDetail(payload.detail);
          appendTranscriptEntry({
            speaker: "system",
            text: payload.detail,
            source: payload.phase,
            turnId: payload.turn_id ?? null,
            isFinal: true,
          });
          return;
        case "server.transcript":
          appendTranscriptEntry({
            speaker: payload.speaker,
            text: payload.text,
            source: payload.source,
            turnId: payload.turn_id,
            isFinal: payload.is_final,
          });
          return;
        case "server.tool.call":
          appendTranscriptEntry({
            speaker: "system",
            text: `Tool call: ${payload.tool_name}`,
            source: "tool_call",
            turnId: payload.turn_id,
            isFinal: true,
          });
          return;
        case "server.tool.result":
          appendTranscriptEntry({
            speaker: "system",
            text:
              payload.status === "completed"
                ? `Tool result: ${payload.tool_name}`
                : `Tool failed: ${payload.tool_name}`,
            source: "tool_result",
            turnId: payload.turn_id,
            isFinal: true,
          });
          return;
        case "server.error":
          setConnectionError(payload.message);
          setConnectionState("error");
          appendTranscriptEntry({
            speaker: "system",
            text: `Error: ${payload.message}`,
            source: payload.code,
            turnId: null,
            isFinal: true,
          });
          return;
        default:
          return;
      }
    };

    socket.onerror = () => {
      setConnectionError("Live websocket error. Please reconnect.");
      setConnectionState("error");
    };

    socket.onclose = () => {
      stopPingLoop();
      socketRef.current = null;

      if (intentionalCloseRef.current) {
        setConnectionState("idle");
        return;
      }

      setConnectionState("error");
      setConnectionDetail("Live tutor connection closed unexpectedly.");
    };
  }

  function sendTextTurn(text: string): boolean {
    const trimmed = text.trim();
    if (!trimmed) {
      return false;
    }

    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setConnectionError("Join live before sending transcript turns.");
      return false;
    }

    const turnId = `turn-ui-${Date.now()}-${turnCounterRef.current++}`;
    const textEvent: ClientTextInputEvent = {
      type: "client.input.text",
      protocol_version: LIVE_PROTOCOL_VERSION,
      turn_id: turnId,
      text: trimmed,
      source: "typed",
      is_final: true,
    };
    const turnEndEvent: ClientTurnEndEvent = {
      type: "client.turn.end",
      protocol_version: LIVE_PROTOCOL_VERSION,
      turn_id: turnId,
      reason: "submit_click",
    };

    try {
      socket.send(JSON.stringify(textEvent));
      socket.send(JSON.stringify(turnEndEvent));
      return true;
    } catch {
      setConnectionError("Unable to send learner turn over websocket.");
      return false;
    }
  }

  function clearTranscript() {
    setTranscriptEntries([]);
  }

  useEffect(() => {
    if (connectionState !== "connected") {
      stopPingLoop();
      return;
    }

    pingIntervalRef.current = setInterval(() => {
      const socket = socketRef.current;
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        return;
      }
      const pingEvent: ClientPingEvent = {
        type: "client.control.ping",
        protocol_version: LIVE_PROTOCOL_VERSION,
        client_time: new Date().toISOString(),
      };
      socket.send(JSON.stringify(pingEvent));
    }, 20000);

    return () => {
      stopPingLoop();
    };
  }, [connectionState]);

  useEffect(() => {
    setTranscriptEntries([]);
    setConnectionError(null);
    setConnectionState("idle");
    setConnectionDetail(session ? "Session ready. Join live to begin." : "Start a session to enable live tutor.");
    intentionalCloseRef.current = true;
    stopPingLoop();
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
  }, [session?.session_id]);

  useEffect(() => {
    return () => {
      intentionalCloseRef.current = true;
      stopPingLoop();
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, []);

  return {
    clearTranscript,
    connect,
    connectionDetail,
    connectionError,
    connectionState,
    disconnect,
    sendTextTurn,
    transcriptEntries,
  };
}
