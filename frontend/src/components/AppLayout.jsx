import { Music4 } from "lucide-react";
import AuthPanel from "./AuthPanel";
import SkillSelector from "./SkillSelector";
import ScoreWorkspace from "./ScoreWorkspace";
import { LessonPanel, SessionLog } from "./StatusPanels";

export default function AppLayout({
  skills,
  authStatus,
  skill,
  onSkillChange,
  authPanelProps,
  scoreWorkspaceProps,
  lessonPanelProps,
  sessionLogProps,
}) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(96,165,250,0.2),_transparent_40%),linear-gradient(180deg,#081225_0%,#09162b_45%,#07101e_100%)] text-slate-100">
      <main className="mx-auto max-w-7xl px-4 py-6 md:px-6">
        <header className="glass mb-6 rounded-3xl px-5 py-4">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="flex items-center gap-2 text-sky-300">
                <Music4 className="h-5 w-5" />
                <span className="text-xs font-semibold uppercase tracking-[0.24em]">Eurydice</span>
              </div>
              <h1 className="mt-2 text-2xl font-semibold text-white md:text-3xl">
                End-to-end musical guidance in one lesson loop
              </h1>
              <p className="mt-2 max-w-3xl text-sm text-slate-300">
                Sign in, prepare a phrase or score, and use one guided surface for capture,
                comparison, and feedback.
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
              <div className="font-medium text-white">Auth</div>
              <div className="mt-1">{authStatus}</div>
            </div>
          </div>
        </header>

        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <section className="space-y-6">
            <SkillSelector skills={skills} skill={skill} onChange={onSkillChange} />
            <AuthPanel {...authPanelProps} />
            <ScoreWorkspace {...scoreWorkspaceProps} />
          </section>

          <section className="space-y-6">
            <LessonPanel {...lessonPanelProps} />
            <SessionLog {...sessionLogProps} />
          </section>
        </div>
      </main>
    </div>
  );
}
