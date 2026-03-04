import { useCallback } from "react";
import Navbar from "./components/Navbar";
import MusicSkillCard from "./components/MusicSkillCard";
import MediaCapture from "./components/MediaCapture";
import { useSession } from "./context/useSession";
import useLiveConnection from "./hooks/useLiveConnection";

const SKILLS = [
  { id: "HEAR_PHRASE", title: "Hear Phrase", description: "Listen and identify melodic phrases.", icon: "🎧" },
  { id: "PLAY_ALONG", title: "Play Along", description: "Follow along with a guided score.", icon: "🎵" },
  { id: "FREE_JAM", title: "Free Jam", description: "Improvise freely with AI feedback.", icon: "🎸" },
];

function App() {
  const { skill, setSkill, micEnabled, cameraEnabled, addCaption, setStatus, status } = useSession();

  const handleMessage = useCallback(
    (data) => {
      if (data.type === "server.text") {
        addCaption("assistant", data.text ?? "");
      } else if (data.type === "server.status") {
        setStatus(data.state === "connected" ? "connected" : "idle");
      }
    },
    [addCaption, setStatus],
  );

  const { send, isConnected } = useLiveConnection({ onMessage: handleMessage });

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-indigo-950 to-gray-900 text-white">
      <Navbar />

      <main className="mx-auto max-w-5xl px-4 py-8 space-y-8">
        {/* Status bar */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Music Skills</h1>
          <div className="flex items-center gap-4">
            <MediaCapture
              micEnabled={micEnabled}
              cameraEnabled={cameraEnabled}
              send={send}
              isConnected={isConnected}
            />
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${
                status === "connected" ? "bg-green-400" : "bg-white/30"
              }`}
              title={status}
            />
          </div>
        </div>

        {/* Skill cards */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SKILLS.map((s) => (
            <MusicSkillCard
              key={s.id}
              title={s.title}
              description={s.description}
              icon={s.icon}
              active={skill === s.id}
              onSelect={() => setSkill(s.id)}
            />
          ))}
        </div>
      </main>
    </div>
  );
}

export default App;
