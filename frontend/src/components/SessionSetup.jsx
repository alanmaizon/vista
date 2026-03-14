import {
  ArrowRight,
  Camera,
  CameraOff,
  MessageSquare,
  Mic,
  MicOff,
  PlayCircle,
  Radio,
  Volume2,
} from "lucide-react";

const FEATURE_CARDS = [
  {
    eyebrow: "Voice",
    title: "Live tutor",
    body: "Talk. Play. Interrupt.",
    Icon: Mic,
    tone:
      "bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.82),transparent_34%),linear-gradient(135deg,#f6f7f8_0%,#dfe4ea_100%)]",
  },
  {
    eyebrow: "Listen",
    title: "Deep feedback",
    body: "Timing. Shape. Clarity.",
    Icon: Volume2,
    tone:
      "bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.72),transparent_28%),linear-gradient(135deg,#dde4eb_0%,#c2ccd8_100%)]",
  },
  {
    eyebrow: "See",
    title: "Score read",
    body: "Frame one bar fast.",
    Icon: Camera,
    tone:
      "bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.78),transparent_30%),linear-gradient(135deg,#f3f0ea_0%,#d5d1c9_100%)]",
  },
  {
    eyebrow: "Loop",
    title: "Follow-ups",
    body: "Ask again in place.",
    Icon: MessageSquare,
    tone:
      "bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.7),transparent_34%),linear-gradient(135deg,#e8ecef_0%,#cbd3da_100%)]",
  },
  {
    eyebrow: "Flow",
    title: "Interrupts",
    body: "Cut in naturally.",
    Icon: Radio,
    tone:
      "bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.78),transparent_32%),linear-gradient(135deg,#f6f7f9_0%,#d7dde4_100%)]",
  },
  {
    eyebrow: "Exit",
    title: "Session recap",
    body: "Leave with next steps.",
    Icon: PlayCircle,
    tone:
      "bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.72),transparent_30%),linear-gradient(135deg,#ebe7df_0%,#d9d3c8_100%)]",
  },
];

const MODE_OPTIONS = [
  { value: "music_tutor", label: "Music tutor" },
  { value: "sight_reading", label: "Sight reading" },
  { value: "technique_practice", label: "Technique" },
  { value: "ear_training", label: "Ear training" },
];

function StatCard({ label, value }) {
  return (
    <div className="border border-slate-300 bg-white px-4 py-4 shadow-[0_14px_28px_rgba(47,52,58,0.04)]">
      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">{label}</div>
      <div className="mt-2 text-sm font-medium text-slate-900">{value}</div>
    </div>
  );
}

function ToggleButton({ active, onClick, activeLabel, idleLabel, ActiveIcon, IdleIcon }) {
  const Icon = active ? ActiveIcon : IdleIcon;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex min-h-12 items-center justify-center gap-2 border px-3 py-3 text-sm font-medium shadow-[6px_6px_0_rgba(184,189,197,0.22)] transition ${
        active ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white text-slate-700"
      }`}
    >
      <Icon className="h-4 w-4" />
      {active ? activeLabel : idleLabel}
    </button>
  );
}

function FeatureCard({ eyebrow, title, body, Icon: icon, tone }) {
  const FeatureIcon = icon;
  return (
    <article className="border border-slate-300 bg-white shadow-[0_18px_42px_rgba(47,52,58,0.05)]">
      <div className={`relative aspect-[1.42/1] overflow-hidden border-b border-slate-300 ${tone}`}>
        <div className="absolute left-3 top-3 flex h-10 w-10 items-center justify-center border border-slate-300 bg-white/88 text-slate-900 shadow-[0_10px_18px_rgba(47,52,58,0.06)]">
          <FeatureIcon className="h-4 w-4" />
        </div>
        <div className="absolute bottom-0 left-0 border-r border-t border-slate-300 bg-white/86 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          {eyebrow}
        </div>
        <div className="absolute bottom-4 right-4 h-[4.5rem] w-[4.5rem] rounded-full border border-white/70 bg-[radial-gradient(circle_at_30%_30%,rgba(255,255,255,0.96),transparent_26%),radial-gradient(circle_at_68%_66%,rgba(201,205,211,0.45),transparent_40%),linear-gradient(180deg,#ffffff_0%,#eceff3_100%)] shadow-[0_24px_52px_rgba(47,52,58,0.1)]" />
      </div>
      <div className="px-4 py-4">
        <h3 className="text-2xl font-semibold tracking-tight text-slate-950">{title}</h3>
        <p className="mt-2 text-sm text-slate-600">{body}</p>
      </div>
    </article>
  );
}

export default function SessionSetup({
  profileDraft,
  setProfileDraft,
  micEnabled,
  cameraEnabled,
  toggleMic,
  toggleCamera,
  startSession,
  isConnecting,
  connectionError,
}) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(184,189,197,0.26),transparent_32%),linear-gradient(180deg,#f8f9fb_0%,#eef1f4_50%,#e7eaee_100%)] text-slate-900">
      <main className="mx-auto w-full max-w-[1340px] px-4 py-4 md:px-6 xl:px-8">
        <section className="glass border border-slate-300/90 px-6 py-6 shadow-[0_28px_58px_rgba(47,52,58,0.08)]">
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
            <div className="flex flex-col justify-between">
              <div>
                <div className="inline-flex items-center gap-3 border border-slate-300 bg-white px-4 py-3 shadow-[0_10px_22px_rgba(47,52,58,0.04)]">
                  <img src="/logo.svg" alt="Eurydice" className="h-4 w-auto" />
                </div>
                <div className="mt-8 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                  Gemini Live Music Tutor
                </div>
                <h1 className="mt-4 text-5xl font-semibold tracking-tight text-slate-950 md:text-6xl">
                  Hear. See. Correct.
                </h1>
                <p className="mt-4 max-w-xl text-lg text-slate-600">
                  Live music coaching for one bar at a time.
                </p>
              </div>

              <div className="mt-8 grid gap-3 md:grid-cols-3">
                <StatCard label="Loop" value="Talk -> Show -> Fix" />
                <StatCard label="Mode" value="Voice + camera" />
                <StatCard label="Stack" value="Gemini + Cloud Run" />
              </div>

              <div className="mt-6 flex flex-wrap gap-3">
                <a
                  href="#entry"
                  className="inline-flex min-h-12 items-center gap-2 border border-slate-900 bg-slate-900 px-5 text-sm font-semibold text-white shadow-[8px_8px_0_rgba(47,52,58,0.16)] transition hover:-translate-x-[2px] hover:-translate-y-[2px]"
                >
                  Enter
                  <ArrowRight className="h-4 w-4" />
                </a>
                <a
                  href="#proofs"
                  className="inline-flex min-h-12 items-center border border-slate-300 bg-white px-5 text-sm font-semibold text-slate-700 shadow-[6px_6px_0_rgba(184,189,197,0.22)]"
                >
                  Proofs
                </a>
              </div>
            </div>

            <form
              id="entry"
              onSubmit={(event) => {
                event.preventDefault();
                void startSession();
              }}
              className="border border-slate-300 bg-white px-4 py-4 shadow-[0_18px_40px_rgba(47,52,58,0.05)]"
            >
              <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Start</div>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">Enter workspace</h2>
              <p className="mt-2 text-sm text-slate-600">Blank fields still work.</p>

              <div className="mt-5 grid gap-3">
                <label className="grid gap-1">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Mode</span>
                  <select
                    value={profileDraft.mode}
                    onChange={(event) =>
                      setProfileDraft((current) => ({ ...current, mode: event.target.value }))
                    }
                    className="min-h-12 border border-slate-300 bg-white px-3 text-sm outline-none focus:border-slate-900"
                  >
                    {MODE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <input
                  value={profileDraft.instrument}
                  onChange={(event) =>
                    setProfileDraft((current) => ({ ...current, instrument: event.target.value }))
                  }
                  placeholder="Instrument"
                  className="min-h-12 border border-slate-300 bg-white px-3 text-sm outline-none focus:border-slate-900"
                />

                <input
                  value={profileDraft.piece}
                  onChange={(event) =>
                    setProfileDraft((current) => ({ ...current, piece: event.target.value }))
                  }
                  placeholder="Piece"
                  className="min-h-12 border border-slate-300 bg-white px-3 text-sm outline-none focus:border-slate-900"
                />

                <textarea
                  value={profileDraft.goal}
                  onChange={(event) =>
                    setProfileDraft((current) => ({ ...current, goal: event.target.value }))
                  }
                  placeholder="Goal"
                  rows={4}
                  className="border border-slate-300 bg-white px-3 py-3 text-sm outline-none focus:border-slate-900"
                />
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2">
                <ToggleButton
                  active={micEnabled}
                  onClick={toggleMic}
                  activeLabel="Mic on"
                  idleLabel="Mic off"
                  ActiveIcon={Mic}
                  IdleIcon={MicOff}
                />
                <ToggleButton
                  active={cameraEnabled}
                  onClick={toggleCamera}
                  activeLabel="Camera on"
                  idleLabel="Camera off"
                  ActiveIcon={Camera}
                  IdleIcon={CameraOff}
                />
              </div>

              <button
                type="submit"
                className="mt-4 flex min-h-13 w-full items-center justify-center gap-2 border border-slate-900 bg-slate-900 px-4 text-sm font-semibold text-white shadow-[8px_8px_0_rgba(47,52,58,0.16)] transition hover:-translate-x-[2px] hover:-translate-y-[2px]"
              >
                {isConnecting ? "Starting" : "Start"}
                <ArrowRight className="h-4 w-4" />
              </button>

              <div className="mt-4 border border-slate-300 bg-[#f8f9fb] px-3 py-3 text-sm text-slate-600">
                Blank fields = general practice.
              </div>

              {connectionError ? (
                <div className="mt-3 border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-700">
                  {connectionError}
                </div>
              ) : null}
            </form>
          </div>
        </section>

        <section id="proofs" className="mt-8">
          <div className="flex items-end justify-between gap-4">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                Sections
              </div>
              <h2 className="mt-2 text-4xl font-semibold tracking-tight text-slate-950">
                One loop. Six proofs.
              </h2>
            </div>
            <div className="hidden text-sm text-slate-500 md:block">Live. Listen. Learn.</div>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {FEATURE_CARDS.map((card) => (
              <FeatureCard key={card.title} {...card} />
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
