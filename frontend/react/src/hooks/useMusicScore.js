import { useState, useCallback } from "react";

/**
 * Hook that manages music-score related state extracted from the legacy app.
 *
 * Mirrors key state from the old static/state.js:
 * - activeMusicScoreId, activeMusicMeasures, scorePrepared, musicScoreDirty
 */
export default function useMusicScore() {
  const [scoreId, setScoreId] = useState(null);
  const [measures, setMeasures] = useState([]);
  const [scorePrepared, setScorePrepared] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [scoreLine, setScoreLine] = useState("");

  const resetScore = useCallback(() => {
    setScoreId(null);
    setMeasures([]);
    setScorePrepared(false);
    setDirty(false);
    setScoreLine("");
  }, []);

  const applyScorePayload = useCallback((payload) => {
    if (payload.scoreId) setScoreId(payload.scoreId);
    if (payload.measures) setMeasures(payload.measures);
    setScorePrepared(true);
    setDirty(false);
  }, []);

  const updateScoreLine = useCallback((value) => {
    setScoreLine(value);
    setDirty(true);
    setScorePrepared(false);
    setMeasures([]);
  }, []);

  return {
    scoreId,
    measures,
    scorePrepared,
    dirty,
    scoreLine,
    resetScore,
    applyScorePayload,
    updateScoreLine,
  };
}
