export const LESSON_PHASES = Object.freeze([
  "idle",
  "intro",
  "goal_capture",
  "exercise_selection",
  "listening",
  "analysis",
  "feedback",
  "next_step",
  "session_complete",
]);

const DEFAULT_CONTROLS = Object.freeze({
  showPrimaryAction: false,
  showCapturePhrase: false,
  showScoreReader: false,
  showInputToggles: false,
  showSecondaryToggle: false,
});

export function normalizeLessonPhase(phase) {
  const clean = typeof phase === "string" ? phase.trim().toLowerCase() : "";
  return LESSON_PHASES.includes(clean) ? clean : "idle";
}

export function humanizeLessonPhase(phase) {
  return normalizeLessonPhase(phase).replaceAll("_", " ");
}

export function actionLabelFromKey(action) {
  const mapping = {
    capture_phrase: "Capture phrase",
    prepare_lesson: "Prepare lesson",
    next_exercise: "Next exercise",
    replay_phrase: "Replay phrase",
    share_goal: "Share goal",
    restart_session: "Restart session",
  };
  return mapping[action] || String(action || "").replaceAll("_", " ").trim() || "Action";
}

export function resolveVisibleControls({ phase, guidedSessionActive }) {
  if (!guidedSessionActive) {
    return DEFAULT_CONTROLS;
  }
  const normalizedPhase = normalizeLessonPhase(phase);
  if (normalizedPhase === "intro" || normalizedPhase === "goal_capture") {
    return {
      showPrimaryAction: false,
      showCapturePhrase: false,
      showScoreReader: false,
      showInputToggles: false,
      showSecondaryToggle: false,
    };
  }
  if (normalizedPhase === "session_complete") {
    return {
      showPrimaryAction: true,
      showCapturePhrase: false,
      showScoreReader: false,
      showInputToggles: false,
      showSecondaryToggle: false,
    };
  }
  if (normalizedPhase === "exercise_selection") {
    return {
      showPrimaryAction: true,
      showCapturePhrase: true,
      showScoreReader: true,
      showInputToggles: true,
      showSecondaryToggle: true,
    };
  }
  if (normalizedPhase === "listening") {
    return {
      showPrimaryAction: true,
      showCapturePhrase: true,
      showScoreReader: false,
      showInputToggles: true,
      showSecondaryToggle: true,
    };
  }
  if (normalizedPhase === "analysis" || normalizedPhase === "feedback" || normalizedPhase === "next_step") {
    return {
      showPrimaryAction: true,
      showCapturePhrase: true,
      showScoreReader: false,
      showInputToggles: true,
      showSecondaryToggle: true,
    };
  }
  return {
    showPrimaryAction: true,
    showCapturePhrase: true,
    showScoreReader: true,
    showInputToggles: true,
    showSecondaryToggle: true,
  };
}
