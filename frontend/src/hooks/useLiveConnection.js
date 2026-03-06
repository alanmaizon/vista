import { useRef, useState, useCallback, useEffect } from "react";

/**
 * Custom hook that manages the WebSocket lifecycle with the /ws/live endpoint.
 *
 * @param {object} options
 * @param {function} options.onMessage  – called with each parsed server message
 * @param {function} [options.onOpen]   – called when the socket opens
 * @param {function} [options.onClose]  – called when the socket closes
 * @param {function} [options.onError]  – called on socket errors
 * @returns {{ connect, disconnect, send, readyState, isConnected }}
 */
export default function useLiveConnection({ onMessage, onOpen, onClose, onError } = {}) {
  const wsRef = useRef(null);
  const [readyState, setReadyState] = useState(WebSocket.CLOSED);

  const updateState = useCallback(() => {
    setReadyState(wsRef.current ? wsRef.current.readyState : WebSocket.CLOSED);
  }, []);

  const connect = useCallback(
    ({ token = "", sessionId, mode = "HEAR_PHRASE" } = {}) => {
      if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) {
        return;
      }

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const url = `${protocol}//${window.location.host}/ws/live`;
      const ws = new WebSocket(url);

      ws.onopen = () => {
        updateState();
        /* Send the init message required by the backend */
        ws.send(
          JSON.stringify({
            type: "client.init",
            token,
            session_id: sessionId ?? "",
            mode,
          }),
        );
        onOpen?.();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          onMessage?.(data);
        } catch {
          /* ignore non-JSON frames */
        }
      };

      ws.onerror = (event) => {
        updateState();
        onError?.(event);
      };

      ws.onclose = () => {
        updateState();
        onClose?.();
      };

      wsRef.current = ws;
      updateState();
    },
    [onMessage, onOpen, onClose, onError, updateState],
  );

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
      updateState();
    }
  }, [updateState]);

  const send = useCallback((payload) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const data = typeof payload === "string" ? payload : JSON.stringify(payload);
      wsRef.current.send(data);
    }
  }, []);

  /* Clean up on unmount */
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  return {
    connect,
    disconnect,
    send,
    readyState,
    isConnected: readyState === WebSocket.OPEN,
  };
}
