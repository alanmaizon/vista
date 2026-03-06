import { useState } from "react";
import { Activity, FileMusic, NotebookPen, Sparkles, Waves } from "lucide-react";
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

const WORKSPACE_FEATURES = [
  {
    title: "Conversational tutoring",
    description: "Gemini Live stays available as a guided music partner once you explicitly start the session.",
  },
  {
    title: "Deterministic review",
    description: "Capture, transcribe, and compare phrases against notation with stable feedback from the music engine.",
  },
  {
    title: "Camera and notation loop",
    description: "Bring score reading, bar preparation, and playback into the same studio instead of splitting tools.",
  },
];

function InspectorToggle({ label, icon, active, onClick }) {
  const IconComponent = icon;

  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition ${
        active
          ? "border-slate-400 bg-slate-900 text-white"
          : "border-slate-300 bg-white/85 text-slate-600 hover:bg-white"
      }`}
    >
      <IconComponent className="h-4 w-4" />
      {label}
    </button>
  );
}

function WorkspaceOnboarding() {
  return (
    <div className="rounded-[1.8rem] border border-slate-300/90 bg-white/78 px-5 py-5 shadow-[0_18px_38px_rgba(47,52,58,0.05)]">
      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        <Sparkles className="h-4 w-4 text-slate-700" />
        Workspace onboarding
      </div>
      <div className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-600">
        The landing page stays deliberately quiet. The feature story lives here instead, inside the
        workspace, once you are ready to explore the full tutoring surface.
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        {WORKSPACE_FEATURES.map((feature) => (
          <div
            key={feature.title}
            className="rounded-[1.5rem] border border-slate-300 bg-[#f8f9fb] px-4 py-4"
          >
            <div className="text-sm font-semibold text-slate-900">{feature.title}</div>
            <div className="mt-2 text-sm leading-relaxed text-slate-600">{feature.description}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function InspectorSurface({
  activeInspector,
  scoreWorkspaceProps,
  lessonPanelProps,
  sessionLogProps,
}) {
  if (!activeInspector) {
    return <WorkspaceOnboarding />;
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
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(184,189,197,0.24),transparent_34%),linear-gradient(180deg,#f7f8fa_0%,#eef1f4_52%,#e6e8eb_100%)] text-slate-800">
      <main className="mr-auto w-full max-w-[1440px] px-4 py-5 md:px-6 xl:pl-10 xl:pr-8 2xl:pl-14">
        <header className="mb-5 flex flex-col gap-3 rounded-[1.8rem] border border-slate-300/90 bg-white/78 px-5 py-4 backdrop-blur-md md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
              Eurydice
            </div>
            <div className="mt-2 text-sm text-slate-600">
              Minimal music workstation for guided capture, playback, and review.
            </div>
          </div>
          <div className="max-w-full truncate rounded-full border border-slate-300 bg-white px-4 py-2 text-xs font-medium text-slate-600 md:max-w-[22rem]">
            {authStatus}
          </div>
        </header>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem] xl:items-start">
          <section className="space-y-4">
            <OrbLayer {...orbLayerProps} />
            <ConversationPanel {...conversationProps} />

            <div className="rounded-[1.8rem] border border-slate-300/90 bg-white/72 px-4 py-4 backdrop-blur-md">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                    Secondary tools
                  </div>
                  <div className="mt-1 text-sm text-slate-600">
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
