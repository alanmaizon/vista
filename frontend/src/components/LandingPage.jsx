const ENTRY_POINTS = [
  "Guided lesson preparation",
  "Focused capture and comparison",
  "Notation, playback, and review",
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
      className={`text-slate-100 transition-all duration-500 ${
        isTransitioning ? "pointer-events-none scale-[1.01] opacity-0 blur-[2px]" : "opacity-100"
      }`}
    >
      <section className="landing-hero-gradient flex min-h-screen items-center px-5 py-14">
        <div className="mx-auto grid w-full max-w-6xl gap-8 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
          <div className="rounded-[2.4rem] border border-white/10 bg-white/[0.04] px-6 py-7 backdrop-blur-md md:px-8 md:py-9">
            <div className="inline-flex items-center rounded-full border border-white/12 bg-white/5 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-200">
              Eurydice
            </div>
            <img
              src="/logo.svg"
              alt="Eurydice"
              className="mt-6 h-20 w-20 rounded-[1.6rem] border border-white/12 bg-white/8 p-3"
            />
            <h1 className="mt-6 text-4xl font-semibold tracking-tight text-white md:text-6xl">
              An intelligent digital music tutor
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-relaxed text-slate-300 md:text-lg">
              Enter a focused workstation for guided listening, capture, notation, and feedback.
              The landing surface stays quiet so the lesson loop can start cleanly.
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-3">
              {ENTRY_POINTS.map((item) => (
                <div
                  key={item}
                  className="rounded-[1.4rem] border border-white/10 bg-slate-950/35 px-4 py-4 text-sm text-slate-200"
                >
                  {item}
                </div>
              ))}
            </div>
          </div>

          <div className="glass rounded-[2.4rem] p-6 md:p-7">
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-200">
              Entry
            </div>
            <h2 className="mt-3 text-2xl font-semibold text-white">Sign in and enter the workspace</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-300">
              Use email and password if you have them. Leave both blank for anonymous challenge
              sign-in.
            </p>

            <div className="mt-6 grid gap-3">
              <input
                value={email}
                onChange={(event) => onEmailChange(event.target.value)}
                placeholder="Email (optional)"
                className="rounded-[1.4rem] border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none transition focus:border-sky-300/60"
              />
              <input
                value={password}
                onChange={(event) => onPasswordChange(event.target.value)}
                type="password"
                placeholder="Password (optional)"
                className="rounded-[1.4rem] border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none transition focus:border-sky-300/60"
              />
              <button
                type="button"
                onClick={onSignIn}
                disabled={signingIn}
                className="landing-cta mt-2 rounded-[1.4rem] bg-sky-400 px-6 py-3 text-base font-semibold text-slate-950 transition hover:bg-sky-300 disabled:cursor-wait disabled:opacity-75"
              >
                {signingIn ? "Signing In..." : "Enter workspace"}
              </button>
            </div>

            <div className="mt-5 rounded-[1.4rem] border border-white/10 bg-slate-950/35 px-4 py-4 text-sm text-slate-300">
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                Status
              </div>
              <div className="mt-2 text-white">{authStatus}</div>
              {errorMessage ? <div className="mt-2 text-rose-300">{errorMessage}</div> : null}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
