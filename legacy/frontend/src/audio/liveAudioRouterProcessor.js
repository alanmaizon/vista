class LiveAudioRouterProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    const channel = input?.[0];
    if (channel?.length) {
      this.port.postMessage(channel.slice());
    }
    return true;
  }
}

registerProcessor("live-audio-router-processor", LiveAudioRouterProcessor);
