import {
  ArrowRight,
  BarChart3,
  BookOpenText,
  Camera,
  Gamepad2,
  Guitar,
  MessageCircleMore,
  Network,
  Route,
  SlidersHorizontal,
  Waves,
} from "lucide-react";

const HERO_POINTS = [
  { label: "Loop", value: "Score -> Play -> Fix" },
  { label: "Mode", value: "Voice + score" },
  { label: "Stack", value: "Gemini + Cloud Run" },
];

const FEATURE_SECTIONS = [
  {
    title: "Live tutor",
    blurb: "Talk. Play. Interrupt.",
    icon: MessageCircleMore,
    image: "/features/conversational-ai-tutor.png",
    kicker: "Voice",
  },
  {
    title: "Deep feedback",
    blurb: "Pitch. Rhythm. Articulation.",
    icon: Waves,
    image: "/features/deep-performance-feedback.png",
    kicker: "Listen",
  },
  {
    title: "Score read",
    blurb: "Frame one bar fast.",
    icon: Camera,
    image: "/features/content-library-repertoire.png",
    kicker: "See",
  },
  {
    title: "Adaptive loops",
    blurb: "Retry with focus.",
    icon: Route,
    image: "/features/adaptive-learning-paths.png",
    kicker: "Coach",
  },
  {
    title: "Playback",
    blurb: "Hear then copy.",
    icon: SlidersHorizontal,
    image: "/features/integrated-playback-accompaniment.png",
    kicker: "Practice",
  },
  {
    title: "Progress",
    blurb: "Track weak spots.",
    icon: BarChart3,
    image: "/features/progress-analytics-dashboard.png",
    kicker: "Measure",
  },
  {
    title: "Library",
    blurb: "Keep pieces ready.",
    icon: BookOpenText,
    image: "/features/content-library-repertoire.png",
    kicker: "Organize",
  },
  {
    title: "Collab",
    blurb: "Share lesson state.",
    icon: Network,
    image: "/features/realtime-collaboration.png",
    kicker: "Share",
  },
  {
    title: "Multi-instrument",
    blurb: "Voice, strings, keys.",
    icon: Guitar,
    image: "/features/multi-instrument-intelligence.png",
    kicker: "Adapt",
  },
];

function FeatureTile({ feature, index }) {
  const Icon = feature.icon;
  const reverseAlignment = index % 2 === 1;

  return (
    <article className="grid min-h-[22rem] border border-slate-300 bg-white shadow-[0_24px_52px_rgba(47,52,58,0.08)]">
      <div className="relative h-56 overflow-hidden border-b border-slate-300 bg-slate-200 md:h-60">
        <img
          src={feature.image}
          alt={`${feature.title} preview`}
          loading="lazy"
          className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.02]"
        />
        <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(15,23,42,0.06),rgba(15,23,42,0.42))]" />
        <div className="absolute left-0 top-0 border-r border-b border-slate-200 bg-white/90 p-3 text-slate-900">
          <Icon className="h-5 w-5" />
        </div>
        <div className="absolute bottom-0 left-0 border-r border-t border-slate-200 bg-white/92 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">
          {feature.kicker}
        </div>
      </div>
      <div className={`flex flex-1 flex-col justify-end gap-3 p-4 md:p-5 ${reverseAlignment ? "items-end text-right" : "items-start text-left"}`}>
        <div>
          <h3 className="text-[1.7rem] font-semibold tracking-[-0.04em] text-slate-900">{feature.title}</h3>
          <p className="mt-2 max-w-[15rem] text-sm text-slate-600">{feature.blurb}</p>
        </div>
      </div>
    </article>
  );
}

export default function LandingPage({
  authStatus,
  errorMessage,
  signingIn,
  email,
  password,
  onEmailChange,
  onPasswordChange,
  onSignIn,
  isTransitioning = false,
}) {
  return (
    <div
      className={`min-h-screen bg-[radial-gradient(circle_at_top,rgba(184,189,197,0.28),transparent_34%),linear-gradient(180deg,#f7f8fa_0%,#eef1f4_54%,#e7eaee_100%)] px-5 py-8 text-slate-800 transition-all duration-400 md:px-8 ${
        isTransitioning ? "pointer-events-none opacity-0" : "opacity-100"
      }`}
    >
      <main className="mx-auto w-full max-w-7xl">
        <section className="grid gap-6 border border-slate-300 bg-white/68 p-5 shadow-[0_30px_60px_rgba(47,52,58,0.08)] lg:grid-cols-[1.12fr_0.88fr] lg:items-start lg:p-6">
          <div className="space-y-6">
            <div className="inline-flex items-center gap-3 border border-slate-300 bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-600 shadow-[0_10px_24px_rgba(47,52,58,0.06)]">
              <img src="/logo.svg" alt="Eurydice" className="h-5 w-5" />
              Eurydice
            </div>

            <div className="space-y-3">
              <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                Gemini live music tutor
              </div>
              <h1 className="max-w-4xl text-5xl font-semibold tracking-[-0.05em] text-slate-950 md:text-7xl">
                Hear. See. Correct.
              </h1>
              <p className="max-w-xl text-base text-slate-600 md:text-lg">Live coaching, one bar at a time.</p>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              {HERO_POINTS.map((item) => (
                <div
                  key={item.label}
                  className="border border-slate-300 bg-white px-4 py-3 shadow-[0_14px_28px_rgba(47,52,58,0.05)]"
                >
                  <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                    {item.label}
                  </div>
                  <div className="mt-2 text-sm font-medium text-slate-900">{item.value}</div>
                </div>
              ))}
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={onSignIn}
                disabled={signingIn}
                className="inline-flex min-h-12 items-center gap-2 border border-slate-900 bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-[8px_8px_0_rgba(47,52,58,0.14)] transition hover:-translate-x-[2px] hover:-translate-y-[2px] hover:shadow-[12px_12px_0_rgba(47,52,58,0.16)] disabled:cursor-wait disabled:opacity-70"
              >
                {signingIn ? "Entering..." : "Enter"}
                <ArrowRight className="h-4 w-4" />
              </button>

              <a
                href="#landing-features"
                className="inline-flex min-h-12 items-center gap-2 border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-800 shadow-[8px_8px_0_rgba(184,189,197,0.32)] transition hover:-translate-x-[2px] hover:-translate-y-[2px] hover:shadow-[12px_12px_0_rgba(184,189,197,0.4)]"
              >
                Features
              </a>
            </div>
          </div>

          <aside className="border border-slate-300 bg-white px-5 py-5 shadow-[0_24px_48px_rgba(47,52,58,0.08)]">
            <div className="flex items-center justify-between gap-3">
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                Start
              </div>
              <Gamepad2 className="h-4 w-4 text-slate-500" />
            </div>

            <h2 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950">Enter</h2>
            <p className="mt-1 text-sm text-slate-600">Sign in or stay guest.</p>

            <div className="mt-4 space-y-3">
              <input
                value={email}
                onChange={(event) => onEmailChange(event.target.value)}
                placeholder="Email"
                className="w-full border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-slate-600 focus:bg-white"
              />
              <input
                value={password}
                onChange={(event) => onPasswordChange(event.target.value)}
                type="password"
                placeholder="Password"
                className="w-full border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-slate-600 focus:bg-white"
              />
            </div>

            <button
              type="button"
              onClick={onSignIn}
              disabled={signingIn}
              className="mt-4 inline-flex min-h-12 w-full items-center justify-center gap-2 border border-slate-900 bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-[8px_8px_0_rgba(47,52,58,0.14)] transition hover:-translate-x-[2px] hover:-translate-y-[2px] hover:shadow-[12px_12px_0_rgba(47,52,58,0.16)] disabled:cursor-wait disabled:opacity-70"
            >
              {signingIn ? "Entering..." : "Start"}
              <ArrowRight className="h-4 w-4" />
            </button>

            <div className="mt-4 border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              {authStatus}
            </div>
            {errorMessage ? (
              <div className="mt-2 border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {errorMessage}
              </div>
            ) : null}
            <div className="mt-3 text-xs text-slate-500">Blank = guest.</div>
          </aside>
        </section>

        <section id="landing-features" className="mt-8 space-y-4">
          <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                Features
              </div>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 md:text-4xl">Nine proof points.</h2>
            </div>
            <div className="text-sm text-slate-600">Talk. Play. Improve.</div>
          </div>

          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {FEATURE_SECTIONS.map((feature, index) => (
              <div key={feature.title} className="group">
                <FeatureTile feature={feature} index={index} />
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
