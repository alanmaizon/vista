import { describe, expect, test } from "vitest";
import {
  actionLabelFromKey,
  humanizeLessonPhase,
  normalizeLessonPhase,
  resolveVisibleControls,
} from "../lessonFlow";

describe("lessonFlow helpers", () => {
  test("normalizeLessonPhase falls back to idle for unknown values", () => {
    expect(normalizeLessonPhase("NOT_REAL")).toBe("idle");
    expect(normalizeLessonPhase("feedback")).toBe("feedback");
  });

  test("humanizeLessonPhase formats underscore phases", () => {
    expect(humanizeLessonPhase("goal_capture")).toBe("goal capture");
  });

  test("actionLabelFromKey maps known actions and handles unknowns", () => {
    expect(actionLabelFromKey("capture_phrase")).toBe("Capture phrase");
    expect(actionLabelFromKey("unknown_action")).toBe("unknown action");
  });

  test("resolveVisibleControls hides controls before exercise selection", () => {
    const controls = resolveVisibleControls({
      phase: "intro",
      guidedSessionActive: true,
    });
    expect(controls.showPrimaryAction).toBe(false);
    expect(controls.showSecondaryToggle).toBe(false);
  });

  test("resolveVisibleControls shows relevant controls during listening", () => {
    const controls = resolveVisibleControls({
      phase: "listening",
      guidedSessionActive: true,
    });
    expect(controls.showPrimaryAction).toBe(true);
    expect(controls.showCapturePhrase).toBe(true);
    expect(controls.showScoreReader).toBe(false);
  });
});
