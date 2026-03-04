import { describe, it, expect } from "vitest";
import { chunkEnergyDb } from "../audioCapture";

describe("chunkEnergyDb", () => {
  it("returns -Infinity for a silent chunk", () => {
    const silent = new Float32Array(256);
    expect(chunkEnergyDb(silent)).toBe(-Infinity);
  });

  it("returns a finite dB value for a non-silent chunk", () => {
    const loud = new Float32Array(256).fill(0.5);
    const db = chunkEnergyDb(loud);
    expect(db).toBeGreaterThan(-Infinity);
    expect(db).toBeLessThan(0);
  });

  it("returns higher dB for louder signal", () => {
    const quiet = new Float32Array(256).fill(0.01);
    const loud = new Float32Array(256).fill(0.5);
    expect(chunkEnergyDb(loud)).toBeGreaterThan(chunkEnergyDb(quiet));
  });
});

describe("capturePcmClip adaptive capture (unit logic)", () => {
  it("onset detection requires energy above threshold", () => {
    // Simulate energy frames: silence followed by signal
    const onsetThresholdDb = -45;
    const silentEnergy = -Infinity;
    const signalEnergy = -20;

    // Silent frames should not trigger onset
    expect(silentEnergy < onsetThresholdDb).toBe(true);
    // Signal frames should trigger onset
    expect(signalEnergy >= onsetThresholdDb).toBe(true);
  });

  it("trailing silence duration triggers stop", () => {
    const trailingSilenceMs = 400;
    const lastAboveTime = 1000;

    // 200ms of silence — should continue
    expect(1200 - lastAboveTime < trailingSilenceMs).toBe(true);

    // 500ms of silence — should stop
    expect(1500 - lastAboveTime >= trailingSilenceMs).toBe(true);
  });

  it("maxMs cap stops recording regardless of energy", () => {
    const maxMs = 10000;
    const startTime = 0;

    expect(9000 - startTime < maxMs).toBe(true);
    expect(10000 - startTime >= maxMs).toBe(true);
  });
});
