/**
 * MusicSkillCard – glassmorphic card representing a music skill / mode.
 *
 * @param {object}  props
 * @param {string}  props.title       – skill name
 * @param {string}  props.description – short description
 * @param {string}  props.icon        – emoji or text icon
 * @param {boolean} props.active      – whether this skill is currently selected
 * @param {function} props.onSelect   – callback when the card is clicked
 */
export default function MusicSkillCard({ title, description, icon, active, onSelect }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`glass rounded-2xl p-6 text-left transition-all hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-white/30 ${
        active ? "ring-2 ring-indigo-400/60" : ""
      }`}
    >
      <div className="mb-3 text-3xl">{icon}</div>
      <h3 className="text-lg font-semibold text-white">{title}</h3>
      <p className="mt-1 text-sm text-white/60">{description}</p>
    </button>
  );
}
