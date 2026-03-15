import type { SessionBootstrapResponse } from "../types";

interface MorphologyPanelProps {
  session: SessionBootstrapResponse | null;
}

export function MorphologyPanel({ session }: MorphologyPanelProps) {
  const cards = session
    ? [
        {
          title: "Form analysis",
          body: "A future parse tool result can populate lemma, inflection, and syntactic role here.",
        },
        {
          title: "Translation hint",
          body: "Use this slot for a short clue rather than a full translation when the learner stalls.",
        },
        {
          title: "Follow-up drill",
          body: "A generated micro-drill can reinforce the exact form or construction that caused trouble.",
        },
      ]
    : [
        {
          title: "Morphology cards",
          body: "Start a tutor session to seed placeholder cards and inspect the intended panel layout.",
        },
      ];

  return (
    <section className="panel">
      <div className="section-heading">
        <p className="eyebrow">Morphology</p>
        <h2>Cards and parse hints</h2>
      </div>
      <div className="card-grid">
        {cards.map((card) => (
          <article className="mini-card" key={card.title}>
            <h3>{card.title}</h3>
            <p>{card.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

