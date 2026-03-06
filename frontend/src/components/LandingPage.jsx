const ENTRY_POINTS = [
  {
    label: "Live tutoring",
    description: "Conversational guidance, deterministic analysis, and lesson flow in one workspace.",
  },
  {
    label: "Performance review",
    description: "Capture a phrase, compare it against notation, and surface focused coaching.",
  },
  {
    label: "Notation workflow",
    description: "Draft, render, and review bars without leaving the same studio surface.",
  },
];

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
      className={`min-h-screen bg-[radial-gradient(circle_at_top,rgba(184,189,197,0.3),transparent_30%),linear-gradient(180deg,#f8f9fb_0%,#eef1f4_52%,#e6e8eb_100%)] px-5 py-10 text-slate-800 transition-all duration-400 md:px-8 ${
        isTransitioning ? "pointer-events-none opacity-0" : "opacity-100"
      }`}
    >
      <main className="mx-auto grid min-h-[calc(100vh-5rem)] w-full max-w-6xl gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
        <section className="space-y-6">
          <div className="inline-flex items-center rounded-full border border-slate-300 bg-white/75 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500 shadow-[0_12px_30px_rgba(47,52,58,0.06)]">
            Eurydice
          </div>

          <div className="space-y-4">
            <img
              src="/logo.svg"
              alt="Eurydice"
              className="h-18 w-18 rounded-3xl border border-slate-300 bg-white/80 p-3 shadow-[0_18px_44px_rgba(47,52,58,0.08)]"
            />
            <div>
              <h1 className="max-w-3xl text-5xl font-semibold tracking-tight text-slate-900 md:text-6xl">
                Intelligent music tutoring, kept focused.
              </h1>
              <p className="mt-4 max-w-2xl text-lg leading-relaxed text-slate-600">
                Eurydice combines live conversation, music analysis, and notation workflow in one
                controlled studio. Enter the workspace only when you are ready to start the tutor.
              </p>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            {ENTRY_POINTS.map((item) => (
              <div
                key={item.label}
                className="rounded-[1.8rem] border border-slate-300/80 bg-white/72 px-4 py-4 shadow-[0_16px_34px_rgba(47,52,58,0.05)]"
              >
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  {item.label}
                </div>
                <div className="mt-2 text-sm leading-relaxed text-slate-600">{item.description}</div>
              </div>
            ))}
          </div>
        </section>

        <aside className="glass rounded-[2.2rem] px-6 py-6">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Enter workspace
          </div>
          <h2 className="mt-3 text-2xl font-semibold text-slate-900">Sign in when you want to start the tutor.</h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">
            The landing page stays static. Microphone capture and Gemini Live only start after you
            enter the workspace and explicitly start a session.
          </p>

          <div className="mt-6 space-y-3">
            <input
              value={email}
              onChange={(event) => onEmailChange(event.target.value)}
              placeholder="Email (optional)"
              className="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-slate-500"
            />
            <input
              value={password}
              onChange={(event) => onPasswordChange(event.target.value)}
              type="password"
              placeholder="Password (optional)"
              className="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-slate-500"
            />
          </div>

          <button
            type="button"
            onClick={onSignIn}
            disabled={signingIn}
            className="mt-5 flex min-h-13 w-full items-center justify-center rounded-2xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-wait disabled:opacity-70"
          >
            {signingIn ? "Signing in..." : "Enter workspace"}
          </button>

          <div className="mt-4 text-sm text-slate-600">{authStatus}</div>
          {errorMessage ? <div className="mt-2 text-sm text-red-600">{errorMessage}</div> : null}
          <div className="mt-4 text-xs text-slate-500">
            Leave both fields blank for anonymous challenge sign-in.
          </div>
        </aside>
      </main>
    </div>
  );
}
