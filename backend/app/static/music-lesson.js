export {
  applyComparisonPayload,
  comparePerformanceClip,
  transcribeOneShotClip,
} from "./modules/AudioProcessor.js";

export {
  applyPreparedScorePayload,
  applyGuidedLessonStepPayload,
  prepareScoreFlow,
  runGuidedLessonAction,
  handleCapturedScoreLine,
  startCameraScoreReadFlow,
} from "./modules/LessonStateMachine.js";
