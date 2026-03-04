import { useState, useCallback } from "react";

/**
 * Hook that manages guided-lesson state extracted from the legacy app.
 *
 * Mirrors lesson-flow state from the old static code:
 * - current step, total steps, lesson state, comparison results
 */
export default function useLessonLogic() {
  const [step, setStep] = useState(0);
  const [totalSteps, setTotalSteps] = useState(0);
  const [lessonState, setLessonState] = useState("idle"); // idle | active | completed
  const [comparison, setComparison] = useState(null);

  const startLesson = useCallback((steps) => {
    setStep(0);
    setTotalSteps(steps);
    setLessonState("active");
    setComparison(null);
  }, []);

  const advanceStep = useCallback(() => {
    setStep((prev) => {
      const next = prev + 1;
      if (next >= totalSteps) {
        setLessonState("completed");
      }
      return next;
    });
  }, [totalSteps]);

  const setComparisonResult = useCallback((result) => {
    setComparison(result);
  }, []);

  const resetLesson = useCallback(() => {
    setStep(0);
    setTotalSteps(0);
    setLessonState("idle");
    setComparison(null);
  }, []);

  return {
    step,
    totalSteps,
    lessonState,
    comparison,
    startLesson,
    advanceStep,
    setComparisonResult,
    resetLesson,
  };
}
