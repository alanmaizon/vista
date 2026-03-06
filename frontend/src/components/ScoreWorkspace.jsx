function noteClass({ active, mismatch }) {
  if (mismatch === "pitch") {
    return "border-red-300 bg-red-50 text-red-900";
  }
  if (mismatch === "rhythm") {
    return "border-amber-300 bg-amber-50 text-amber-900";
  }
  if (active) {
    return "border-sky-300 bg-sky-50 text-sky-900";
  }
  return "border-slate-200 bg-white text-slate-700";
}

export default function ScoreWorkspace({
  activeScore,
  activeNoteRange,
  comparisonStateByIndex,
  scoreLine,
  onScoreLineChange,
  isPlaying,
  detectedTempo,
  tempoOverride,
  onTempoOverrideChange,
  onPlayScore,
  onPlayAnalysis,
  hasAnalysisPlayback,
  videoRef,
  isReadingScore,
  lessonState,
}) {
  return (
    <>
      <div className="glass rounded-3xl p-5">
        <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
          Score line
        </label>
        <textarea
          value={scoreLine}
          onChange={(event) => onScoreLineChange(event.target.value)}
          rows={3}
          className="mt-3 w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-3 text-sm text-slate-100 outline-none focus:border-sky-300/60"
          placeholder="C4/q D4/q E4/h | G4/q A4/q B4/h"
        />
        <div className="mt-3 text-xs text-slate-400">
          Guided Lesson uses this draft unless you capture a bar directly from the live camera reader.
        </div>
      </div>

      <div className="glass rounded-3xl p-5">
        <div className="flex items-center justify-between">
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">Live feed</div>
          {isReadingScore ? (
            <span className="rounded-full border border-emerald-300/30 bg-emerald-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-200">
              Reading from camera
            </span>
          ) : null}
        </div>
        <div className="mt-4 overflow-hidden rounded-3xl border border-white/10 bg-slate-950/60">
          <video ref={videoRef} autoPlay muted playsInline className="aspect-video w-full object-cover" />
        </div>
        <div className="mt-3 text-xs text-slate-400">
          Camera capture is only used during the live score reader. It sends one JPEG frame per second while connected.
        </div>
      </div>

      <div className="glass rounded-3xl p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">Rendered score</div>
            {detectedTempo ? (
              <div className="mt-2 text-xs text-slate-400">Detected phrase tempo: {Math.round(detectedTempo)} BPM</div>
            ) : null}
          </div>
          <div className="flex flex-col gap-2 md:items-end">
            {lessonState.measureIndex != null ? (
              <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-300">
                Bar {lessonState.measureIndex}
              </div>
            ) : null}
            <div className="flex flex-wrap items-center gap-2">
              <input
                value={tempoOverride}
                onChange={(event) => onTempoOverrideChange(event.target.value)}
                inputMode="numeric"
                placeholder="Tempo"
                className="w-24 rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-300/60"
              />
              <button
                type="button"
                onClick={onPlayScore}
                disabled={isPlaying || !activeScore?.measures?.length}
                className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-100 transition hover:bg-white/10 disabled:cursor-wait disabled:opacity-60"
              >
                {isPlaying ? "Playing..." : "Play score"}
              </button>
              <button
                type="button"
                onClick={onPlayAnalysis}
                disabled={isPlaying || !hasAnalysisPlayback}
                className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-100 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Play phrase
              </button>
            </div>
          </div>
        </div>
        <div className="mt-4 rounded-3xl border border-slate-200 bg-white p-5 text-slate-900">
          {activeScore?.svg ? (
            <div dangerouslySetInnerHTML={{ __html: activeScore.svg }} />
          ) : activeScore?.musicxml ? (
            <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-slate-700">{activeScore.musicxml}</pre>
          ) : (
            <div className="text-sm text-slate-500">Prepare a lesson to render notation here.</div>
          )}
        </div>

        {activeScore?.expected_notes?.length ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {activeScore.expected_notes.map((note, index) => {
              const active = activeNoteRange && index >= activeNoteRange.start && index < activeNoteRange.end;
              const mismatch = comparisonStateByIndex.get(index);
              return (
                <span
                  key={`${note.note_name}-${index}`}
                  className={`rounded-full border px-3 py-1 text-xs font-medium ${noteClass({
                    active,
                    mismatch,
                  })}`}
                >
                  {note.note_name}
                </span>
              );
            })}
          </div>
        ) : null}
      </div>
    </>
  );
}
