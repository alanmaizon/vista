const volMeterWorklet = `
class VolMeterWorklet extends AudioWorkletProcessor {
  volume = 0;
  updateIntervalInMs = 25;
  nextUpdateFrame = this.updateIntervalInMs;

  constructor() {
    super();
    this.port.onmessage = (event) => {
      if (event.data.updateIntervalInMs) {
        this.updateIntervalInMs = event.data.updateIntervalInMs;
      }
    };
  }

  get intervalInFrames() {
    return (this.updateIntervalInMs / 1000) * sampleRate;
  }

  process(inputs) {
    const input = inputs[0];

    if (input.length > 0) {
      const samples = input[0];
      let sum = 0;

      for (let index = 0; index < samples.length; index += 1) {
        sum += samples[index] * samples[index];
      }

      const rms = Math.sqrt(sum / samples.length);
      this.volume = Math.max(rms, this.volume * 0.7);

      this.nextUpdateFrame -= samples.length;
      if (this.nextUpdateFrame < 0) {
        this.nextUpdateFrame += this.intervalInFrames;
        this.port.postMessage({ volume: this.volume });
      }
    }

    return true;
  }
}
`;

export default volMeterWorklet;

