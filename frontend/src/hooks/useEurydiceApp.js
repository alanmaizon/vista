import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import useLiveConnection from "./useLiveConnection";
import { apiRequest } from "../lib/api";
import { bytesToBase64, capturePcmClip } from "../lib/audioCapture";
import { createLiveAudioPlayback } from "../lib/liveAudioPlayback";
import { createLiveAudioRouter } from "../lib/liveAudioRouter";
import { createLiveEventBus } from "../lib/liveEventBus";
import { playPhrase } from "../lib/playback";

function appendTimestamped(items, role, text) {
  return [...items, { role, text, id: `${Date.now()}-${items.length}` }];
}

function scoreIsDirty(scoreLine, activeScore) {
  if (!activeScore) {
    return true;
  }
  return scoreLine.trim() !== (activeScore.normalized ?? "").trim();
}

function buildPrimaryActionLabel({ activeScore, lessonState, scoreLine }) {
  if (!activeScore || scoreIsDirty(scoreLine, activeScore)) {
    return "Prepare lesson";
  }
  if (lessonState.stage === "awaiting-compare") {
    return "Compare bar";
  }
  if (lessonState.stage === "reviewed") {
    return "Next bar";
  }
  if (lessonState.stage === "complete") {
    return "Restart lesson";
  }
  return "Start lesson";
}

function initialLessonState() {
  return {
    stage: "idle",
    measureIndex: null,
    totalMeasures: 0,
    noteStartIndex: null,
    noteEndIndex: null,
    prompt: "",
  };
}

function generateToolCallId() {
  if (window?.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  return `tool-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function generateConversationId(prefix = "msg") {
  if (window?.crypto?.randomUUID) {
    return `${prefix}-${window.crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function normalizeRouterEventNotes(event) {
  if (event?.type === "NOTE_PLAYED" && event.pitch) {
    return [event.pitch];
  }
  if (event?.type === "PHRASE_PLAYED" && Array.isArray(event.notes)) {
    return event.notes.filter(Boolean);
  }
  return [];
}

function buildTraceMismatch(event, payload) {
  if (!payload) {
    return { mismatch: false, mismatchReason: null };
  }
  const routerNotes = normalizeRouterEventNotes(event);
  const deterministicNotes = Array.isArray(payload.notes)
    ? payload.notes.map((item) => item?.note_name).filter(Boolean)
    : [];

  if (event?.type === "PHRASE_PLAYED") {
    if (!deterministicNotes.length) {
      return { mismatch: true, mismatchReason: "deterministic_empty_phrase" };
    }
    if (!routerNotes.length) {
      return { mismatch: true, mismatchReason: "router_empty_phrase" };
    }
    if (routerNotes.join("|") !== deterministicNotes.join("|")) {
      return { mismatch: true, mismatchReason: "router_phrase_note_mismatch" };
    }
  }

  return { mismatch: false, mismatchReason: null };
}

export default function useEurydiceApp() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [user, setUser] = useState(null);
  const [authStatus, setAuthStatus] = useState("Checking session...");
  const [status, setStatus] = useState("Ready.");
  const [errorMessage, setErrorMessage] = useState("");
  const [captions, setCaptions] = useState([]);
  const [conversationMessages, setConversationMessages] = useState([]);
  const [micEnabled, setMicEnabled] = useState(true);
  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [instrumentProfile, setInstrumentProfile] = useState("AUTO");
  const [scoreLine, setScoreLine] = useState("C4/q D4/q D4/q");
  const [activeScore, setActiveScore] = useState(null);
  const [lessonState, setLessonState] = useState(initialLessonState);
  const [analysis, setAnalysis] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [userSkillProfile, setUserSkillProfile] = useState(null);
  const [nextDrills, setNextDrills] = useState([]);
  const [tutorPrompt, setTutorPrompt] = useState("");
  const [runtimeStatus, setRuntimeStatus] = useState({
    verovioAvailable: null,
    verovioDetail: "",
    crepeAvailable: null,
    crepeDetail: "",
  });
  const [liveToolMetrics, setLiveToolMetrics] = useState({
    total_calls: 0,
    total_successes: 0,
    total_failures: 0,
    overall_success_rate: 0,
    failure_kinds: {},
    metrics: [],
    recent_calls: [],
  });
  const [sessionId, setSessionId] = useState(null);
  const [liveMode, setLiveMode] = useState(null);
  const [liveAudioMode, setLiveAudioMode] = useState("SILENCE");
  const [liveAudioLevels, setLiveAudioLevels] = useState({
    energyDb: -90,
    speechConfidence: 0,
    musicConfidence: 0,
    speechActive: false,
    pitchHz: null,
    pitchConfidence: 0,
  });
  const [recentMusicEvents, setRecentMusicEvents] = useState([]);
  const [interruptState, setInterruptState] = useState({
    status: "idle",
    pendingType: null,
    pendingSummary: "",
    queuedCount: 0,
    lastDetectedAt: null,
    lastFlushedAt: null,
  });
  const [cameraCapturePending, setCameraCapturePending] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [tempoOverride, setTempoOverride] = useState("");
  const [playbackAudioElement, setPlaybackAudioElement] = useState(null);
  const [orbLowPower, setOrbLowPower] = useState(true);

  const videoRef = useRef(null);
  const cameraStreamRef = useRef(null);
  const frameTimerRef = useRef(null);
  const runLessonActionRef = useRef(null);
  const stopLiveSessionRef = useRef(() => {});
  const liveMessageHandlerRef = useRef(async () => {});
  const pendingToolCallsRef = useRef(new Map());
  const isConnectedRef = useRef(false);
  const liveModeRef = useRef(null);
  const liveAudioRouterRef = useRef(null);
  const liveAudioPlaybackRef = useRef(null);
  const liveEventBusRef = useRef(createLiveEventBus());
  const conversationStreamRefs = useRef({ assistant: null, user: null });
  const assistantStreamingRef = useRef(false);
  const liveAudioLevelsRef = useRef({
    energyDb: -90,
    speechConfidence: 0,
    musicConfidence: 0,
    speechActive: false,
    pitchHz: null,
    pitchConfidence: 0,
  });
  const lastAssistantAudioAtRef = useRef(0);
  const pendingMusicInterruptRef = useRef(null);
  const musicInterruptTimerRef = useRef(null);
  const autoTutorStartRef = useRef(false);
  const musicAnalysisInFlightRef = useRef(false);
  const captureFocusedMusicClipRef = useRef((options) => capturePcmClip(options));

  const appendCaption = useCallback((role, text) => {
    if (!text) {
      return;
    }
    setCaptions((items) => appendTimestamped(items, role, text));
  }, []);

  const appendConversationMessage = useCallback((role, text, { kind = "message", streaming = false } = {}) => {
    if (!text) {
      return;
    }
    setConversationMessages((items) => [
      ...items,
      {
        id: generateConversationId(role),
        role,
        text,
        kind,
        streaming,
      },
    ]);
  }, []);

  const upsertConversationStream = useCallback((role, text, { kind = "speech", final = false } = {}) => {
    if (!text) {
      return;
    }

    const activeId = conversationStreamRefs.current[role];
    const messageId = activeId || generateConversationId(`${role}-stream`);
    if (!activeId && !final) {
      conversationStreamRefs.current[role] = messageId;
    }

    setConversationMessages((items) => {
      const index = items.findIndex((item) => item.id === messageId);
      if (index === -1) {
        return [
          ...items,
          {
            id: messageId,
            role,
            text,
            kind,
            streaming: !final,
          },
        ];
      }

      const nextItems = [...items];
      nextItems[index] = {
        ...nextItems[index],
        text,
        kind,
        streaming: !final,
      };
      return nextItems;
    });

    if (final) {
      conversationStreamRefs.current[role] = null;
    }
  }, []);

  const finalizeAssistantMessage = useCallback((text) => {
    if (!text) {
      return;
    }

    const activeId = conversationStreamRefs.current.assistant;
    setConversationMessages((items) => {
      if (activeId) {
        return items.map((item) =>
          item.id === activeId
            ? {
                ...item,
                text,
                kind: "assistant",
                streaming: false,
              }
            : item,
        );
      }

      const lastMessage = items.at(-1);
      if (lastMessage?.role === "assistant" && lastMessage.text === text) {
        return items;
      }

      return [
        ...items,
        {
          id: generateConversationId("assistant"),
          role: "assistant",
          text,
          kind: "assistant",
          streaming: false,
        },
      ];
    });
    conversationStreamRefs.current.assistant = null;
  }, []);

  const resetLessonState = useCallback(() => {
    setLessonState(initialLessonState());
    setComparison(null);
    setUserSkillProfile(null);
    setNextDrills([]);
    setTutorPrompt("");
  }, []);

  const stopCameraCapture = useCallback(() => {
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

  const rejectPendingToolCalls = useCallback((reason) => {
    const pending = pendingToolCallsRef.current;
    for (const [callId, entry] of pending.entries()) {
      window.clearTimeout(entry.timeoutId);
      entry.reject(new Error(reason || `Tool call timed out (${callId}).`));
    }
    pending.clear();
  }, []);

  const { connect, disconnect, send, isConnected } = useLiveConnection({
    onMessage: (data) => {
      void liveMessageHandlerRef.current(data);
    },
    onClose: () => {
      rejectPendingToolCalls("Live session closed before tool response.");
      stopCameraCapture();
      setLiveMode(null);
      setSessionId(null);
      setCameraCapturePending(false);
      conversationStreamRefs.current.assistant = null;
      conversationStreamRefs.current.user = null;
      assistantStreamingRef.current = false;
      pendingMusicInterruptRef.current = null;
      if (musicInterruptTimerRef.current) {
        window.clearTimeout(musicInterruptTimerRef.current);
        musicInterruptTimerRef.current = null;
      }
      setInterruptState({
        status: "idle",
        pendingType: null,
        pendingSummary: "",
        queuedCount: 0,
        lastDetectedAt: null,
        lastFlushedAt: null,
      });
      setStatus("Live session closed.");
    },
    onError: () => {
      rejectPendingToolCalls("Live connection error before tool response.");
      setStatus("Live connection error.");
    },
  });

  useEffect(() => {
    isConnectedRef.current = isConnected;
  }, [isConnected]);

  useEffect(() => {
    liveModeRef.current = liveMode;
  }, [liveMode]);

  useEffect(() => {
    liveAudioLevelsRef.current = liveAudioLevels;
  }, [liveAudioLevels]);

  const applyPreparedScorePayload = useCallback(
    (payload) => {
      setActiveScore(payload);
      resetLessonState();
      setAnalysis(null);
      setComparison(null);
      setStatus("Notation ready.");
      appendCaption(
        "Render",
        payload.render_backend === "VEROVIO"
          ? "Rendered notation with Verovio."
          : "Verovio was unavailable, so MusicXML fallback is shown.",
      );
      for (const warning of payload.warnings ?? []) {
        appendCaption("Warning", warning);
      }
    },
    [appendCaption, resetLessonState],
  );

  const applyLessonPayload = useCallback(
    (payload) => {
      setLessonState({
        stage: payload.lesson_stage,
        measureIndex: payload.measure_index,
        totalMeasures: payload.total_measures,
        noteStartIndex: payload.note_start_index,
        noteEndIndex: payload.note_end_index,
        prompt: payload.prompt,
      });
      setStatus(payload.status);
      appendCaption("Lesson", payload.prompt);
      appendConversationMessage("system", payload.prompt, { kind: "lesson" });
    },
    [appendCaption, appendConversationMessage],
  );

  const applyComparisonPayload = useCallback(
    (payload) => {
      setComparison(payload);
      setStatus(payload.needs_replay ? "Replay requested." : "Comparison ready.");
      appendCaption("Compare", payload.summary);
      appendConversationMessage("assistant", payload.summary, { kind: "analysis" });
      for (const mismatch of payload.mismatches ?? []) {
        appendCaption("Difference", mismatch);
      }
      for (const warning of payload.warnings ?? []) {
        appendCaption("Warning", warning);
      }
      setLessonState((current) => ({
        ...current,
        stage: payload.needs_replay || !payload.match ? "awaiting-compare" : "reviewed",
      }));
    },
    [appendCaption, appendConversationMessage],
  );

  useEffect(() => {
    let active = true;
    async function loadSessionUser() {
      try {
        const payload = await apiRequest("/api/auth/me");
        if (!active) {
          return;
        }
        setUser(payload);
        autoTutorStartRef.current = false;
        conversationStreamRefs.current.assistant = null;
        conversationStreamRefs.current.user = null;
        setAuthStatus(`Signed in as ${payload.email || payload.uid}`);
        setStatus("Signed in.");
      } catch {
        if (!active) {
          return;
        }
        setUser(null);
        autoTutorStartRef.current = false;
        setConversationMessages([]);
        conversationStreamRefs.current.assistant = null;
        conversationStreamRefs.current.user = null;
        assistantStreamingRef.current = false;
        setRecentMusicEvents([]);
        setInterruptState({
          status: "idle",
          pendingType: null,
          pendingSummary: "",
          queuedCount: 0,
          lastDetectedAt: null,
          lastFlushedAt: null,
        });
        setAuthStatus("Signed out. Click Sign In.");
      }
    }
    void loadSessionUser();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!user) {
      return undefined;
    }

    let active = true;
    async function loadRuntime() {
      try {
        const payload = await apiRequest("/api/music/runtime");
        if (!active) {
          return;
        }
        setRuntimeStatus({
          verovioAvailable: Boolean(payload?.verovio_available),
          verovioDetail: payload?.verovio_detail || "",
          crepeAvailable: Boolean(payload?.crepe_available),
          crepeDetail: payload?.crepe_detail || "",
        });
      } catch {
        if (active) {
          setRuntimeStatus((current) => ({
            ...current,
            verovioDetail: "Runtime status unavailable.",
          }));
        }
      }
    }
    void loadRuntime();
    return () => {
      active = false;
    };
  }, [user]);

  useEffect(() => {
    if (!isConnected || liveMode !== "READ_SCORE" || !cameraEnabled) {
      stopCameraCapture();
      return undefined;
    }

    let cancelled = false;
    async function startCameraCapture() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: "environment" },
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        cameraStreamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          void videoRef.current.play().catch(() => {});
        }

        frameTimerRef.current = window.setInterval(() => {
          const video = videoRef.current;
          if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
            return;
          }
          const canvas = document.createElement("canvas");
          canvas.width = video.videoWidth || 1280;
          canvas.height = video.videoHeight || 720;
          const context = canvas.getContext("2d");
          if (!context) {
            return;
          }
          context.drawImage(video, 0, 0, canvas.width, canvas.height);
          const base64Data = canvas.toDataURL("image/jpeg", 0.72).split(",", 2)[1];
          if (!base64Data) {
            return;
          }
          send({
            type: "client.video",
            mime: "image/jpeg",
            data_b64: base64Data,
          });
        }, 1000);
      } catch {
        setErrorMessage("Unable to access the camera. Check permissions and try again.");
        setStatus("Camera unavailable.");
      }
    }

    void startCameraCapture();
    return () => {
      cancelled = true;
      stopCameraCapture();
    };
  }, [cameraEnabled, isConnected, liveMode, send, stopCameraCapture]);

  useEffect(() => () => {
    stopCameraCapture();
  }, [stopCameraCapture]);

  useEffect(() => () => {
    rejectPendingToolCalls("Session context disposed before tool response.");
  }, [rejectPendingToolCalls]);

  const handleSignIn = useCallback(async () => {
    setErrorMessage("");
    try {
      const payload = await apiRequest("/api/auth/login", {
        method: "POST",
        body: {
          email: email.trim() || null,
          password: password || null,
        },
      });
      setUser(payload);
      autoTutorStartRef.current = false;
      setConversationMessages([]);
      conversationStreamRefs.current.assistant = null;
      conversationStreamRefs.current.user = null;
      assistantStreamingRef.current = false;
      setRecentMusicEvents([]);
      setInterruptState({
        status: "idle",
        pendingType: null,
        pendingSummary: "",
        queuedCount: 0,
        lastDetectedAt: null,
        lastFlushedAt: null,
      });
      setAuthStatus(`Signed in as ${payload.email || payload.uid}`);
      setStatus("Signed in.");
      return true;
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Sign-in failed.");
      setStatus("Sign-in failed.");
      return false;
    }
  }, [email, password]);

  const loadLiveToolMetrics = useCallback(async () => {
    if (!user) {
      return;
    }
    try {
      const payload = await apiRequest("/api/music/analytics/live-tools");
      setLiveToolMetrics({
        total_calls: Number(payload?.total_calls || 0),
        total_successes: Number(payload?.total_successes || 0),
        total_failures: Number(payload?.total_failures || 0),
        overall_success_rate: Number(payload?.overall_success_rate || 0),
        failure_kinds:
          payload?.failure_kinds && typeof payload.failure_kinds === "object"
            ? payload.failure_kinds
            : {},
        metrics: Array.isArray(payload?.metrics) ? payload.metrics : [],
        recent_calls: Array.isArray(payload?.recent_calls) ? payload.recent_calls : [],
      });
    } catch {
      // Keep the latest snapshot visible if telemetry fetch fails.
    }
  }, [user]);

  const reportLiveAudioTrace = useCallback(
    async ({ event, deterministicPayload = null, mismatch = false, mismatchReason = null }) => {
      if (!user || !event?.type) {
        return;
      }
      const levels = liveAudioLevelsRef.current;
      try {
        await apiRequest("/api/music/analytics/live-audio-trace", {
          method: "POST",
          body: {
            session_id: sessionId,
            event_type: event.type,
            router_mode: liveAudioMode || "SILENCE",
            speech_active: Boolean(levels.speechActive),
            speech_confidence: levels.speechConfidence,
            music_confidence: levels.musicConfidence,
            pitch_hz: levels.pitchHz,
            pitch_confidence: levels.pitchConfidence,
            router_summary: {
              pitch: event.pitch || null,
              notes: Array.isArray(event.notes) ? event.notes : normalizeRouterEventNotes(event),
              tempo: event.tempo || null,
              pattern: Array.isArray(event.pattern) ? event.pattern : null,
              confidence: event.confidence || null,
            },
            deterministic_summary: deterministicPayload
              ? {
                  kind: deterministicPayload.kind || null,
                  notes: Array.isArray(deterministicPayload.notes)
                    ? deterministicPayload.notes.map((item) => item?.note_name).filter(Boolean)
                    : [],
                  confidence: deterministicPayload.confidence || null,
                  summary: deterministicPayload.summary || null,
                }
              : null,
            mismatch,
            mismatch_reason: mismatchReason,
          },
        });
      } catch {
        // Trace reporting must never block live tutoring.
      }
    },
    [liveAudioMode, sessionId, user],
  );

  useEffect(() => {
    if (!user) {
      setLiveToolMetrics({
        total_calls: 0,
        total_successes: 0,
        total_failures: 0,
        overall_success_rate: 0,
        failure_kinds: {},
        metrics: [],
        recent_calls: [],
      });
      return undefined;
    }
    void loadLiveToolMetrics();
    return undefined;
  }, [loadLiveToolMetrics, user]);

  const ensureGuidedLessonSession = useCallback(async () => {
    if (!user) {
      throw new Error("Sign in before starting the guided lesson.");
    }
    if (liveMode === "READ_SCORE" && isConnectedRef.current) {
      throw new Error("Stop camera reader before running guided lesson tools.");
    }
    if (!isConnectedRef.current || liveMode !== "GUIDED_LESSON" || !sessionId) {
      setStatus("Creating Gemini Live tutor...");
      const session = await apiRequest("/api/sessions", {
        method: "POST",
        body: {
          domain: "MUSIC",
          mode: "GUIDED_LESSON",
          goal: "Act as a conversational music tutor. Greet the user, listen to speech and played phrases, and use score or comparison tools when relevant.",
        },
      });
      setSessionId(session.id);
      setLiveMode("GUIDED_LESSON");
      connect({
        sessionId: session.id,
        mode: "GUIDED_LESSON",
      });
      setStatus("Opening Gemini Live tutor...");
    }

    const start = Date.now();
    while (!isConnectedRef.current) {
      if (Date.now() - start > 6000) {
        throw new Error("Timed out waiting for guided lesson live connection.");
      }
      await new Promise((resolve) => window.setTimeout(resolve, 120));
    }
  }, [connect, liveMode, sessionId, user]);

  const invokeLiveTool = useCallback(
    async (name, args, { sendToModel = false } = {}) => {
      await ensureGuidedLessonSession();
      const callId = generateToolCallId();
      const payload = await new Promise((resolve, reject) => {
        const timeoutId = window.setTimeout(() => {
          pendingToolCallsRef.current.delete(callId);
          reject(new Error(`Tool call timed out: ${name}`));
        }, 20000);
        pendingToolCallsRef.current.set(callId, { resolve, reject, timeoutId, name });
        send({
          type: "client.tool",
          call_id: callId,
          name,
          args,
          send_to_model: Boolean(sendToModel),
        });
      });
      return payload;
    },
    [ensureGuidedLessonSession, send],
  );

  const startTutorSession = useCallback(async () => {
    setErrorMessage("");
    await ensureGuidedLessonSession();
  }, [ensureGuidedLessonSession]);

  const runLessonAction = useCallback(
    async ({ sourceTextOverride = null, forcedPrepare = false } = {}) => {
      setErrorMessage("");
      if (!user) {
        throw new Error("Sign in before starting the guided lesson.");
      }

      const currentScoreLine = (sourceTextOverride ?? scoreLine).trim();
      const prepared = activeScore && !scoreIsDirty(currentScoreLine, activeScore);
      const awaitingCompare = prepared && lessonState.stage === "awaiting-compare" && !forcedPrepare;

      let body;
      if (!prepared || forcedPrepare) {
        if (!currentScoreLine) {
          throw new Error("Enter a score line before preparing the lesson.");
        }
        setStatus("Preparing lesson...");
        body = {
          source_text: currentScoreLine,
          time_signature: "4/4",
          lesson_stage: "idle",
          instrument_profile: instrumentProfile,
        };
      } else if (awaitingCompare) {
        if (!micEnabled) {
          throw new Error("Turn the microphone on before comparing this bar.");
        }
        setStatus("Recording a comparison take...");
        const clip = await captureFocusedMusicClipRef.current({ durationMs: 2800, mode: "music" });
        setStatus("Comparing bar...");
        body = {
          score_id: activeScore.score_id,
          current_measure_index: lessonState.measureIndex,
          lesson_stage: "awaiting-compare",
          audio_b64: clip.audioB64,
          mime: clip.mime,
          max_notes: 12,
          instrument_profile: instrumentProfile,
        };
      } else {
        setStatus("Loading lesson step...");
        body = {
          score_id: activeScore.score_id,
          current_measure_index: lessonState.measureIndex,
          lesson_stage: lessonState.stage === "complete" ? "complete" : lessonState.stage || "idle",
          instrument_profile: instrumentProfile,
        };
      }

      const payload = await invokeLiveTool("lesson_action", body);

      if (payload?.score) {
        applyPreparedScorePayload(payload.score);
      }
      if (payload?.lesson) {
        applyLessonPayload(payload.lesson);
      }
      if (payload?.comparison) {
        applyComparisonPayload(payload.comparison);
      }
      if (payload?.user_skill_profile) {
        setUserSkillProfile(payload.user_skill_profile);
      }
      if (Array.isArray(payload?.next_drills)) {
        setNextDrills(payload.next_drills);
      }
      if (typeof payload?.tutor_prompt === "string") {
        setTutorPrompt(payload.tutor_prompt);
      }
    },
    [
      activeScore,
      applyComparisonPayload,
      applyLessonPayload,
      applyPreparedScorePayload,
      lessonState.measureIndex,
      lessonState.stage,
      micEnabled,
      instrumentProfile,
      invokeLiveTool,
      scoreLine,
      user,
    ],
  );

  const handleHearPhrase = useCallback(async () => {
    setErrorMessage("");
    if (!user) {
      throw new Error("Sign in before capturing a phrase.");
    }
    if (!micEnabled) {
      throw new Error("Turn the microphone on before capturing a phrase.");
    }
    setStatus("Recording a short phrase...");
    const clip = await captureFocusedMusicClipRef.current({ mode: "music" });
    setStatus("Transcribing phrase...");
    const payload = await apiRequest("/api/music/transcribe", {
      method: "POST",
      body: {
        audio_b64: clip.audioB64,
        mime: clip.mime,
        expected: "AUTO",
        max_notes: 8,
        instrument_profile: instrumentProfile,
      },
    });
    setAnalysis(payload);
    setStatus("Transcription ready.");
    appendConversationMessage("assistant", payload.summary || "Phrase analysed.", {
      kind: "analysis",
    });
    appendCaption("Transcription", payload.summary || "Phrase analysed.");
    for (const warning of payload.warnings ?? []) {
      appendCaption("Warning", warning);
    }
  }, [appendCaption, appendConversationMessage, instrumentProfile, micEnabled, user]);

  const startReadScoreSession = useCallback(async () => {
    setErrorMessage("");
    if (!user) {
      throw new Error("Sign in before reading a score.");
    }
    if (!cameraEnabled) {
      throw new Error("Turn the camera on before reading a score.");
    }
    if (isConnected) {
      rejectPendingToolCalls("Live mode changed before tool response.");
      disconnect();
      setLiveMode(null);
      setSessionId(null);
      stopCameraCapture();
    }
    setStatus("Creating live score reader...");
    const session = await apiRequest("/api/sessions", {
      method: "POST",
      body: {
        domain: "MUSIC",
        mode: "READ_SCORE",
        goal: "Read one short bar from the visible sheet and emit NOTE_LINE when it is readable.",
      },
    });
    setSessionId(session.id);
    setLiveMode("READ_SCORE");
    setCameraCapturePending(true);
    connect({
      sessionId: session.id,
      mode: "READ_SCORE",
    });
    setStatus("Opening live score reader...");
    appendCaption("Setup", "Keep one short bar centered and steady until Eurydice captures a NOTE_LINE.");
  }, [
    appendCaption,
    cameraEnabled,
    connect,
    disconnect,
    isConnected,
    rejectPendingToolCalls,
    stopCameraCapture,
    user,
  ]);

  const stopLiveSession = useCallback(() => {
    rejectPendingToolCalls("Live session stopped before tool response.");
    if (isConnected) {
      send({ type: "client.stop" });
    }
    disconnect();
    setLiveMode(null);
    setSessionId(null);
    setCameraCapturePending(false);
    stopCameraCapture();
    conversationStreamRefs.current.assistant = null;
    conversationStreamRefs.current.user = null;
    assistantStreamingRef.current = false;
    if (musicInterruptTimerRef.current) {
      window.clearTimeout(musicInterruptTimerRef.current);
      musicInterruptTimerRef.current = null;
    }
    pendingMusicInterruptRef.current = null;
    setInterruptState({
      status: "idle",
      pendingType: null,
      pendingSummary: "",
      queuedCount: 0,
      lastDetectedAt: null,
      lastFlushedAt: null,
    });
    setStatus("Live session stopped.");
  }, [disconnect, isConnected, rejectPendingToolCalls, send, stopCameraCapture]);

  const sendLiveText = useCallback(
    (text) => {
      const trimmed = text?.trim();
      if (!trimmed || !isConnectedRef.current || liveModeRef.current !== "GUIDED_LESSON") {
        return;
      }
      send({
        type: "client.text",
        text: trimmed,
      });
    },
    [send],
  );

  const flushPendingMusicInterrupt = useCallback(() => {
    const pending = pendingMusicInterruptRef.current;
    if (!pending) {
      return;
    }
    pendingMusicInterruptRef.current = null;
    setInterruptState((current) => ({
      ...current,
      status: "flushing",
      queuedCount: 0,
      pendingType: pending.type,
      pendingSummary: pending.summary,
      lastFlushedAt: Date.now(),
    }));
    sendLiveText(pending.text);
  }, [sendLiveText]);

  const queueMusicInterrupt = useCallback(
    ({ text, type, summary }) => {
      if (!text) {
        return;
      }
      const now = Date.now();
      const queuedCount = pendingMusicInterruptRef.current
        ? (pendingMusicInterruptRef.current.count || 1) + 1
        : 1;
      pendingMusicInterruptRef.current = {
        text,
        type,
        summary,
        count: queuedCount,
        queuedAt: now,
      };
      setInterruptState((current) => ({
        ...current,
        status: "queued",
        pendingType: type,
        pendingSummary: summary,
        queuedCount,
        lastDetectedAt: now,
      }));
      if (musicInterruptTimerRef.current) {
        window.clearTimeout(musicInterruptTimerRef.current);
      }
      const speakingRecently =
        assistantStreamingRef.current || Date.now() - lastAssistantAudioAtRef.current < 700;
      musicInterruptTimerRef.current = window.setTimeout(() => {
        musicInterruptTimerRef.current = null;
        flushPendingMusicInterrupt();
      }, speakingRecently ? 760 : 320);
    },
    [flushPendingMusicInterrupt],
  );

  const handleMusicEvent = useCallback(
    async (event) => {
      if (!event || typeof event !== "object") {
        return;
      }

      setRecentMusicEvents((items) => [event, ...items].slice(0, 6));

      if (event.type === "NOTE_PLAYED") {
        appendConversationMessage("music", `Note detected: ${event.pitch}`, { kind: "music" });
        void reportLiveAudioTrace({ event });
        queueMusicInterrupt({
          text: `A music interrupt just occurred: NOTE_PLAYED pitch=${event.pitch} confidence=${Math.round(
            Number(event.confidence || 0) * 100,
          )}%. Respond briefly once your current sentence ends.`,
          type: event.type,
          summary: `Note ${event.pitch}`,
        });
        return;
      }

      if (event.type === "RHYTHM_PATTERN") {
        appendConversationMessage(
          "music",
          `Rhythm detected at ${event.tempo || "?"} BPM`,
          { kind: "music" },
        );
        void reportLiveAudioTrace({ event });
        queueMusicInterrupt({
          text: `A rhythm interrupt just occurred: RHYTHM_PATTERN tempo=${event.tempo || "unknown"} BPM pattern=${Array.isArray(
            event.pattern,
          ) ? event.pattern.join("-") : "unknown"}. Give one short coaching response.`,
          type: event.type,
          summary: `Rhythm ${event.tempo || "?"} BPM`,
        });
        return;
      }

      if (event.type !== "PHRASE_PLAYED") {
        return;
      }

      appendConversationMessage("music", `Phrase detected: ${event.notes.join(" · ")}`, {
        kind: "music",
      });

      if (!user || musicAnalysisInFlightRef.current) {
        void reportLiveAudioTrace({ event });
        queueMusicInterrupt({
          text: `A phrase interrupt just occurred: PHRASE_PLAYED notes=${event.notes.join(",")}. Acknowledge it briefly and continue the lesson.`,
          type: event.type,
          summary: `Phrase ${event.notes.join(" · ")}`,
        });
        return;
      }

      musicAnalysisInFlightRef.current = true;
      try {
        const payload = await apiRequest("/api/music/transcribe", {
          method: "POST",
          body: {
            audio_b64: event.audioB64,
            mime: event.mime,
            expected: "AUTO",
            max_notes: 8,
            instrument_profile: instrumentProfile,
          },
        });
        setAnalysis(payload);
        setStatus("Live phrase analysed.");
        appendConversationMessage("assistant", payload.summary || "Phrase analysed.", {
          kind: "analysis",
        });
        appendCaption("Analysis", payload.summary || "Phrase analysed.");
        {
          const traceDecision = buildTraceMismatch(event, payload);
          void reportLiveAudioTrace({
            event,
            deterministicPayload: payload,
            mismatch: traceDecision.mismatch,
            mismatchReason: traceDecision.mismatchReason,
          });
        }
        queueMusicInterrupt({
          text: `A phrase interrupt just occurred. Deterministic analysis summary: ${
            payload.summary || "Phrase analysed."
          } Respond briefly using that evidence.`,
          type: event.type,
          summary: payload.summary || `Phrase ${event.notes.join(" · ")}`,
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Unable to analyse live phrase.";
        appendConversationMessage("system", message, { kind: "warning" });
      } finally {
        musicAnalysisInFlightRef.current = false;
      }
    },
    [
      appendCaption,
      appendConversationMessage,
      instrumentProfile,
      queueMusicInterrupt,
      reportLiveAudioTrace,
      user,
    ],
  );

  useEffect(() => {
    runLessonActionRef.current = runLessonAction;
  }, [runLessonAction]);

  useEffect(() => {
    stopLiveSessionRef.current = stopLiveSession;
  }, [stopLiveSession]);

  useEffect(() => {
    const eventBus = liveEventBusRef.current;
    const unsubscribeNote = eventBus.on("music.note", (event) => {
      void handleMusicEvent(event);
    });
    const unsubscribePhrase = eventBus.on("music.phrase", (event) => {
      void handleMusicEvent(event);
    });
    const unsubscribeRhythm = eventBus.on("music.rhythm", (event) => {
      void handleMusicEvent(event);
    });

    return () => {
      unsubscribeNote();
      unsubscribePhrase();
      unsubscribeRhythm();
    };
  }, [handleMusicEvent]);

  useEffect(() => {
    if (!user || autoTutorStartRef.current) {
      return undefined;
    }
    autoTutorStartRef.current = true;
    window.setTimeout(() => {
      void startTutorSession().catch((error) => {
        setErrorMessage(error instanceof Error ? error.message : "Unable to start Gemini Live.");
      });
    }, 180);
    return undefined;
  }, [startTutorSession, user]);

  const startLiveAudioRouter = useCallback(async () => {
    if (!user || !micEnabled || !isConnectedRef.current || liveModeRef.current !== "GUIDED_LESSON") {
      return;
    }
    if (liveAudioRouterRef.current) {
      return;
    }

    const router = createLiveAudioRouter({
      eventBus: liveEventBusRef.current,
      onSpeechChunk: (pcmBytes) => {
        if (!isConnectedRef.current || liveModeRef.current !== "GUIDED_LESSON") {
          return;
        }
        send({
          type: "client.audio",
          mime: "audio/pcm;rate=16000",
          data_b64: bytesToBase64(pcmBytes),
        });
      },
      onLevels: (levels) => {
        setLiveAudioLevels(levels);
      },
      onModeChange: (mode) => {
        setLiveAudioMode(mode);
      },
    });

    liveAudioRouterRef.current = router;
    try {
      await router.start();
    } catch (error) {
      if (liveAudioRouterRef.current === router) {
        liveAudioRouterRef.current = null;
      }
      setErrorMessage(error instanceof Error ? error.message : "Unable to access the microphone.");
      setStatus("Microphone unavailable.");
    }
  }, [micEnabled, send, user]);

  const stopLiveAudioRouter = useCallback(async () => {
    if (!liveAudioRouterRef.current) {
      setLiveAudioMode("SILENCE");
      return;
    }
    const router = liveAudioRouterRef.current;
    liveAudioRouterRef.current = null;
    await router.stop();
    setLiveAudioMode("SILENCE");
  }, []);

  const captureFocusedMusicClip = useCallback(
    async (options) => {
      const shouldResumeLiveRouter = Boolean(liveAudioRouterRef.current);
      if (shouldResumeLiveRouter) {
        await stopLiveAudioRouter();
      }
      try {
        return await capturePcmClip(options);
      } finally {
        if (shouldResumeLiveRouter) {
          await startLiveAudioRouter();
        }
      }
    },
    [startLiveAudioRouter, stopLiveAudioRouter],
  );

  useEffect(() => {
    captureFocusedMusicClipRef.current = captureFocusedMusicClip;
  }, [captureFocusedMusicClip]);

  useEffect(() => {
    if (!user || !micEnabled || !isConnected || liveMode !== "GUIDED_LESSON") {
      void stopLiveAudioRouter();
      return undefined;
    }

    void startLiveAudioRouter();

    return () => {
      void stopLiveAudioRouter();
    };
  }, [isConnected, liveMode, micEnabled, startLiveAudioRouter, stopLiveAudioRouter, user]);

  useEffect(() => {
    const playback = createLiveAudioPlayback();
    const eventBus = liveEventBusRef.current;
    liveAudioPlaybackRef.current = playback;
    return () => {
      if (musicInterruptTimerRef.current) {
        window.clearTimeout(musicInterruptTimerRef.current);
      }
      pendingMusicInterruptRef.current = null;
      eventBus.clear();
      void stopLiveAudioRouter();
      if (liveAudioPlaybackRef.current === playback) {
        void playback.close();
        liveAudioPlaybackRef.current = null;
      }
    };
  }, [stopLiveAudioRouter]);

  const handleLiveMessage = useCallback(
    async (data) => {
      switch (data.type) {
        case "server.tool_result": {
          const callId = typeof data.call_id === "string" ? data.call_id : "";
          if (callId && pendingToolCallsRef.current.has(callId)) {
            const pending = pendingToolCallsRef.current.get(callId);
            pendingToolCallsRef.current.delete(callId);
            window.clearTimeout(pending.timeoutId);
            if (data.ok) {
              pending.resolve(data.result ?? {});
            } else {
              pending.reject(new Error(data.error || `Tool call failed: ${pending.name}`));
            }
            void loadLiveToolMetrics();
            break;
          }
          if (!data.ok) {
            appendCaption("Tool", `${data.name || "tool"} failed: ${data.error || "Unknown error"}`);
            void loadLiveToolMetrics();
            break;
          }
          appendCaption("Tool", `${data.name || "tool"} completed.`);
          void loadLiveToolMetrics();
          break;
        }
        case "server.audio":
          lastAssistantAudioAtRef.current = Date.now();
          if (liveAudioPlaybackRef.current) {
            try {
              await liveAudioPlaybackRef.current.enqueue(data.data_b64, data.mime);
            } catch {
              // Keep the text transcript flowing even if audio playback is unavailable.
            }
          }
          break;
        case "server.transcript": {
          if (liveMode === "READ_SCORE") {
            break;
          }
          const role = data.role === "user" ? "user" : "assistant";
          const text = typeof data.text === "string" ? data.text : "";
          if (!text) {
            break;
          }
          if (role === "assistant") {
            assistantStreamingRef.current = Boolean(data.partial);
            if (!pendingMusicInterruptRef.current) {
              setInterruptState((current) => ({
                ...current,
                status: "listening",
              }));
            }
          }
          upsertConversationStream(role, text, {
            kind: "speech",
            final: !data.partial,
          });
          if (!data.partial && role === "user") {
            appendCaption("You", text);
          }
          break;
        }
        case "server.text":
          if (liveMode === "READ_SCORE") {
            break;
          }
          if (!cameraCapturePending) {
            assistantStreamingRef.current = false;
            finalizeAssistantMessage(data.text ?? "");
            appendCaption("Live", data.text ?? "");
            if (pendingMusicInterruptRef.current) {
              if (musicInterruptTimerRef.current) {
                window.clearTimeout(musicInterruptTimerRef.current);
              }
              musicInterruptTimerRef.current = window.setTimeout(() => {
                musicInterruptTimerRef.current = null;
                flushPendingMusicInterrupt();
              }, 120);
            } else {
              setInterruptState((current) => ({
                ...current,
                status: "listening",
              }));
            }
          }
          break;
        case "server.status":
          if (liveMode === "READ_SCORE") {
            setStatus("Camera reader connected.");
          } else {
            setStatus(`Connected in ${data.skill}.`);
            setInterruptState((current) => ({
              ...current,
              status: data.skill === "GUIDED_LESSON" ? "listening" : current.status,
            }));
            appendConversationMessage(
              "system",
              data.skill === "GUIDED_LESSON"
                ? "Gemini Live is ready. Speak naturally or play when prompted."
                : `Connected in ${data.skill}.`,
              { kind: "status" },
            );
          }
          break;
        case "server.score_capture":
          setCameraCapturePending(false);
          appendCaption("Score", `Captured score line: ${data.note_line}`);
          setScoreLine(data.note_line ?? "");
          stopLiveSessionRef.current();
          if (runLessonActionRef.current) {
            await runLessonActionRef.current({
              sourceTextOverride: data.note_line ?? "",
              forcedPrepare: true,
            });
          }
          break;
        case "server.score_unclear":
          setCameraCapturePending(false);
          setStatus("Sheet still unclear.");
          appendCaption(
            "Score",
            "The score is still unclear. Move closer, reduce glare, and center one short bar.",
          );
          break;
        case "server.summary":
          appendConversationMessage(
            "system",
            Array.isArray(data.bullets) ? data.bullets.join(" ") : "Live session complete.",
            { kind: "status" },
          );
          appendCaption(
            "Summary",
            Array.isArray(data.bullets) ? data.bullets.join(" ") : "Session complete.",
          );
          break;
        case "error":
          setErrorMessage(data.message || "Live session error.");
          setStatus("Error.");
          appendConversationMessage("system", data.message || "Live session error.", {
            kind: "warning",
          });
          break;
        default:
          break;
      }
    },
    [
      appendCaption,
      appendConversationMessage,
      cameraCapturePending,
      finalizeAssistantMessage,
      flushPendingMusicInterrupt,
      liveMode,
      loadLiveToolMetrics,
      upsertConversationStream,
    ],
  );

  useEffect(() => {
    liveMessageHandlerRef.current = handleLiveMessage;
  }, [handleLiveMessage]);

  const detectedTempo = useMemo(() => {
    return analysis?.tempo_bpm ?? null;
  }, [analysis]);

  const handlePlayPhrase = useCallback(
    async (notes, defaultTempo) => {
      if (isPlaying || !notes?.length) {
        return;
      }
      setIsPlaying(true);
      try {
        const tempo =
          tempoOverride && Number(tempoOverride) > 0
            ? Number(tempoOverride)
            : defaultTempo || 120;
        await playPhrase({
          notes,
          tempo_bpm: tempo,
          audioElement: playbackAudioElement,
        });
      } finally {
        setIsPlaying(false);
      }
    },
    [isPlaying, playbackAudioElement, tempoOverride],
  );

  const handlePlayAnalysis = useCallback(() => {
    if (!analysis?.notes?.length) {
      return;
    }
    return handlePlayPhrase(analysis.notes, analysis.tempo_bpm);
  }, [analysis, handlePlayPhrase]);

  const handlePlayScore = useCallback(() => {
    if (!activeScore?.measures?.length) {
      return;
    }
    const notes = activeScore.measures.flatMap((m) =>
      (m.notes ?? []).map((n) => ({
        midi_note: n.midi_note,
        beats: n.beats,
      })),
    );
    return handlePlayPhrase(notes, 120);
  }, [activeScore, handlePlayPhrase]);

  const isReadingScore = isConnected && liveMode === "READ_SCORE";

  const handlePrimaryAction = useCallback(async () => {
    if (isBusy) {
      return;
    }
    setIsBusy(true);
    try {
      await runLessonAction();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Action failed.");
      setStatus("Action failed.");
    } finally {
      setIsBusy(false);
    }
  }, [isBusy, runLessonAction]);

  const handleCapturePhraseAction = useCallback(async () => {
    if (isBusy) {
      return;
    }
    setIsBusy(true);
    try {
      await handleHearPhrase();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Phrase capture failed.");
      setStatus("Phrase capture failed.");
    } finally {
      setIsBusy(false);
    }
  }, [handleHearPhrase, isBusy]);

  const handleToggleScoreReader = useCallback(async () => {
    if (isBusy) {
      return;
    }
    setIsBusy(true);
    try {
      if (isReadingScore) {
        stopLiveSession();
      } else {
        await startReadScoreSession();
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Camera reader action failed.");
      setStatus("Camera reader action failed.");
    } finally {
      setIsBusy(false);
    }
  }, [isBusy, isReadingScore, startReadScoreSession, stopLiveSession]);

  const primaryActionLabel = useMemo(() => {
    return buildPrimaryActionLabel({ activeScore, lessonState, scoreLine });
  }, [activeScore, lessonState, scoreLine]);

  const activeNoteRange = useMemo(() => {
    if (lessonState.noteStartIndex == null || lessonState.noteEndIndex == null) {
      return null;
    }
    return {
      start: lessonState.noteStartIndex,
      end: lessonState.noteEndIndex,
    };
  }, [lessonState.noteEndIndex, lessonState.noteStartIndex]);

  const comparisonStateByIndex = useMemo(() => {
    if (!comparison?.comparisons || !activeNoteRange) {
      return new Map();
    }
    const nextMap = new Map();
    for (const item of comparison.comparisons) {
      const relativeIndex = Math.max(0, Number(item.index || 1) - 1);
      const absoluteIndex = activeNoteRange.start + relativeIndex;
      if (!item.pitch_match) {
        nextMap.set(absoluteIndex, "pitch");
      } else if (!item.rhythm_match) {
        nextMap.set(absoluteIndex, "rhythm");
      } else {
        nextMap.set(absoluteIndex, "match");
      }
    }
    return nextMap;
  }, [activeNoteRange, comparison]);

  const runtimeSummary = useMemo(() => {
    if (runtimeStatus.verovioAvailable == null) {
      return "Runtime status will load after sign-in.";
    }
    const renderStatus = runtimeStatus.verovioAvailable
      ? "Verovio is available for SVG notation rendering."
      : "Verovio is not installed on the backend yet; MusicXML fallback will be used.";
    const pitchStatus = runtimeStatus.crepeAvailable
      ? " CREPE confirmation is active for focused clips."
      : " FastYIN is active; CREPE confirmation is not installed.";
    return `${renderStatus}${pitchStatus}`;
  }, [runtimeStatus.crepeAvailable, runtimeStatus.verovioAvailable]);

  return {
    email,
    setEmail,
    password,
    setPassword,
    authStatus,
    status,
    errorMessage,
    captions,
    conversationMessages,
    micEnabled,
    setMicEnabled,
    cameraEnabled,
    setCameraEnabled,
    instrumentProfile,
    setInstrumentProfile,
    scoreLine,
    setScoreLine,
    activeScore,
    lessonState,
    analysis,
    comparison,
    userSkillProfile,
    nextDrills,
    tutorPrompt,
    liveToolMetrics,
    sessionId,
    liveMode,
    liveAudioMode,
    liveAudioLevels,
    recentMusicEvents,
    interruptState,
    isReadingScore,
    isBusy,
    isPlaying,
    isConnected,
    playbackAudioElement,
    setPlaybackAudioElement,
    orbLowPower,
    setOrbLowPower,
    videoRef,
    primaryActionLabel,
    activeNoteRange,
    comparisonStateByIndex,
    runtimeSummary,
    isAuthenticated: Boolean(user),
    detectedTempo,
    tempoOverride,
    setTempoOverride,
    handleSignIn,
    startTutorSession,
    stopLiveSession,
    handlePrimaryAction,
    handleCapturePhraseAction,
    handleToggleScoreReader,
    handlePlayAnalysis,
    handlePlayScore,
    resetLessonState,
  };
}
