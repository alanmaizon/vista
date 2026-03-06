import { useEffect } from "react";
import {
  BarChart3,
  BookOpenText,
  ChevronDown,
  Gamepad2,
  Guitar,
  MessageCircleMore,
  Network,
  Route,
  SlidersHorizontal,
  Waves,
} from "lucide-react";

const HERO_STATS = [
  { label: "Lesson Flow", value: "Score -> Perform -> Feedback" },
  { label: "Core Engine", value: "Deterministic + Live AI" },
  { label: "Mode", value: "Voice-first Music Tutoring" },
];

const FEATURE_SECTIONS = [
  {
    title: "Deep Performance Feedback",
    description:
      "Eurydice listens with bar-level precision and explains where pitch, timing, or articulation drifted. Feedback is immediate, specific, and actionable so every repetition has purpose.",
    icon: Waves,
    image: "/features/deep-performance-feedback.png",
  },
  {
    title: "Adaptive Learning Paths",
    description:
      "Lessons evolve based on how you actually play, not a fixed script. Eurydice adjusts tempo, complexity, and repetition patterns to keep challenge and momentum balanced.",
    icon: Route,
    image: "/features/adaptive-learning-paths.png",
  },
  {
    title: "Progress Analytics & Teacher Dashboard",
    description:
      "Track improvement over sessions with measurable performance signals and progression snapshots. Teachers can review attempts quickly and focus live instruction where it matters most.",
    icon: BarChart3,
    image: "/features/progress-analytics-dashboard.png",
  },
  {
    title: "Multi-Instrument Intelligence",
    description:
      "From voice to strings to keys, Eurydice adapts recognition and coaching to instrument context. The same lesson loop supports technique-specific interpretation without fragmenting your workflow.",
    icon: Guitar,
    image: "/features/multi-instrument-intelligence.png",
  },
  {
    title: "Gamified Practice",
    description:
      "Structured streaks, milestones, and challenge loops turn repetition into progress-driven play. Motivation is tied to musical quality, not shallow interaction metrics.",
    icon: Gamepad2,
    image: "/features/gamified-practice.png",
  },
  {
    title: "Integrated Playback & Accompaniment",
    description:
      "Hear target phrases instantly, loop difficult bars, and practice with responsive accompaniment. Eurydice keeps playback and guidance in one coherent practice surface.",
    icon: SlidersHorizontal,
    image: "/features/integrated-playback-accompaniment.png",
  },
  {
    title: "Real-Time Collaboration",
    description:
      "Students, teachers, and peers can align on the same score context and performance feedback in real time. Collaboration flows through shared musical artifacts, not disconnected chat threads.",
    icon: Network,
    image: "/features/realtime-collaboration.png",
  },
  {
    title: "Content Library & Repertoire",
    description:
      "Build a structured catalog of songs, exercises, and practice variants mapped to your goals. Eurydice keeps each repertoire item tied to measurable progress and lesson history.",
    icon: BookOpenText,
    image: "/features/content-library-repertoire.png",
  },
  {
    title: "Conversational AI Music Tutor",
    description:
      "Ask naturally, play immediately, and receive coaching that understands both musical intent and performance reality. Eurydice is designed as a live tutor, not a static notation viewer.",
    icon: MessageCircleMore,
    image: "/features/conversational-ai-tutor.png",
  },
];

function FeatureCard({ feature, index }) {
  const Icon = feature.icon;
  const isLight = index % 2 === 0;

  return (
    <section
      className={`parallax-section relative isolate flex min-h-[90vh] items-center overflow-hidden px-5 py-20 md:px-10 ${
        isLight ? "bg-slate-100 text-slate-900" : "bg-slate-900 text-slate-100"
      }`}
    >
      <div className="parallax-bg" aria-hidden />
      <div className="mx-auto grid w-full max-w-6xl gap-8 md:grid-cols-[0.9fr_1.1fr] md:items-center">
        <div
          className={`glass rounded-3xl p-7 ${
            isLight ? "border-slate-300/70 bg-white/70 text-slate-700" : "border-white/15 bg-white/5 text-slate-300"
          }`}
        >
          <div
            className={`mb-5 inline-flex h-16 w-16 items-center justify-center rounded-2xl ${
              isLight ? "bg-sky-100 text-sky-700" : "bg-sky-400/15 text-sky-200"
            }`}
          >
            <Icon className="h-8 w-8" />
          </div>
          <h3
            className={`mt-3 text-3xl font-semibold md:text-4xl ${isLight ? "text-slate-900" : "text-white"}`}
          >
            {feature.title}
          </h3>
          <p className="mt-4 text-base leading-relaxed md:text-lg">{feature.description}</p>
        </div>
        <div
          className={`aspect-square w-full overflow-hidden rounded-3xl border ${
            isLight
              ? "border-slate-300/70 bg-white/80 text-slate-700"
              : "border-white/15 bg-slate-950/35 text-slate-300"
          }`}
        >
          <img
            src={feature.image}
            alt={`${feature.title} preview`}
            loading="lazy"
            className="h-full w-full object-cover"
          />
        </div>
      </div>
    </section>
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
  useEffect(() => {
    const targets = Array.from(document.querySelectorAll(".feature-observe"));
    if (!targets.length) {
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) {
            continue;
          }
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      },
      {
        root: null,
        rootMargin: "0px 0px -12% 0px",
        threshold: 0.22,
      },
    );

    for (const node of targets) {
      observer.observe(node);
    }

    return () => observer.disconnect();
  }, []);

  return (
    <div
      className={`text-slate-100 transition-all duration-500 ${
        isTransitioning ? "pointer-events-none scale-[1.01] opacity-0 blur-[2px]" : "opacity-100"
      }`}
    >
      <section className="landing-hero-gradient relative flex min-h-screen items-center justify-center overflow-hidden px-5 py-16 text-center">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(56,189,248,0.16),transparent_40%),radial-gradient(circle_at_80%_80%,rgba(99,102,241,0.14),transparent_36%)]" />
        <div className="relative z-10 mx-auto max-w-4xl">
          <div className="mb-6 inline-flex items-center rounded-full border border-white/20 bg-white/8 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-sky-200">
            Gemini Live Agent Challenge
          </div>
          <img
            src="/logo.svg"
            alt="Eurydice"
            className="mx-auto mb-7 h-24 w-24 rounded-3xl border border-white/20 bg-white/10 p-3 shadow-[0_18px_48px_rgba(56,189,248,0.32)]"
          />
          <h1 className="text-5xl font-semibold tracking-tight text-white md:text-7xl">Eurydice</h1>
          <p className="mt-4 text-lg text-slate-300 md:text-2xl">An Intelligent Digital Music Tutor</p>
          <p className="mx-auto mt-5 max-w-3xl text-sm leading-relaxed text-slate-300 md:text-base">
            Learn a song end to end with one continuous workflow: read notation, hear target phrases,
            perform bar by bar, and receive clear coaching in real time.
          </p>
          <div className="mx-auto mt-8 grid max-w-3xl gap-3 text-left sm:grid-cols-3">
            {HERO_STATS.map((item) => (
              <div
                key={item.label}
                className="rounded-2xl border border-white/15 bg-white/6 px-4 py-3 backdrop-blur-md"
              >
                <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-300">
                  {item.label}
                </div>
                <div className="mt-1 text-sm font-medium text-white">{item.value}</div>
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={onSignIn}
            disabled={signingIn}
            className="landing-cta mt-10 rounded-2xl bg-sky-400 px-10 py-3 text-lg font-semibold text-slate-950 transition hover:-translate-y-0.5 hover:bg-sky-300 hover:shadow-[0_18px_35px_rgba(56,189,248,0.34)] disabled:cursor-wait disabled:opacity-75"
          >
            {signingIn ? "Signing In..." : "Sign In to Start"}
          </button>
          <p className="mt-4 text-sm text-slate-300">{authStatus}</p>
          {errorMessage ? <p className="mt-2 text-sm text-rose-300">{errorMessage}</p> : null}
          <div className="mx-auto mt-7 grid w-full max-w-2xl gap-2 rounded-2xl border border-white/15 bg-white/5 p-4 text-left md:grid-cols-2">
            <input
              value={email}
              onChange={(event) => onEmailChange(event.target.value)}
              placeholder="Email (optional)"
              className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-sky-300/60"
            />
            <input
              value={password}
              onChange={(event) => onPasswordChange(event.target.value)}
              type="password"
              placeholder="Password (optional)"
              className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-sky-300/60"
            />
            <p className="md:col-span-2 text-xs text-slate-300">
              Leave both blank for anonymous challenge sign-in.
            </p>
          </div>
        </div>
        <a
          href="#eurydice-features"
          className="absolute bottom-8 left-1/2 -translate-x-1/2 text-slate-300 transition hover:text-white"
        >
          <ChevronDown className="h-7 w-7 animate-bounce" />
        </a>
      </section>

      <div id="eurydice-features">
        {FEATURE_SECTIONS.map((feature, index) => (
          <div
            key={feature.title}
            className="feature-observe"
            style={{ transitionDelay: `${(index % 3) * 90}ms` }}
          >
            <FeatureCard feature={feature} index={index} />
          </div>
        ))}
      </div>
    </div>
  );
}
