import { useState } from "react";
import AppLayout from "./components/AppLayout";
import LandingPage from "./components/LandingPage";
import useEurydiceApp, { SKILLS } from "./hooks/useEurydiceApp";

export default function App() {
  const [signingIn, setSigningIn] = useState(false);
  const {
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
      await handleSignIn();
    } finally {
      setSigningIn(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <LandingPage
        authStatus={authStatus}
        errorMessage={errorMessage}
        signingIn={signingIn}
        firebaseConfigText={firebaseConfigText}
        email={email}
        password={password}
        onFirebaseConfigChange={setFirebaseConfigText}
        onEmailChange={setEmail}
        onPasswordChange={setPassword}
        onSignIn={handleLandingSignIn}
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
        firebaseConfigText,
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
        onFirebaseConfigChange: setFirebaseConfigText,
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
