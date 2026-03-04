const ACTIVE_CARD =
  "border-sky-300/70 bg-sky-400/10 shadow-[0_0_0_1px_rgba(125,211,252,0.2)]";
const IDLE_CARD = "border-white/10 bg-white/5 hover:bg-white/10";

export default function SkillSelector({ skills, skill, onChange }) {
  return (
    <div className="glass rounded-3xl p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">
            Mode
          </div>
          <div className="mt-1 text-sm text-slate-400">
            Pick one musical workflow and keep the session focused.
          </div>
        </div>
        <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-300">
          {skill.replaceAll("_", " ")}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        {skills.map((item) => {
          const active = item.id === skill;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onChange(item.id)}
              className={`rounded-2xl border px-4 py-4 text-left transition ${
                active ? ACTIVE_CARD : IDLE_CARD
              }`}
            >
              <div className="text-sm font-semibold text-white">{item.title}</div>
              <div className="mt-1 text-xs text-slate-300">{item.description}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
