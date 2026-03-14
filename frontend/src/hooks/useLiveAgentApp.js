import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "../lib/api";
import { bytesToBase64 } from "../lib/audioCapture";
import { createLiveAudioPlayback } from "../lib/liveAudioPlayback";
import { createLiveAudioRouter } from "../lib/liveAudioRouter";

const MESSAGE_LIMIT = 32;
const CAMERA_FRAME_INTERVAL_MS = 1100;
const AUTO_MIN_SPEECH_CHUNKS = 4;
const PUSH_TO_TALK_MIN_SPEECH_CHUNKS = 2;
const ASSISTANT_SPEECH_GATE_MS = 1200;

function buildInitialProfile() {
  return {
    mode: "music_tutor",
    instrument: "",
    piece: "",
    goal: "",
  };
}

function buildInitialAudioLevels() {
  return {
    energyDb: -90,
    speechConfidence: 0,
    musicConfidence: 0,
    speechActive: false,
    pitchHz: null,
    pitchConfidence: 0,
  };
}

function buildInitialConnectionMeta() {
  return {
    sessionId: null,
    transport: null,
    location: null,
    skill: null,
  };
}

function normalizeIncomingMessage(data) {
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return data;
  }
  const { type, payload, metadata, ...rest } = data;
  if (payload && typeof payload === "object" && !Array.isArray(payload)) {
    return {
      type,
      ...payload,
      ...(metadata && typeof metadata === "object" && !Array.isArray(metadata) ? metadata : {}),
      ...rest,
    };
  }
  if (metadata && typeof metadata === "object" && !Array.isArray(metadata)) {
    return {
      type,
      ...metadata,
      ...rest,
    };
  }
  return data;
}

function normalizeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function mergeMessageText(existingText, incomingText) {
  const existing = normalizeText(existingText);
  const incoming = normalizeText(incomingText);

  if (!existing) {
    return incoming;
  }
  if (!incoming) {
    return existing;
  }
  if (incoming === existing) {
    return existing;
  }
  if (incoming.startsWith(existing)) {
    return incoming;
  }
  if (existing.startsWith(incoming)) {
    return existing;
  }
  const omitSpace = /^[,.;:!?)]/.test(incoming) || /[(/"']$/.test(existing);
  return `${existing}${omitSpace ? "" : " "}${incoming}`.replace(/\s+([,.;:!?])/g, "$1");
}

function upsertMessage(items, nextMessage) {
  const index = items.findIndex((item) => item.id === nextMessage.id);
  if (index === -1) {
    return [...items, nextMessage].slice(-MESSAGE_LIMIT);
  }

  const current = items[index];
  const updated = {
    ...current,
    ...nextMessage,
    text: mergeMessageText(current.text, nextMessage.text),
  };
  const nextItems = [...items];
  nextItems[index] = updated;
  return nextItems.slice(-MESSAGE_LIMIT);
}

function makeMessageId(prefix, turnId, fallbackIndex) {
  if (turnId) {
    return `${prefix}:${turnId}`;
  }
  return `${prefix}:fallback:${fallbackIndex}`;
}

export default function useLiveAgentApp() {
  const [profileDraft, setProfileDraft] = useState(buildInitialProfile);
  const [sessionProfile, setSessionProfile] = useState(null);
  const [runtimeInfo, setRuntimeInfo] = useState(null);
  const [runtimeDebug, setRuntimeDebug] = useState(null);
  const [messages, setMessages] = useState([]);
  const [summary, setSummary] = useState(null);
  const [connectionError, setConnectionError] = useState("");
  const [conversationInput, setConversationInput] = useState("");
  const [isConnecting, setIsConnecting] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [assistantState, setAssistantState] = useState("idle");
  const [micEnabled, setMicEnabled] = useState(true);
  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [speechInputMode, setSpeechInputMode] = useState("push_to_talk");
  const [isPushToTalkActive, setIsPushToTalkActive] = useState(false);
  const [liveAudioMode, setLiveAudioMode] = useState("SILENCE");
  const [liveAudioLevels, setLiveAudioLevels] = useState(buildInitialAudioLevels);
  const [connectionMeta, setConnectionMeta] = useState(buildInitialConnectionMeta);

  const videoRef = useRef(null);
  const wsRef = useRef(null);
  const audioRouterRef = useRef(null);
  const playbackRef = useRef(null);
  const cameraStreamRef = useRef(null);
  const frameTimerRef = useRef(null);
  const assistantPulseTimerRef = useRef(null);
  const messageCounterRef = useRef(0);
  const isConnectedRef = useRef(false);
  const cameraCanvasRef = useRef(null);
  const speechInputModeRef = useRef("push_to_talk");
  const pushToTalkActiveRef = useRef(false);
  const pushToTalkReleaseTimerRef = useRef(null);
  const speechTurnOpenRef = useRef(false);
  const speechChunkBufferRef = useRef([]);
  const speechSentChunkCountRef = useRef(0);
  const awaitingAssistantTurnRef = useRef(false);
  const assistantStateRef = useRef("idle");
  const assistantSpeechGateUntilRef = useRef(0);

  useEffect(() => {
    assistantStateRef.current = assistantState;
  }, [assistantState]);

  useEffect(() => {
    speechInputModeRef.current = speechInputMode;
    if (speechInputMode !== "push_to_talk") {
      pushToTalkActiveRef.current = false;
      const timerId = window.setTimeout(() => {
        setIsPushToTalkActive(false);
      }, 0);
      return () => window.clearTimeout(timerId);
    }
    return undefined;
  }, [speechInputMode]);

  const refreshRuntime = useCallback(async () => {
    try {
      const [runtime, debug] = await Promise.all([
        apiRequest("/api/runtime"),
        apiRequest("/api/runtime/debug"),
      ]);
      setRuntimeInfo(runtime);
      setRuntimeDebug(debug);
    } catch (error) {
      console.warn("Unable to refresh runtime info:", error);
    }
  }, []);

  useEffect(() => {
    const timerId = window.setTimeout(() => {
      void refreshRuntime();
    }, 0);
    return () => window.clearTimeout(timerId);
  }, [refreshRuntime]);

  useEffect(() => {
    if (!isConnected) {
      return undefined;
    }
    const intervalId = window.setInterval(() => {
      void refreshRuntime();
    }, 2500);
    return () => window.clearInterval(intervalId);
  }, [isConnected, refreshRuntime]);

  const disconnectSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    isConnectedRef.current = false;
    setIsConnected(false);
    setIsConnecting(false);
    setAssistantState("idle");
  }, []);

  const clearAssistantPulse = useCallback(() => {
    if (assistantPulseTimerRef.current) {
      window.clearTimeout(assistantPulseTimerRef.current);
      assistantPulseTimerRef.current = null;
    }
  }, []);

  const pulseAssistantSpeaking = useCallback(() => {
    clearAssistantPulse();
    setAssistantState("speaking");
    assistantPulseTimerRef.current = window.setTimeout(() => {
      assistantPulseTimerRef.current = null;
      setAssistantState(isConnectedRef.current ? "listening" : "idle");
    }, 900);
  }, [clearAssistantPulse]);

  const ensurePlayback = useCallback(async () => {
    if (!playbackRef.current) {
      playbackRef.current = createLiveAudioPlayback();
    }
    await playbackRef.current.ensureContext();
  }, []);

  const closePlayback = useCallback(async () => {
    clearAssistantPulse();
    if (!playbackRef.current) {
      return;
    }
    await playbackRef.current.close();
    playbackRef.current = null;
  }, [clearAssistantPulse]);

  const sendSocketMessage = useCallback((payload) => {
    const socket = wsRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return false;
    }
    socket.send(JSON.stringify(payload));
    return true;
  }, []);

  const endSpeechTurn = useCallback(() => {
    speechChunkBufferRef.current = [];
    if (!speechTurnOpenRef.current) {
      speechSentChunkCountRef.current = 0;
      return;
    }
    speechTurnOpenRef.current = false;
    speechSentChunkCountRef.current = 0;
    awaitingAssistantTurnRef.current = true;
    sendSocketMessage({ type: "client.audio_end" });
  }, [sendSocketMessage]);

  const stopAudioRouter = useCallback(async () => {
    if (pushToTalkReleaseTimerRef.current) {
      window.clearTimeout(pushToTalkReleaseTimerRef.current);
      pushToTalkReleaseTimerRef.current = null;
    }
    pushToTalkActiveRef.current = false;
    setIsPushToTalkActive(false);
    speechTurnOpenRef.current = false;
    speechChunkBufferRef.current = [];
    speechSentChunkCountRef.current = 0;
    awaitingAssistantTurnRef.current = false;
    assistantSpeechGateUntilRef.current = 0;
    if (!audioRouterRef.current) {
      setLiveAudioMode("SILENCE");
      return;
    }
    const router = audioRouterRef.current;
    audioRouterRef.current = null;
    await router.stop();
    setLiveAudioMode("SILENCE");
    setLiveAudioLevels(buildInitialAudioLevels());
  }, []);

  const startAudioRouter = useCallback(async () => {
    if (!isConnectedRef.current || !micEnabled || audioRouterRef.current) {
      return;
    }

    const router = createLiveAudioRouter({
      onSpeechChunk: (pcmBytes) => {
        const suppressAutoSpeech =
          speechInputModeRef.current !== "push_to_talk" &&
          (awaitingAssistantTurnRef.current ||
            assistantStateRef.current === "speaking" ||
            performance.now() < assistantSpeechGateUntilRef.current);
        if (suppressAutoSpeech) {
          speechChunkBufferRef.current = [];
          speechSentChunkCountRef.current = 0;
          return;
        }
        if (
          speechInputModeRef.current === "push_to_talk" &&
          !pushToTalkActiveRef.current
        ) {
          return;
        }
        const requiredChunkCount =
          speechInputModeRef.current === "push_to_talk"
            ? PUSH_TO_TALK_MIN_SPEECH_CHUNKS
            : AUTO_MIN_SPEECH_CHUNKS;
        if (!speechTurnOpenRef.current) {
          speechChunkBufferRef.current.push(pcmBytes);
          if (speechChunkBufferRef.current.length < requiredChunkCount) {
            return;
          }
          const bufferedChunks = speechChunkBufferRef.current;
          speechChunkBufferRef.current = [];
          let acceptedCount = 0;
          for (const chunk of bufferedChunks) {
            const accepted = sendSocketMessage({
              type: "client.audio",
              mime: "audio/pcm;rate=16000",
              data_b64: bytesToBase64(chunk),
            });
            if (!accepted) {
              speechSentChunkCountRef.current = 0;
              return;
            }
            acceptedCount += 1;
          }
          speechTurnOpenRef.current = acceptedCount > 0;
          speechSentChunkCountRef.current = acceptedCount;
          awaitingAssistantTurnRef.current = false;
          return;
        }
        const accepted = sendSocketMessage({
          type: "client.audio",
          mime: "audio/pcm;rate=16000",
          data_b64: bytesToBase64(pcmBytes),
        });
        if (accepted) {
          speechSentChunkCountRef.current += 1;
        }
      },
      onSpeechPause: () => {
        if (speechInputModeRef.current === "push_to_talk") {
          return;
        }
        endSpeechTurn();
      },
      onLevels: (levels) => {
        setLiveAudioLevels(levels);
      },
      onModeChange: (mode) => {
        setLiveAudioMode(mode);
      },
    });

    audioRouterRef.current = router;
    try {
      await router.start();
    } catch (error) {
      audioRouterRef.current = null;
      setConnectionError(error instanceof Error ? error.message : "Microphone unavailable.");
    }
  }, [endSpeechTurn, micEnabled, sendSocketMessage]);

  const stopCameraCapture = useCallback(async () => {
    if (frameTimerRef.current) {
      window.clearInterval(frameTimerRef.current);
      frameTimerRef.current = null;
    }
    if (cameraStreamRef.current) {
      cameraStreamRef.current.getTracks().forEach((track) => track.stop());
      cameraStreamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }, []);

  const startCameraCapture = useCallback(async () => {
    if (!isConnectedRef.current || !cameraEnabled || cameraStreamRef.current) {
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
      cameraStreamRef.current = stream;
      const videoElement = videoRef.current;
      if (videoElement) {
        videoElement.srcObject = stream;
        await videoElement.play();
      }

      if (!cameraCanvasRef.current) {
        cameraCanvasRef.current = document.createElement("canvas");
      }
      const canvas = cameraCanvasRef.current;
      const context = canvas.getContext("2d");

      frameTimerRef.current = window.setInterval(() => {
        const video = videoRef.current;
        if (!context || !video || video.readyState < 2 || !isConnectedRef.current) {
          return;
        }
        const width = video.videoWidth || 1280;
        const height = video.videoHeight || 720;
        canvas.width = width;
        canvas.height = height;
        context.drawImage(video, 0, 0, width, height);
        const dataUrl = canvas.toDataURL("image/jpeg", 0.72);
        const [, dataB64 = ""] = dataUrl.split(",");
        if (!dataB64) {
          return;
        }
        sendSocketMessage({
          type: "client.video",
          mime: "image/jpeg",
          data_b64: dataB64,
        });
      }, CAMERA_FRAME_INTERVAL_MS);
    } catch (error) {
      setConnectionError(error instanceof Error ? error.message : "Camera unavailable.");
    }
  }, [cameraEnabled, sendSocketMessage]);

  useEffect(() => {
    if (isConnected && micEnabled) {
      const timerId = window.setTimeout(() => {
        void startAudioRouter();
      }, 0);
      return () => {
        window.clearTimeout(timerId);
        void stopAudioRouter();
      };
    } else {
      const timerId = window.setTimeout(() => {
        void stopAudioRouter();
      }, 0);
      return () => {
        window.clearTimeout(timerId);
      };
    }
  }, [isConnected, micEnabled, startAudioRouter, stopAudioRouter]);

  useEffect(() => {
    if (isConnected && cameraEnabled) {
      const timerId = window.setTimeout(() => {
        void startCameraCapture();
      }, 0);
      return () => {
        window.clearTimeout(timerId);
        void stopCameraCapture();
      };
    } else {
      const timerId = window.setTimeout(() => {
        void stopCameraCapture();
      }, 0);
      return () => {
        window.clearTimeout(timerId);
      };
    }
  }, [cameraEnabled, isConnected, startCameraCapture, stopCameraCapture]);

  useEffect(() => {
    return () => {
      disconnectSocket();
      void stopAudioRouter();
      void stopCameraCapture();
      void closePlayback();
    };
  }, [closePlayback, disconnectSocket, stopAudioRouter, stopCameraCapture]);

  const handleServerMessage = useCallback(
    async (rawMessage) => {
      const message = normalizeIncomingMessage(rawMessage);
      if (!message || typeof message !== "object") {
        return;
      }

      if (message.type === "server.audio") {
        awaitingAssistantTurnRef.current = false;
        assistantSpeechGateUntilRef.current = performance.now() + ASSISTANT_SPEECH_GATE_MS;
        if (playbackRef.current && message.data_b64) {
          await playbackRef.current.enqueue(message.data_b64, message.mime);
        }
        pulseAssistantSpeaking();
        return;
      }

      if (message.type === "server.status") {
        setConnectionMeta({
          sessionId: message.session_id || null,
          transport: message.transport || null,
          location: message.location || null,
          skill: message.skill || null,
        });
        setIsConnecting(false);
        setIsConnected(true);
        isConnectedRef.current = true;
        setAssistantState("listening");
        return;
      }

      if (message.type === "server.summary") {
        setSummary(message);
        return;
      }

      if (message.type === "error") {
        const text = normalizeText(message.message) || "Unknown live error.";
        setConnectionError(text);
        setMessages((items) =>
          upsertMessage(items, {
            id: makeMessageId("system", null, ++messageCounterRef.current),
            role: "system",
            text,
            partial: false,
          }),
        );
        return;
      }

      if (message.type === "server.transcript" || message.type === "server.text") {
        const role =
          message.type === "server.text"
            ? "assistant"
            : message.role === "user"
              ? "user"
              : "assistant";
        const turnId = typeof message.turn_id === "string" ? message.turn_id : null;
        const fallbackIndex = ++messageCounterRef.current;
        const text = normalizeText(message.text);
        if (!text) {
          return;
        }
        if (role === "user" && message.partial) {
          return;
        }
        setMessages((items) =>
          upsertMessage(items, {
            id: makeMessageId(role, turnId, fallbackIndex),
            role,
            text,
            partial: Boolean(message.partial) && !message.turn_complete,
          }),
        );
        if (role === "assistant") {
          awaitingAssistantTurnRef.current = false;
          assistantSpeechGateUntilRef.current = performance.now() + ASSISTANT_SPEECH_GATE_MS;
          pulseAssistantSpeaking();
        }
      }
    },
    [pulseAssistantSpeaking],
  );

  const startSession = useCallback(async () => {
    if (isConnecting || isConnected) {
      return;
    }

    setConnectionError("");
    setSummary(null);
    setMessages([]);
    setSessionProfile(null);
    setConnectionMeta(buildInitialConnectionMeta());
    setIsConnecting(true);
    awaitingAssistantTurnRef.current = false;
    assistantSpeechGateUntilRef.current = 0;
    speechChunkBufferRef.current = [];
    speechSentChunkCountRef.current = 0;

    try {
      await ensurePlayback();
      const normalized = await apiRequest("/api/live/session-profile", {
        method: "POST",
        body: {
          mode: profileDraft.mode,
          instrument: profileDraft.instrument,
          piece: profileDraft.piece,
          goal: profileDraft.goal,
          camera_expected: cameraEnabled,
        },
      });
      setSessionProfile(normalized.session_profile);

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const socket = new WebSocket(`${protocol}//${window.location.host}/ws/live`);

      socket.onopen = () => {
        socket.send(
          JSON.stringify({
            type: "client.init",
            ...normalized.session_profile,
          }),
        );
      };

      socket.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          void handleServerMessage(parsed);
        } catch (error) {
          console.warn("Ignoring non-JSON websocket frame:", error);
        }
      };

      socket.onerror = () => {
        setConnectionError("Live connection error.");
      };

      socket.onclose = () => {
        disconnectSocket();
        void refreshRuntime();
      };

      wsRef.current = socket;
    } catch (error) {
      setIsConnecting(false);
      setConnectionError(error instanceof Error ? error.message : "Unable to start session.");
    }
  }, [
    cameraEnabled,
    disconnectSocket,
    ensurePlayback,
    handleServerMessage,
    isConnected,
    isConnecting,
    profileDraft.goal,
    profileDraft.instrument,
    profileDraft.mode,
    profileDraft.piece,
    refreshRuntime,
  ]);

  const stopSession = useCallback(() => {
    if (!sendSocketMessage({ type: "client.stop" })) {
      disconnectSocket();
    }
  }, [disconnectSocket, sendSocketMessage]);

  const sendText = useCallback(() => {
    const text = normalizeText(conversationInput);
    if (!text) {
      return;
    }
    if (
      sendSocketMessage({
        type: "client.text",
        text,
      })
    ) {
      setConversationInput("");
    }
  }, [conversationInput, sendSocketMessage]);

  const toggleMic = useCallback(() => {
    setMicEnabled((value) => !value);
  }, []);

  const toggleCamera = useCallback(() => {
    setCameraEnabled((value) => !value);
  }, []);

  const beginPushToTalk = useCallback(() => {
    if (speechInputModeRef.current !== "push_to_talk" || !micEnabled || !isConnectedRef.current) {
      return;
    }
    if (pushToTalkReleaseTimerRef.current) {
      window.clearTimeout(pushToTalkReleaseTimerRef.current);
      pushToTalkReleaseTimerRef.current = null;
    }
    pushToTalkActiveRef.current = true;
    setIsPushToTalkActive(true);
    if (!audioRouterRef.current) {
      void startAudioRouter();
    }
  }, [micEnabled, startAudioRouter]);

  const endPushToTalk = useCallback(() => {
    if (speechInputModeRef.current !== "push_to_talk") {
      return;
    }
    setIsPushToTalkActive(false);
    if (pushToTalkReleaseTimerRef.current) {
      window.clearTimeout(pushToTalkReleaseTimerRef.current);
    }
    pushToTalkReleaseTimerRef.current = window.setTimeout(() => {
      pushToTalkReleaseTimerRef.current = null;
      pushToTalkActiveRef.current = false;
      endSpeechTurn();
    }, 140);
  }, [endSpeechTurn]);

  const resetSession = useCallback(() => {
    disconnectSocket();
    void stopAudioRouter();
    void stopCameraCapture();
    void closePlayback();
    setSessionProfile(null);
    setMessages([]);
    setSummary(null);
    setConnectionError("");
    setConversationInput("");
    setConnectionMeta(buildInitialConnectionMeta());
    setLiveAudioLevels(buildInitialAudioLevels());
    setLiveAudioMode("SILENCE");
    awaitingAssistantTurnRef.current = false;
    assistantSpeechGateUntilRef.current = 0;
    speechChunkBufferRef.current = [];
    speechSentChunkCountRef.current = 0;
  }, [closePlayback, disconnectSocket, stopAudioRouter, stopCameraCapture]);

  return {
    profileDraft,
    setProfileDraft,
    sessionProfile,
    runtimeInfo,
    runtimeDebug,
    messages,
    summary,
    connectionError,
    conversationInput,
    setConversationInput,
    isConnecting,
    isConnected,
    assistantState,
    micEnabled,
    cameraEnabled,
    liveAudioMode,
    liveAudioLevels,
    connectionMeta,
    videoRef,
    refreshRuntime,
    startSession,
    stopSession,
    sendText,
    toggleMic,
    toggleCamera,
    speechInputMode,
    setSpeechInputMode,
    isPushToTalkActive,
    beginPushToTalk,
    endPushToTalk,
    resetSession,
  };
}
