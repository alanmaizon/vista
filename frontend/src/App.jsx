import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Camera,
  CameraOff,
  LoaderCircle,
  Mic,
  MicOff,
  Music4,
  Radio,
  ScanLine,
  Wifi,
  WifiOff,
} from "lucide-react";
import useLiveConnection from "./hooks/useLiveConnection";
import { apiRequest } from "./lib/api";
import { capturePcmClip } from "./lib/audioCapture";
import { signInWithFirebase } from "./lib/firebaseBrowser";

const SKILLS = [
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
    throw new Error("Firebase config is missing. Paste it in, or set VISTA_FIREBASE_WEB_CONFIG on the backend.");
  }
  try {
    const parsed = JSON.parse(trimmed);
    if (!parsed || typeof parsed !== "object") {
      throw new Error("Firebase config must be a JSON object.");
    }
    return parsed;
  } catch (error) {
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

function noteClass({ active, mismatch }) {
  if (mismatch === "pitch") {
    return "border-red-300 bg-red-50 text-red-900";
  }
  if (mismatch === "rhythm") {
    return "border-amber-300 bg-amber-50 text-amber-900";
  }
  if (active) {
    return "border-sky-300 bg-sky-50 text-sky-900";
  }
  return "border-slate-200 bg-white text-slate-700";
}

export default function App() {
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
  const [lessonState, setLessonState] = useState({
    stage: "idle",
    measureIndex: null,
    totalMeasures: 0,
    noteStartIndex: null,
    noteEndIndex: null,
    prompt: "",
  });
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
    setLessonState({
      stage: "idle",
      measureIndex: null,
      totalMeasures: 0,
      noteStartIndex: null,
      noteEndIndex: null,
      prompt: "",
    });
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
          setAuthStatus("Firebase config is missing. Paste it in, or set VISTA_FIREBASE_WEB_CONFIG on the backend.");
        }
      } catch (error) {
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
      } catch (error) {
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
      } catch (error) {
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
          appendCaption("Score", "The score is still unclear. Move closer, reduce glare, and center one short bar.");
          break;
        case "server.summary":
          appendCaption("Summary", Array.isArray(data.bullets) ? data.bullets.join(" ") : "Session complete.");
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
  }, [handleHearPhrase, isBusy, isConnected, liveMode, runLessonAction, skill, startReadScoreSession, stopLiveSession]);

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

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(96,165,250,0.2),_transparent_40%),linear-gradient(180deg,#081225_0%,#09162b_45%,#07101e_100%)] text-slate-100">
      <main className="mx-auto max-w-7xl px-4 py-6 md:px-6">
        <header className="glass mb-6 rounded-3xl px-5 py-4">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex items-center gap-2 text-sky-300">
                <Music4 className="h-5 w-5" />
                <span className="text-xs font-semibold uppercase tracking-[0.24em]">Eurydice</span>
              </div>
              <h1 className="mt-2 text-2xl font-semibold text-white md:text-3xl">
                End-to-end musical guidance in one lesson loop
              </h1>
              <p className="mt-2 max-w-3xl text-sm text-slate-300">
                Sign in, prepare a phrase or score, and use one guided surface for capture, comparison, and feedback.
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
              <div className="font-medium text-white">Auth</div>
              <div className="mt-1">{authStatus}</div>
            </div>
          </div>
        </header>

        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <section className="space-y-6">
            <div className="glass rounded-3xl p-5">
              <div className="grid gap-4 lg:grid-cols-3">
                {SKILLS.map((item) => {
                  const active = item.id === skill;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setSkill(item.id)}
                      className={`rounded-2xl border px-4 py-4 text-left transition ${
                        active
                          ? "border-sky-300/70 bg-sky-400/10 shadow-[0_0_0_1px_rgba(125,211,252,0.2)]"
                          : "border-white/10 bg-white/5 hover:bg-white/10"
                      }`}
                    >
                      <div className="text-sm font-semibold text-white">{item.title}</div>
                      <div className="mt-1 text-xs text-slate-300">{item.description}</div>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="glass rounded-3xl p-5">
              <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
                <div className="space-y-3">
                  <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
                    Firebase config
                  </label>
                  <textarea
                    value={firebaseConfigText}
                    onChange={(event) => setFirebaseConfigText(event.target.value)}
                    rows={5}
                    className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-3 text-xs text-slate-200 outline-none focus:border-sky-300/60"
                  />
                  <div className="grid gap-3 md:grid-cols-2">
                    <input
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      placeholder="Email (optional)"
                      className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-sky-300/60"
                    />
                    <input
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      placeholder="Password (optional)"
                      type="password"
                      className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-sky-300/60"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={handleSignIn}
                    className="rounded-2xl bg-sky-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-300"
                  >
                    Sign In
                  </button>
                </div>

                <div className="space-y-4 rounded-3xl border border-white/10 bg-slate-950/40 p-4">
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">Session</div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <button
                      type="button"
                      onClick={() => setMicEnabled((value) => !value)}
                      className={`flex items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-medium transition ${
                        micEnabled ? "bg-emerald-400/15 text-emerald-200" : "bg-white/5 text-slate-400"
                      }`}
                    >
                      {micEnabled ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
                      Mic {micEnabled ? "On" : "Off"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setCameraEnabled((value) => !value)}
                      className={`flex items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-medium transition ${
                        cameraEnabled ? "bg-emerald-400/15 text-emerald-200" : "bg-white/5 text-slate-400"
                      }`}
                    >
                      {cameraEnabled ? <Camera className="h-4 w-4" /> : <CameraOff className="h-4 w-4" />}
                      Camera {cameraEnabled ? "On" : "Off"}
                    </button>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-3 text-sm text-slate-300">
                    <div className="flex items-center gap-2 text-white">
                      {isConnected ? <Wifi className="h-4 w-4 text-emerald-300" /> : <WifiOff className="h-4 w-4 text-slate-400" />}
                      {status}
                    </div>
                    <div className="mt-2 text-xs text-slate-400">{runtimeSummary}</div>
                    {sessionId ? <div className="mt-2 text-[11px] text-slate-500">Session: {sessionId}</div> : null}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      void handlePrimaryAction();
                    }}
                    disabled={isBusy}
                    className="flex w-full items-center justify-center gap-2 rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-100 disabled:cursor-wait disabled:opacity-70"
                  >
                    {isBusy ? <LoaderCircle className="h-4 w-4 animate-spin" /> : skill === "READ_SCORE" ? <ScanLine className="h-4 w-4" /> : <Radio className="h-4 w-4" />}
                    {primaryActionLabel}
                  </button>
                </div>
              </div>
            </div>

            <div className="glass rounded-3xl p-5">
              <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
                Score line
              </label>
              <textarea
                value={scoreLine}
                onChange={(event) => {
                  setScoreLine(event.target.value);
                  if (activeScore) {
                    resetLessonState();
                  }
                }}
                rows={3}
                className="mt-3 w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-3 text-sm text-slate-100 outline-none focus:border-sky-300/60"
                placeholder="C4/q D4/q E4/h | G4/q A4/q B4/h"
              />
              <div className="mt-3 text-xs text-slate-400">
                Guided Lesson uses this draft unless you capture a bar directly from the live camera reader.
              </div>
            </div>

            <div className="glass rounded-3xl p-5">
              <div className="flex items-center justify-between">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">Live feed</div>
                {liveMode === "READ_SCORE" ? (
                  <span className="rounded-full border border-emerald-300/30 bg-emerald-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-200">
                    Reading from camera
                  </span>
                ) : null}
              </div>
              <div className="mt-4 overflow-hidden rounded-3xl border border-white/10 bg-slate-950/60">
                <video ref={videoRef} autoPlay muted playsInline className="aspect-video w-full object-cover" />
              </div>
              <div className="mt-3 text-xs text-slate-400">
                Camera capture is only used during the live score reader. It sends one JPEG frame per second while connected.
              </div>
            </div>
          </section>

          <section className="space-y-6">
            <div className="glass rounded-3xl p-5">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">Rendered score</div>
              <div className="mt-4 rounded-3xl border border-slate-200 bg-white p-5 text-slate-900">
                {activeScore?.svg ? (
                  <div dangerouslySetInnerHTML={{ __html: activeScore.svg }} />
                ) : activeScore?.musicxml ? (
                  <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-slate-700">{activeScore.musicxml}</pre>
                ) : (
                  <div className="text-sm text-slate-500">Prepare a lesson to render notation here.</div>
                )}
              </div>

              {activeScore?.expected_notes?.length ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  {activeScore.expected_notes.map((note, index) => {
                    const active =
                      activeNoteRange && index >= activeNoteRange.start && index < activeNoteRange.end;
                    const mismatch = comparisonStateByIndex.get(index);
                    return (
                      <span
                        key={`${note.note_name}-${index}`}
                        className={`rounded-full border px-3 py-1 text-xs font-medium ${noteClass({ active, mismatch })}`}
                      >
                        {note.note_name}
                      </span>
                    );
                  })}
                </div>
              ) : null}
            </div>

            <div className="glass rounded-3xl p-5">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">Lesson state</div>
              <div className="mt-3 space-y-2 text-sm text-slate-200">
                <div>Mode: {skill}</div>
                <div>Lesson stage: {lessonState.stage}</div>
                <div>
                  Measure: {lessonState.measureIndex ?? "—"}
                  {lessonState.totalMeasures ? ` / ${lessonState.totalMeasures}` : ""}
                </div>
                {lessonState.prompt ? <div className="rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-slate-100">{lessonState.prompt}</div> : null}
              </div>

              {analysis ? (
                <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
                  <div className="font-medium text-white">Phrase analysis</div>
                  <div className="mt-1">{analysis.summary}</div>
                  {analysis.notes?.length ? (
                    <div className="mt-2 text-xs text-slate-300">
                      Notes: {analysis.notes.map((note) => note.note_name || note.note || "?").join(", ")}
                    </div>
                  ) : null}
                </div>
              ) : null}

              {comparison ? (
                <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
                  <div className="font-medium text-white">Comparison</div>
                  <div className="mt-1">{comparison.summary}</div>
                  <div className="mt-2 text-xs text-slate-300">Accuracy: {Math.round((comparison.accuracy || 0) * 100)}%</div>
                </div>
              ) : null}

              {errorMessage ? (
                <div className="mt-4 rounded-2xl border border-red-300/30 bg-red-400/10 px-4 py-3 text-sm text-red-100">
                  {errorMessage}
                </div>
              ) : null}
            </div>

            <div className="glass rounded-3xl p-5">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">Session log</div>
              <div className="mt-4 max-h-[26rem] space-y-3 overflow-y-auto">
                {captions.length ? (
                  captions.map((caption) => (
                    <div key={caption.id} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">{caption.role}</div>
                      <div className="mt-1 text-sm text-slate-100">{caption.text}</div>
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-white/10 px-4 py-6 text-sm text-slate-400">
                    Sign in and start with “Prepare lesson” or “Hear phrase”. Live captions and lesson guidance will appear here.
                  </div>
                )}
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
