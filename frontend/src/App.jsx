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
    sessionId,
    isReadingScore,
    isBusy,
    isConnected,
    videoRef,
    primaryActionLabel,
    activeNoteRange,
    comparisonStateByIndex,
    runtimeSummary,
    isAuthenticated,
    handleSignIn,
    handlePrimaryAction,
    handleCapturePhraseAction,
    handleToggleScoreReader,
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
        onToggleScoreReader: () => {
          void handleToggleScoreReader();
        },
      }}
      scoreWorkspaceProps={{
        activeScore,
        activeNoteRange,
        comparisonStateByIndex,
        scoreLine,
        onScoreLineChange: (value) => {
          setScoreLine(value);
          if (activeScore) {
            resetLessonState();
          }
        },
        videoRef,
        isReadingScore,
        lessonState,
      }}
      lessonPanelProps={{
        lessonState,
        analysis,
        comparison,
        userSkillProfile,
        nextDrills,
        tutorPrompt,
        errorMessage,
      }}
      sessionLogProps={{
        captions,
      }}
    />
  );
}
