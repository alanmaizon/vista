import { useState } from "react";
import { Settings } from "lucide-react";
import SettingsPanel from "./SettingsPanel";

export default function Navbar() {
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <>
      <nav className="sticky top-0 z-40 flex items-center justify-between px-4 py-3 glass">
        <div className="flex items-center gap-2">
          <img src="/logo.svg" alt="Eurydice logo" className="h-8 w-8" />
          <span className="text-lg font-semibold text-white">Eurydice</span>
        </div>

        <button
          type="button"
          onClick={() => setSettingsOpen(true)}
          aria-label="Open settings"
          className="rounded-lg p-2 text-white/70 hover:bg-white/10 hover:text-white transition-colors"
        >
          <Settings className="h-5 w-5" />
        </button>
      </nav>

      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  );
}
