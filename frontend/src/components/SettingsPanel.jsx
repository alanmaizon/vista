import { Dialog, DialogPanel, DialogTitle, Transition, TransitionChild } from "@headlessui/react";
import { X } from "lucide-react";
import { Fragment } from "react";
import { useSession } from "../context/useSession";

export default function SettingsPanel({ open, onClose }) {
  const { skill, setSkill, micEnabled, setMicEnabled, cameraEnabled, setCameraEnabled } = useSession();

  return (
    <Transition show={open} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        {/* Backdrop */}
        <TransitionChild
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/40" />
        </TransitionChild>

        {/* Slide-over panel */}
        <div className="fixed inset-0 overflow-hidden">
          <div className="absolute inset-0 overflow-hidden">
            <div className="pointer-events-none fixed inset-y-0 right-0 flex max-w-full pl-10">
              <TransitionChild
                as={Fragment}
                enter="transform transition ease-in-out duration-300"
                enterFrom="translate-x-full"
                enterTo="translate-x-0"
                leave="transform transition ease-in-out duration-200"
                leaveFrom="translate-x-0"
                leaveTo="translate-x-full"
              >
                <DialogPanel className="pointer-events-auto w-screen max-w-sm glass rounded-l-2xl p-6 text-white">
                  <div className="flex items-center justify-between mb-6">
                    <DialogTitle className="text-lg font-semibold">Settings</DialogTitle>
                    <button
                      type="button"
                      onClick={onClose}
                      aria-label="Close settings"
                      className="rounded-lg p-1.5 hover:bg-white/10 transition-colors"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>

                  <div className="space-y-6">
                    {/* Skill / Mode selector */}
                    <div>
                      <label htmlFor="skill-select" className="block text-sm font-medium mb-1 text-white/80">
                        Music Skill
                      </label>
                      <select
                        id="skill-select"
                        value={skill}
                        onChange={(e) => setSkill(e.target.value)}
                        className="w-full rounded-lg bg-white/10 border border-white/20 px-3 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-white/30"
                      >
                        <option value="HEAR_PHRASE">Hear Phrase</option>
                        <option value="PLAY_ALONG">Play Along</option>
                        <option value="FREE_JAM">Free Jam</option>
                      </select>
                    </div>

                    {/* Media toggles */}
                    <fieldset className="space-y-3">
                      <legend className="text-sm font-medium text-white/80">Media</legend>

                      <label className="flex items-center gap-3 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={micEnabled}
                          onChange={(e) => setMicEnabled(e.target.checked)}
                          className="h-4 w-4 rounded border-white/30 bg-white/10 text-indigo-500 focus:ring-indigo-400"
                        />
                        <span className="text-sm">Microphone</span>
                      </label>

                      <label className="flex items-center gap-3 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={cameraEnabled}
                          onChange={(e) => setCameraEnabled(e.target.checked)}
                          className="h-4 w-4 rounded border-white/30 bg-white/10 text-indigo-500 focus:ring-indigo-400"
                        />
                        <span className="text-sm">Camera</span>
                      </label>
                    </fieldset>
                  </div>
                </DialogPanel>
              </TransitionChild>
            </div>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
