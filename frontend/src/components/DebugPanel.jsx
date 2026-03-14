import { Activity, RefreshCw } from "lucide-react";

function formatState(isConnected, isConnecting) {
  if (isConnecting) {
    return "Connecting";
  }
  if (isConnected) {
    return "Live";
  }
  return "Idle";
}

export default function DebugPanel({
  runtimeInfo,
  runtimeDebug,
  connectionMeta,
  isConnected,
  isConnecting,
  refreshRuntime,
}) {
  return (
    <aside className="pointer-events-none fixed bottom-4 right-4 z-40 hidden xl:block">
      <div className="pointer-events-auto glass w-[19rem] border border-slate-300/90 px-4 py-4 shadow-[0_24px_48px_rgba(47,52,58,0.1)]">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Debug</div>
            <div className="mt-1 text-sm font-semibold text-slate-900">
              {formatState(isConnected, isConnecting)}
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              void refreshRuntime();
            }}
            className="flex h-10 w-10 items-center justify-center border border-slate-300 bg-white text-slate-700 shadow-[6px_6px_0_rgba(184,189,197,0.2)]"
            aria-label="Refresh runtime"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-4 grid gap-2 text-sm text-slate-700">
          <div className="border border-slate-300 bg-white px-3 py-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Model</div>
            <div className="mt-1 break-words">{runtimeInfo?.model_id || "..."}</div>
          </div>
          <div className="border border-slate-300 bg-white px-3 py-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
              Transport
            </div>
            <div className="mt-1">{connectionMeta?.transport || "None"}</div>
          </div>
          <div className="border border-slate-300 bg-white px-3 py-3">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
              <Activity className="h-3.5 w-3.5" />
              Sessions
            </div>
            <div className="mt-1">
              Active {runtimeDebug?.active_session_count ?? 0}
              {runtimeDebug?.recent_sessions?.[0]?.transport
                ? ` · Recent ${runtimeDebug.recent_sessions[0].transport}`
                : ""}
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
