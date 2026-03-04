import { describe, it, expect } from "vitest";
import { midiToFrequency } from "../playback";

describe("midiToFrequency", () => {
  it("returns 440 Hz for MIDI note 69 (A4)", () => {
    expect(midiToFrequency(69)).toBeCloseTo(440, 1);
  });

  it("returns ~261.63 Hz for MIDI note 60 (C4)", () => {
    expect(midiToFrequency(60)).toBeCloseTo(261.63, 0);
  });

  it("returns ~880 Hz for MIDI note 81 (A5)", () => {
    expect(midiToFrequency(81)).toBeCloseTo(880, 0);
  });

  it("doubles frequency for each octave (12 semitones)", () => {
    const f1 = midiToFrequency(60);
    const f2 = midiToFrequency(72);
    expect(f2 / f1).toBeCloseTo(2.0, 5);
  });
});
