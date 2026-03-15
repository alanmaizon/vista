type AudioContextOptionsWithId = AudioContextOptions & {
  id?: string;
};

const audioContextMap = new Map<string, AudioContext>();

function getAudioContextConstructor() {
  const browserWindow = window as typeof window & {
    webkitAudioContext?: typeof AudioContext;
  };

  return window.AudioContext ?? browserWindow.webkitAudioContext;
}

export const getSharedAudioContext = (() => {
  const didInteract = new Promise<void>((resolve) => {
    window.addEventListener("pointerdown", () => resolve(), { once: true });
    window.addEventListener("keydown", () => resolve(), { once: true });
  });

  return async (options?: AudioContextOptionsWithId): Promise<AudioContext> => {
    const AudioContextConstructor = getAudioContextConstructor();
    if (!AudioContextConstructor) {
      throw new Error("This browser does not support Web Audio.");
    }

    const existingId = options?.id;
    if (existingId && audioContextMap.has(existingId)) {
      return audioContextMap.get(existingId)!;
    }

    try {
      const unlockAudio = new Audio();
      unlockAudio.src =
        "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA";
      await unlockAudio.play();
    } catch {
      await didInteract;
    }

    const audioContext = new AudioContextConstructor(options);
    if (existingId) {
      audioContextMap.set(existingId, audioContext);
    }
    return audioContext;
  };
})();
