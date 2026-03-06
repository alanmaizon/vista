import { useEffect, useState } from "react";
import AppLayout from "./components/AppLayout";
import LandingPage from "./components/LandingPage";
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
    isConnected,
    isPlaying,
    playbackAudioElement,
    setPlaybackAudioElement,
    orbLowPower,
    setOrbLowPower,
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
    <AppLayout
      authStatus={authStatus}
      orbProps={{
        audioSource: isPlaying && playbackAudioElement ? "element" : "microphone",
        audioElement: playbackAudioElement,
        active: isPlaying ? Boolean(playbackAudioElement) : micEnabled && isConnected,
        intensity: orbLowPower ? 0.72 : 0.88,
        theme: isPlaying ? "plasma" : "aurora",
        performanceMode: orbLowPower ? "lite" : "adaptive",
      }}
      playbackAudioElementRef={setPlaybackAudioElement}
      authPanelProps={{
        email,
        password,
        authStatus,
        micEnabled,
        cameraEnabled,
        instrumentProfile,
        isConnected,
        status,
        runtimeSummary,
        sessionId,
        isReadingScore,
        isBusy,
        orbLowPower,
        primaryActionLabel,
        onEmailChange: setEmail,
        onPasswordChange: setPassword,
        onSignIn: handleSignIn,
        onToggleMic: () => setMicEnabled((value) => !value),
        onToggleCamera: () => setCameraEnabled((value) => !value),
        onInstrumentProfileChange: setInstrumentProfile,
        onPrimaryAction: () => {
          void handlePrimaryAction();
        },
        onCapturePhrase: () => {
          void handleCapturePhraseAction();
        },
        onToggleOrbLowPower: () => setOrbLowPower((value) => !value),
        onToggleScoreReader: () => {
          void handleToggleScoreReader();
        },
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
