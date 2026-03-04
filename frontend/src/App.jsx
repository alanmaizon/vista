import AppLayout from "./components/AppLayout";
import useEurydiceApp, { SKILLS } from "./hooks/useEurydiceApp";

export default function App() {
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
    handleSignIn,
    handlePrimaryAction,
    resetLessonState,
  } = useEurydiceApp();

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
