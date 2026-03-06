import { useEffect, useState } from "react";
import LandingPage from "./components/LandingPage";
import WorkspaceView from "./components/WorkspaceView";
import useEurydiceApp from "./hooks/useEurydiceApp";

export default function App() {
  const [signingIn, setSigningIn] = useState(false);
  const [isEnteringWorkspace, setIsEnteringWorkspace] = useState(false);
  const {
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
    isReadingScore,
    isBusy,
    isSessionStarting,
    isConnected,
    liveMode,
    liveAudioMode,
    liveAudioLevels,
    recentMusicEvents,
    interruptState,
    isPlaying,
    setPlaybackAudioElement,
    videoRef,
    primaryActionLabel,
    activeNoteRange,
    comparisonStateByIndex,
    runtimeSummary,
    isAuthenticated,
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
  } = useEurydiceApp();

  const handleLandingSignIn = async () => {
    if (signingIn) {
      return;
    }
    setSigningIn(true);
    try {
      const signedIn = await handleSignIn();
      if (signedIn) {
        setIsEnteringWorkspace(true);
      }
    } finally {
      setSigningIn(false);
    }
  };

  useEffect(() => {
    if (!isAuthenticated || !isEnteringWorkspace) {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      setIsEnteringWorkspace(false);
    }, 520);
    return () => window.clearTimeout(timer);
  }, [isAuthenticated, isEnteringWorkspace]);

  useEffect(() => {
    const path = window.location.pathname;
    if (isAuthenticated && path !== "/workspace") {
      window.history.replaceState({}, "", "/workspace");
      return;
    }
    if (!isAuthenticated && path === "/workspace") {
      window.history.replaceState({}, "", "/");
    }
  }, [isAuthenticated]);

  if (!isAuthenticated || isEnteringWorkspace) {
    return (
      <LandingPage
        authStatus={authStatus}
        errorMessage={errorMessage}
        signingIn={signingIn}
        email={email}
        password={password}
        onEmailChange={setEmail}
        onPasswordChange={setPassword}
        onSignIn={handleLandingSignIn}
        isTransitioning={isEnteringWorkspace}
      />
    );
  }

  return (
    <WorkspaceView
      authStatus={authStatus}
      orbLayerProps={{
        status,
        runtimeSummary,
        lessonState,
        isConnected,
        micEnabled,
        cameraEnabled,
        isReadingScore,
        isPlaying,
        isBusy,
        isSessionStarting,
        sessionId,
        liveAudioMode,
        interruptState,
      }}
      playbackAudioElementRef={setPlaybackAudioElement}
      controlsProps={{
        authStatus,
        micEnabled,
        cameraEnabled,
        instrumentProfile,
        isConnected,
        liveMode,
        liveAudioMode,
        status,
        runtimeSummary,
        sessionId,
        isReadingScore,
        isBusy,
        isSessionStarting,
        primaryActionLabel,
        onToggleMic: () => setMicEnabled((value) => !value),
        onToggleCamera: () => setCameraEnabled((value) => !value),
        onInstrumentProfileChange: setInstrumentProfile,
        onStartTutorSession: () => {
          void startTutorSession();
        },
        onStopTutorSession: () => {
          stopLiveSession();
        },
        onPrimaryAction: () => {
          void handlePrimaryAction();
        },
        onCapturePhrase: () => {
          void handleCapturePhraseAction();
        },
        onToggleScoreReader: () => {
          void handleToggleScoreReader();
        },
      }}
      conversationProps={{
        messages: conversationMessages,
        liveAudioMode,
        liveAudioLevels,
        recentMusicEvents,
        interruptState,
      }}
      scoreWorkspaceProps={{
        activeScore,
        status,
        isConnected,
        isBusy,
        micEnabled,
        cameraEnabled,
        sessionId,
        activeNoteRange,
        comparisonStateByIndex,
        scoreLine,
        onScoreLineChange: (value) => {
          setScoreLine(value);
          if (activeScore) {
            resetLessonState();
          }
        },
        isPlaying,
        detectedTempo,
        tempoOverride,
        onTempoOverrideChange: setTempoOverride,
        onPlayScore: () => {
          void handlePlayScore();
        },
        onPlayAnalysis: () => {
          void handlePlayAnalysis();
        },
        videoRef,
        isReadingScore,
        lessonState,
        hasAnalysisPlayback: Boolean(analysis?.notes?.length),
      }}
      lessonPanelProps={{
        lessonState,
        analysis,
        comparison,
        userSkillProfile,
        nextDrills,
        tutorPrompt,
        liveToolMetrics,
        errorMessage,
      }}
      sessionLogProps={{
        captions,
      }}
    />
  );
}
