import { ArrowRight, RefreshCw, Radio } from "lucide-react";

function SummaryRow({ label, value }) {
  return (
    <div className="border border-slate-300 bg-white px-4 py-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-2 text-sm font-medium text-slate-900">{value || "General"}</div>
    </div>
  );
}

export default function SessionSummary({ summary, sessionProfile, connectionMeta, onNewSession }) {
  const bullets = Array.isArray(summary?.bullets) ? summary.bullets.filter(Boolean) : [];

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(184,189,197,0.26),transparent_32%),linear-gradient(180deg,#f8f9fb_0%,#eef1f4_50%,#e7eaee_100%)] text-slate-900">
      <main className="mx-auto flex min-h-screen w-full max-w-[980px] items-center px-4 py-10 md:px-6">
        <section className="glass w-full border border-slate-300/90 px-6 py-6 shadow-[0_28px_58px_rgba(47,52,58,0.08)]">
          <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                Session recap
              </div>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950">
                Keep the next step simple.
              </h1>
              <p className="mt-3 max-w-xl text-sm text-slate-600">
                Eurydice closed the live loop and left one clean handoff for the next pass.
              </p>
            </div>

            <button
              type="button"
              onClick={onNewSession}
              className="inline-flex min-h-12 items-center gap-2 border border-slate-900 bg-slate-900 px-5 text-sm font-semibold text-white shadow-[8px_8px_0_rgba(47,52,58,0.16)] transition hover:-translate-x-[2px] hover:-translate-y-[2px]"
            >
              New session
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-6 grid gap-3 md:grid-cols-3">
            <SummaryRow label="Mode" value={sessionProfile?.mode?.replaceAll("_", " ")} />
            <SummaryRow label="Piece" value={sessionProfile?.piece} />
            <SummaryRow label="Transport" value={connectionMeta?.transport} />
          </div>

          <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1fr)_17rem]">
            <div className="border border-slate-300 bg-white px-4 py-4 shadow-[0_14px_28px_rgba(47,52,58,0.04)]">
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                <Radio className="h-3.5 w-3.5" />
                Notes
              </div>
              <div className="mt-4 space-y-3">
                {bullets.length ? (
                  bullets.map((bullet) => (
                    <div key={bullet} className="border border-slate-200 bg-[#f8f9fb] px-3 py-3 text-sm text-slate-700">
                      {bullet}
                    </div>
                  ))
                ) : (
                  <div className="border border-slate-200 bg-[#f8f9fb] px-3 py-3 text-sm text-slate-600">
                    No summary arrived. Start another pass when you are ready.
                  </div>
                )}
              </div>
            </div>

            <div className="border border-slate-300 bg-[#f8f9fb] px-4 py-4 shadow-[0_14px_28px_rgba(47,52,58,0.04)]">
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                Reset
              </div>
              <p className="mt-3 text-sm text-slate-600">
                Keep the profile or change it. The next session will clear the previous transcript.
              </p>
              <button
                type="button"
                onClick={onNewSession}
                className="mt-5 inline-flex min-h-12 w-full items-center justify-center gap-2 border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 shadow-[6px_6px_0_rgba(184,189,197,0.22)]"
              >
                <RefreshCw className="h-4 w-4" />
                Back to setup
              </button>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
