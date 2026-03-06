import { useEffect, useState } from "react";
import AppLayout from "./components/AppLayout";
import LandingPage from "./components/LandingPage";
import useEurydiceApp, { SKILLS } from "./hooks/useEurydiceApp";

export default function App() {
  const [signingIn, setSigningIn] = useState(false);
  const [isEnteringWorkspace, setIsEnteringWorkspace] = useState(false);
  const {
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
    isAuthenticated,
    handleSignIn,
    handlePrimaryAction,
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
      skills={SKILLS}
      authStatus={authStatus}
      skill={skill}
      onSkillChange={setSkill}
      authPanelProps={{
        email,
        password,
        authStatus,
        micEnabled,
        cameraEnabled,
        isConnected,
        status,
        runtimeSummary,
        sessionId,
        skill,
        isBusy,
        primaryActionLabel,
        onEmailChange: setEmail,
        onPasswordChange: setPassword,
        onSignIn: handleSignIn,
        onToggleMic: () => setMicEnabled((value) => !value),
        onToggleCamera: () => setCameraEnabled((value) => !value),
        onPrimaryAction: () => {
          void handlePrimaryAction();
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
        liveMode,
        lessonState,
      }}
      lessonPanelProps={{
        skill,
        lessonState,
        analysis,
        comparison,
        errorMessage,
      }}
      sessionLogProps={{
        captions,
      }}
    />
  );
}
