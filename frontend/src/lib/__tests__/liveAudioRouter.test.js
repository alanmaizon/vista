import { describe, expect, it } from "vitest";
import {
  classifyAudioFrame,
  resolveAudioMode,
  resolveSpeechActivity,
  shouldEmitStableNote,
} from "../liveAudioRouter";

describe("classifyAudioFrame", () => {
  it("returns silence for very low energy input", () => {
    expect(
      classifyAudioFrame({
        energyDb: -70,
        zeroCrossingRate: 0.02,
        spectralCentroid: 300,
        pitch: { hz: null, clarity: 0 },
      }),
    ).toEqual({
      mode: "SILENCE",
      speechConfidence: 0,
      musicConfidence: 0,
    });
  });

  it("detects strong harmonic content as music", () => {
    const result = classifyAudioFrame({
      energyDb: -24,
      zeroCrossingRate: 0.03,
      spectralCentroid: 950,
      pitch: { hz: 440, clarity: 0.86 },
    });
    expect(result.mode).toBe("MUSIC");
    expect(result.musicConfidence).toBeGreaterThan(result.speechConfidence);
  });
});

describe("resolveAudioMode", () => {
  it("holds speech on borderline frames instead of flapping to music", () => {
    expect(
      resolveAudioMode({
        currentMode: "SPEECH",
        energyDb: -26,
        speechConfidence: 0.54,
        musicConfidence: 0.5,
        pitchConfidence: 0.38,
      }),
    ).toBe("SPEECH");
  });

  it("holds music through brief ambiguity when pitch is still stable", () => {
    expect(
      resolveAudioMode({
        currentMode: "MUSIC",
        energyDb: -28,
        speechConfidence: 0.43,
        musicConfidence: 0.45,
        pitchConfidence: 0.64,
      }),
    ).toBe("MUSIC");
  });

  it("switches from silence to music only when harmonic confidence is real", () => {
    expect(
      resolveAudioMode({
        currentMode: "SILENCE",
        energyDb: -30,
        speechConfidence: 0.46,
        musicConfidence: 0.72,
        pitchConfidence: 0.71,
      }),
    ).toBe("MUSIC");
  });

  it("drops to silence when energy collapses", () => {
    expect(
      resolveAudioMode({
        currentMode: "MUSIC",
        energyDb: -65,
        speechConfidence: 0.3,
        musicConfidence: 0.4,
        pitchConfidence: 0.6,
      }),
    ).toBe("SILENCE");
  });
});

describe("resolveSpeechActivity", () => {
  it("requires a stronger entry threshold for speech", () => {
    expect(
      resolveSpeechActivity({
        active: false,
        energyDb: -32,
        speechConfidence: 0.58,
        zeroCrossingRate: 0.05,
        pitchConfidence: 0.2,
      }),
    ).toBe(false);
  });

  it("holds active speech through a softer follow-up frame", () => {
    expect(
      resolveSpeechActivity({
        active: true,
        energyDb: -40,
        speechConfidence: 0.41,
        zeroCrossingRate: 0.02,
        pitchConfidence: 0.3,
      }),
    ).toBe(true);
  });
});

describe("shouldEmitStableNote", () => {
  it("accepts a stable, confident note hold", () => {
    expect(
      shouldEmitStableNote({
        frames: 4,
        confidence: 0.82,
        minHz: 438,
        maxHz: 442,
      }),
    ).toBe(true);
  });

  it("rejects unstable pitch spread even with enough frames", () => {
    expect(
      shouldEmitStableNote({
        frames: 5,
        confidence: 0.88,
        minHz: 420,
        maxHz: 460,
      }),
    ).toBe(false);
  });
});
