import { useState } from "react";
import { Activity, FileMusic, NotebookPen, Waves } from "lucide-react";
import ConversationPanel from "./ConversationPanel";
import OrbLayer from "./OrbLayer";
import WorkspaceControls from "./WorkspaceControls";
import {
  ComposerPanel,
  LiveFeedPanel,
  RenderedScorePanel,
} from "./ScoreWorkspace";
import { LessonPanel, SessionLog } from "./StatusPanels";

const INSPECTOR_ITEMS = [
  { key: "notation", label: "Notation", icon: FileMusic },
  { key: "capture", label: "Capture feed", icon: Waves },
  { key: "analysis", label: "Analysis", icon: Activity },
  { key: "session", label: "Session log", icon: NotebookPen },
];

function InspectorToggle({ label, icon, active, onClick }) {
  const IconComponent = icon;

  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition ${
        active
          ? "border-sky-300/30 bg-sky-400/15 text-sky-100"
          : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"
      }`}
    >
      <IconComponent className="h-4 w-4" />
      {label}
    </button>
  );
}

function InspectorSurface({
  activeInspector,
  scoreWorkspaceProps,
  lessonPanelProps,
  sessionLogProps,
}) {
  if (!activeInspector) {
    return (
      <div className="rounded-[1.8rem] border border-dashed border-white/10 bg-white/[0.03] px-5 py-5 text-sm text-slate-400">
        Open notation, capture feed, analysis, or session log only when you need it.
      </div>
    );
  }

  if (activeInspector === "notation") {
    return (
      <div className="space-y-4">
        <ComposerPanel {...scoreWorkspaceProps} />
        <RenderedScorePanel {...scoreWorkspaceProps} />
      </div>
    );
  }

  if (activeInspector === "capture") {
    return <LiveFeedPanel {...scoreWorkspaceProps} />;
  }

  if (activeInspector === "analysis") {
    return <LessonPanel {...lessonPanelProps} />;
  }

  return <SessionLog {...sessionLogProps} />;
}

export default function WorkspaceView({
  authStatus,
  orbProps,
  orbLayerProps,
  playbackAudioElementRef,
  controlsProps,
  conversationProps,
  scoreWorkspaceProps,
  lessonPanelProps,
  sessionLogProps,
}) {
  const [activeInspector, setActiveInspector] = useState(null);

  const toggleInspector = (panelKey) => {
    setActiveInspector((current) => (current === panelKey ? null : panelKey));
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(96,165,250,0.18),transparent_38%),linear-gradient(180deg,#081225_0%,#09162b_44%,#07101e_100%)] text-slate-100">
      <main className="mr-auto w-full max-w-[1440px] px-4 py-5 md:px-6 xl:pl-10 xl:pr-8 2xl:pl-14">
        <header className="mb-5 flex flex-col gap-3 rounded-[1.8rem] border border-white/10 bg-white/[0.04] px-5 py-4 backdrop-blur-md md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-200">
              Eurydice
            </div>
            <div className="mt-2 text-sm text-slate-300">
              Minimal music workstation for guided capture, playback, and review.
            </div>
          </div>
          <div className="max-w-full truncate rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-medium text-slate-300 md:max-w-[22rem]">
            {authStatus}
          </div>
        </header>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem] xl:items-start">
          <section className="space-y-4">
            <OrbLayer orbProps={orbProps} {...orbLayerProps} />
            <ConversationPanel {...conversationProps} />

            <div className="rounded-[1.8rem] border border-white/10 bg-white/[0.04] px-4 py-4 backdrop-blur-md">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                    Secondary tools
                  </div>
                  <div className="mt-1 text-sm text-slate-300">
                    Keep the workspace quiet by opening one inspector at a time.
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {INSPECTOR_ITEMS.map((item) => (
                    <InspectorToggle
                      key={item.key}
                      label={item.label}
                      icon={item.icon}
                      active={activeInspector === item.key}
                      onClick={() => toggleInspector(item.key)}
                    />
                  ))}
                </div>
              </div>

              <div className="mt-4">
                <InspectorSurface
                  activeInspector={activeInspector}
                  scoreWorkspaceProps={scoreWorkspaceProps}
                  lessonPanelProps={lessonPanelProps}
                  sessionLogProps={sessionLogProps}
                />
              </div>
            </div>
          </section>

          <WorkspaceControls {...controlsProps} />
        </div>

        <audio ref={playbackAudioElementRef} preload="auto" className="hidden" aria-hidden="true" />
      </main>
    </div>
  );
}
