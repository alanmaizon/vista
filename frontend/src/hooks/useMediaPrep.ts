import { useEffect, useState } from "react";

type BusyKind = "microphone" | "camera" | null;

export function useMediaPrep() {
  const [microphoneReady, setMicrophoneReady] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [worksheetAttached, setWorksheetAttached] = useState(false);
  const [worksheetName, setWorksheetName] = useState<string | null>(null);
  const [worksheetPreviewUrl, setWorksheetPreviewUrl] = useState<string | null>(null);
  const [busyKind, setBusyKind] = useState<BusyKind>(null);
  const [error, setError] = useState<string | null>(null);

  const supportsMediaDevices =
    typeof navigator !== "undefined" &&
    Boolean(navigator.mediaDevices?.getUserMedia);

  useEffect(() => {
    return () => {
      if (worksheetPreviewUrl) {
        URL.revokeObjectURL(worksheetPreviewUrl);
      }
    };
  }, [worksheetPreviewUrl]);

  async function requestMicrophone() {
    if (!supportsMediaDevices) {
      setError("This browser does not expose media device APIs.");
      return;
    }

    setBusyKind("microphone");
    setError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      setMicrophoneReady(true);
    } catch {
      setError("Microphone permission was not granted.");
    } finally {
      setBusyKind(null);
    }
  }

  async function requestCamera() {
    if (!supportsMediaDevices) {
      setError("This browser does not expose media device APIs.");
      return;
    }

    setBusyKind("camera");
    setError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      stream.getTracks().forEach((track) => track.stop());
      setCameraReady(true);
    } catch {
      setError("Camera permission was not granted.");
    } finally {
      setBusyKind(null);
    }
  }

  function setWorksheet(file: File | null) {
    if (worksheetPreviewUrl) {
      URL.revokeObjectURL(worksheetPreviewUrl);
    }

    if (!file) {
      setWorksheetAttached(false);
      setWorksheetName(null);
      setWorksheetPreviewUrl(null);
      return;
    }

    setWorksheetAttached(true);
    setWorksheetName(file.name);
    setWorksheetPreviewUrl(URL.createObjectURL(file));
    setError(null);
  }

  return {
    busyKind,
    cameraReady,
    error,
    microphoneReady,
    requestCamera,
    requestMicrophone,
    setWorksheet,
    supportsMediaDevices,
    worksheetAttached,
    worksheetName,
    worksheetPreviewUrl,
  };
}

