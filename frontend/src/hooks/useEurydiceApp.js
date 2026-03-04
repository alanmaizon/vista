import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import useLiveConnection from "./useLiveConnection";
import { apiRequest } from "../lib/api";
import { capturePcmClip } from "../lib/audioCapture";
import { signInWithFirebase } from "../lib/firebaseBrowser";

export const SKILLS = [
  {
    id: "GUIDED_LESSON",
    title: "Guided Lesson",
    description: "Prepare a score, move bar by bar, then compare each take.",
  },
  {
    id: "HEAR_PHRASE",
    title: "Hear Phrase",
    description: "Capture a short phrase and identify the notes or interval shape.",
  },
  {
    id: "READ_SCORE",
    title: "Read From Camera",
    description: "Use a live camera view to capture a short readable bar into the lesson flow.",
  },
];

function appendTimestamped(items, role, text) {
  return [...items, { role, text, id: `${Date.now()}-${items.length}` }];
}

function normalizeFirebaseConfigText(rawValue) {
  const trimmed = rawValue.trim();
  if (!trimmed) {
    throw new Error(
      "Firebase config is missing. Paste it in, or set VISTA_FIREBASE_WEB_CONFIG on the backend.",
    );
  }
  try {
    const parsed = JSON.parse(trimmed);
    if (!parsed || typeof parsed !== "object") {
      throw new Error("Firebase config must be a JSON object.");
    }
    return parsed;
  } catch {
    throw new Error("Firebase config must be valid JSON.");
  }
}

function scoreIsDirty(scoreLine, activeScore) {
  if (!activeScore) {
    return true;
  }
  return scoreLine.trim() !== (activeScore.normalized ?? "").trim();
}

function buildPrimaryActionLabel({ skill, activeScore, lessonState, scoreLine }) {
  if (skill === "HEAR_PHRASE") {
    return "Hear phrase";
  }
  if (skill === "READ_SCORE") {
    return "Read from camera";
  }
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

export default function useEurydiceApp() {
  const [firebaseConfigText, setFirebaseConfigText] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [user, setUser] = useState(null);
  const [authStatus, setAuthStatus] = useState("Loading Firebase config...");
  const [skill, setSkill] = useState("GUIDED_LESSON");
  const [status, setStatus] = useState("Ready.");
  const [errorMessage, setErrorMessage] = useState("");
  const [captions, setCaptions] = useState([]);
  const [micEnabled, setMicEnabled] = useState(true);
  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [scoreLine, setScoreLine] = useState("C4/q D4/q D4/q");
  const [activeScore, setActiveScore] = useState(null);
  const [lessonState, setLessonState] = useState(initialLessonState);
  const [analysis, setAnalysis] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [runtimeStatus, setRuntimeStatus] = useState({
    verovioAvailable: null,
    verovioDetail: "",
    crepeAvailable: null,
    crepeDetail: "",
  });
  const [sessionId, setSessionId] = useState(null);
  const [liveMode, setLiveMode] = useState(null);
  const [cameraCapturePending, setCameraCapturePending] = useState(false);
  const [isBusy, setIsBusy] = useState(false);

  const videoRef = useRef(null);
  const cameraStreamRef = useRef(null);
  const frameTimerRef = useRef(null);
  const runLessonActionRef = useRef(null);
  const stopLiveSessionRef = useRef(() => {});
  const liveMessageHandlerRef = useRef(async () => {});

  const appendCaption = useCallback((role, text) => {
    if (!text) {
      return;
    }
    setCaptions((items) => appendTimestamped(items, role, text));
  }, []);

  const resetLessonState = useCallback(() => {
    setLessonState(initialLessonState());
    setComparison(null);
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

  const { connect, disconnect, send, isConnected } = useLiveConnection({
    onMessage: (data) => {
      void liveMessageHandlerRef.current(data);
    },
    onClose: () => {
      stopCameraCapture();
      setLiveMode(null);
      setSessionId(null);
      setCameraCapturePending(false);
      setStatus("Live session closed.");
    },
    onError: () => {
      setStatus("Live connection error.");
    },
  });

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
    },
    [appendCaption],
  );

  const applyComparisonPayload = useCallback(
    (payload) => {
      setComparison(payload);
      setStatus(payload.needs_replay ? "Replay requested." : "Comparison ready.");
      appendCaption("Compare", payload.summary);
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
    [appendCaption],
  );

  const getIdToken = useCallback(async () => {
    if (!user) {
      throw new Error("Sign in first.");
    }
    return user.getIdToken(true);
  }, [user]);

  useEffect(() => {
    let active = true;
    async function loadClientConfig() {
      try {
        const payload = await apiRequest("/api/client-config");
        const firebaseConfig = payload?.firebaseConfig;
        if (active && firebaseConfig) {
          setFirebaseConfigText(JSON.stringify(firebaseConfig, null, 2));
          setAuthStatus("Firebase config loaded. Click Sign In.");
        } else if (active) {
          setAuthStatus(
            "Firebase config is missing. Paste it in, or set VISTA_FIREBASE_WEB_CONFIG on the backend.",
          );
        }
      } catch {
        if (active) {
          setAuthStatus("Unable to load Firebase config automatically. Paste it in to continue.");
        }
      }
    }
    void loadClientConfig();
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
        const token = await user.getIdToken(true);
        const payload = await apiRequest("/api/music/runtime", { token });
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

  const handleSignIn = useCallback(async () => {
    setErrorMessage("");
    try {
      const config = normalizeFirebaseConfigText(firebaseConfigText);
      const signedInUser = await signInWithFirebase(config, { email: email.trim(), password });
      setUser(signedInUser);
      setAuthStatus(`Signed in as ${signedInUser.email || signedInUser.uid}`);
      setStatus("Signed in.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Sign-in failed.");
      setStatus("Sign-in failed.");
    }
  }, [email, firebaseConfigText, password]);

  const runLessonAction = useCallback(
    async ({ sourceTextOverride = null, forcedPrepare = false } = {}) => {
      setErrorMessage("");
      if (!user) {
        throw new Error("Sign in before starting the guided lesson.");
      }

      const token = await getIdToken();
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
        };
      } else if (awaitingCompare) {
        if (!micEnabled) {
          throw new Error("Turn the microphone on before comparing this bar.");
        }
        setStatus("Recording a comparison take...");
        const clip = await capturePcmClip({ durationMs: 2800 });
        setStatus("Comparing bar...");
        body = {
          score_id: activeScore.score_id,
          current_measure_index: lessonState.measureIndex,
          lesson_stage: "awaiting-compare",
          audio_b64: clip.audioB64,
          mime: clip.mime,
          max_notes: 12,
        };
      } else {
        setStatus("Loading lesson step...");
        body = {
          score_id: activeScore.score_id,
          current_measure_index: lessonState.measureIndex,
          lesson_stage: lessonState.stage === "complete" ? "complete" : lessonState.stage || "idle",
        };
      }

      const payload = await apiRequest("/api/music/lesson-action", {
        method: "POST",
        token,
        body,
      });

      if (payload?.score) {
        applyPreparedScorePayload(payload.score);
      }
      if (payload?.lesson) {
        applyLessonPayload(payload.lesson);
      }
      if (payload?.comparison) {
        applyComparisonPayload(payload.comparison);
      }
    },
    [
      activeScore,
      applyComparisonPayload,
      applyLessonPayload,
      applyPreparedScorePayload,
      getIdToken,
      lessonState.measureIndex,
      lessonState.stage,
      micEnabled,
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
    const token = await getIdToken();
    setStatus("Recording a short phrase...");
    const clip = await capturePcmClip();
    setStatus("Transcribing phrase...");
    const payload = await apiRequest("/api/music/transcribe", {
      method: "POST",
      token,
      body: {
        audio_b64: clip.audioB64,
        mime: clip.mime,
        expected: "AUTO",
        max_notes: 8,
      },
    });
    setAnalysis(payload);
    setStatus("Transcription ready.");
    appendCaption("Transcription", payload.summary || "Phrase analysed.");
    for (const warning of payload.warnings ?? []) {
      appendCaption("Warning", warning);
    }
  }, [appendCaption, getIdToken, micEnabled, user]);

  const startReadScoreSession = useCallback(async () => {
    setErrorMessage("");
    if (!user) {
      throw new Error("Sign in before reading a score.");
    }
    if (!cameraEnabled) {
      throw new Error("Turn the camera on before reading a score.");
    }
    const token = await getIdToken();
    setStatus("Creating live score reader...");
    const session = await apiRequest("/api/sessions", {
      method: "POST",
      token,
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
      token,
      sessionId: session.id,
      mode: "READ_SCORE",
    });
    setStatus("Opening live score reader...");
    appendCaption("Setup", "Keep one short bar centered and steady until Eurydice captures a NOTE_LINE.");
  }, [appendCaption, cameraEnabled, connect, getIdToken, user]);

  const stopLiveSession = useCallback(() => {
    if (isConnected) {
      send({ type: "client.stop" });
    }
    disconnect();
    setLiveMode(null);
    setSessionId(null);
    setCameraCapturePending(false);
    stopCameraCapture();
    setStatus("Live session stopped.");
  }, [disconnect, isConnected, send, stopCameraCapture]);

  useEffect(() => {
    runLessonActionRef.current = runLessonAction;
  }, [runLessonAction]);

  useEffect(() => {
    stopLiveSessionRef.current = stopLiveSession;
  }, [stopLiveSession]);

  const handleLiveMessage = useCallback(
    async (data) => {
      switch (data.type) {
        case "server.text":
          if (!cameraCapturePending) {
            appendCaption("Live", data.text ?? "");
          }
          break;
        case "server.status":
          setStatus(`Connected in ${data.skill}.`);
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
          appendCaption(
            "Summary",
            Array.isArray(data.bullets) ? data.bullets.join(" ") : "Session complete.",
          );
          break;
        case "error":
          setErrorMessage(data.message || "Live session error.");
          setStatus("Error.");
          break;
        default:
          break;
      }
    },
    [appendCaption, cameraCapturePending],
  );

  useEffect(() => {
    liveMessageHandlerRef.current = handleLiveMessage;
  }, [handleLiveMessage]);

  const handlePrimaryAction = useCallback(async () => {
    if (isBusy) {
      return;
    }
    setIsBusy(true);
    try {
      if (skill === "HEAR_PHRASE") {
        await handleHearPhrase();
      } else if (skill === "READ_SCORE") {
        if (isConnected && liveMode === "READ_SCORE") {
          stopLiveSession();
        } else {
          await startReadScoreSession();
        }
      } else {
        await runLessonAction();
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Action failed.");
      setStatus("Action failed.");
    } finally {
      setIsBusy(false);
    }
  }, [
    handleHearPhrase,
    isBusy,
    isConnected,
    liveMode,
    runLessonAction,
    skill,
    startReadScoreSession,
    stopLiveSession,
  ]);

  const primaryActionLabel = useMemo(() => {
    if (skill === "READ_SCORE" && isConnected && liveMode === "READ_SCORE") {
      return "Stop reader";
    }
    return buildPrimaryActionLabel({ skill, activeScore, lessonState, scoreLine });
  }, [activeScore, isConnected, lessonState, liveMode, scoreLine, skill]);

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
    firebaseConfigText,
    setFirebaseConfigText,
    email,
    setEmail,
    password,
    setPassword,
    authStatus,
    skill,
    setSkill,
    status,
    errorMessage,
    captions,
    micEnabled,
    setMicEnabled,
    cameraEnabled,
    setCameraEnabled,
    scoreLine,
    setScoreLine,
    activeScore,
    lessonState,
    analysis,
    comparison,
    sessionId,
    liveMode,
    isBusy,
    isConnected,
    videoRef,
    primaryActionLabel,
    activeNoteRange,
    comparisonStateByIndex,
    runtimeSummary,
    handleSignIn,
    handlePrimaryAction,
    resetLessonState,
  };
}
