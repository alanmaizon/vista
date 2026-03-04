import { useState, useMemo, useCallback } from "react";
import { SessionContext } from "./sessionContextValue";

/**
 * Provides session-level state shared across the application.
 *
 * Consolidates state that was previously global in static/state.js:
 * - authentication, session metadata, media toggles, skill/mode selection.
 */
export function SessionProvider({ children }) {
  const [user, setUser] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [skill, setSkill] = useState("HEAR_PHRASE");
  const [status, setStatus] = useState("idle"); // idle | connecting | connected | error
  const [riskMode, setRiskMode] = useState("NORMAL");
  const [micEnabled, setMicEnabled] = useState(true);
  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [captions, setCaptions] = useState([]);

  const addCaption = useCallback((role, text) => {
    setCaptions((prev) => [...prev, { role, text, ts: Date.now() }]);
  }, []);

  const clearCaptions = useCallback(() => setCaptions([]), []);

  const resetSession = useCallback(() => {
    setSessionId(null);
    setStatus("idle");
    setRiskMode("NORMAL");
    setCaptions([]);
  }, []);

  const value = useMemo(
    () => ({
      user,
      setUser,
      sessionId,
      setSessionId,
      skill,
      setSkill,
      status,
      setStatus,
      riskMode,
      setRiskMode,
      micEnabled,
      setMicEnabled,
      cameraEnabled,
      setCameraEnabled,
      captions,
      addCaption,
      clearCaptions,
      resetSession,
    }),
    [user, sessionId, skill, status, riskMode, micEnabled, cameraEnabled, captions, addCaption, clearCaptions, resetSession],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
