import { Music4, Sparkles, Waves } from "lucide-react";
import AudioReactiveOrb from "./AudioReactiveOrb";
import AuthPanel from "./AuthPanel";
import {
  ComposerPanel,
  LiveFeedPanel,
  RenderedScorePanel,
} from "./ScoreWorkspace";
import { LessonPanel, SessionLog } from "./StatusPanels";

export default function AppLayout({
  authStatus,
  orbProps,
  playbackAudioElementRef,
  authPanelProps,
  scoreWorkspaceProps,
  lessonPanelProps,
  sessionLogProps,
}) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(96,165,250,0.2),_transparent_40%),linear-gradient(180deg,#081225_0%,#09162b_45%,#07101e_100%)] text-slate-100">
      <main className="mr-auto w-full max-w-[1480px] px-4 py-6 md:px-6 xl:pl-10 xl:pr-8 2xl:pl-14">
        <header className="glass workspace-orb-panel relative mb-6 overflow-hidden rounded-[2rem] px-6 py-5">
          <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02)_48%,rgba(56,189,248,0.05))]" />
          <div className="workspace-orb-shell absolute right-[-3.5rem] top-1/2 -translate-y-1/2">
            <AudioReactiveOrb
              audioSource={orbProps.audioSource}
              audioElement={orbProps.audioElement}
              active={orbProps.active}
              intensity={orbProps.intensity}
              size="workspace"
              theme={orbProps.theme}
              performanceMode={orbProps.performanceMode}
            />
          </div>
          <div className="relative z-10 flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
            <div className="max-w-4xl">
              <div className="flex items-center gap-2 text-sky-300">
                <Music4 className="h-5 w-5" />
                <span className="text-xs font-semibold uppercase tracking-[0.24em]">Eurydice</span>
              </div>
              <h1 className="mt-2 text-2xl font-semibold text-white md:text-3xl">
                Music-AI workstation for guided capture, analysis, and notation
              </h1>
              <p className="mt-2 max-w-3xl text-sm text-slate-300">
                Controls stay on the left, live capture stays in focus, analytics stay visible, and the score remains a wide composition canvas.
              </p>
            </div>

            <div className="grid gap-2 text-sm text-slate-300 sm:grid-cols-3">
              <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                  <Waves className="h-3.5 w-3.5 text-sky-300" />
                  Session
                </div>
                <div className="mt-1 font-medium text-white">{authStatus}</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                  <Sparkles className="h-3.5 w-3.5 text-sky-300" />
                  Focus
                </div>
                <div className="mt-1 font-medium text-white">Capture → Compare → Review</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Render mode</div>
                <div className="mt-1 font-medium text-white">
                  {orbProps.performanceMode === "lite" ? "Low-power default" : "Adaptive"}
                </div>
              </div>
            </div>
          </div>
        </header>

        <div className="grid gap-6 xl:grid-cols-[20rem_minmax(0,1.2fr)_22rem] xl:items-start">
          <aside className="space-y-6">
            <AuthPanel {...authPanelProps} />
          </aside>

          <section className="space-y-6">
            <ComposerPanel {...scoreWorkspaceProps} />
            <LiveFeedPanel {...scoreWorkspaceProps} />
          </section>

          <aside className="space-y-6">
            <LessonPanel {...lessonPanelProps} />
            <SessionLog {...sessionLogProps} />
          </aside>
        </div>

        <section className="mt-6">
          <RenderedScorePanel {...scoreWorkspaceProps} />
        </section>

        <audio ref={playbackAudioElementRef} preload="auto" className="hidden" aria-hidden="true" />
      </main>
    </div>
  );
}
