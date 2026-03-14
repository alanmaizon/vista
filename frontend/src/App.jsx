import { useEffect, useState } from "react";
import DebugPanel from "./components/DebugPanel";
import LiveAgentWorkspace from "./components/LiveAgentWorkspace";
import SessionSetup from "./components/SessionSetup";
import SessionSummary from "./components/SessionSummary";
import useLiveAgentApp from "./hooks/useLiveAgentApp";

export default function App() {
  const app = useLiveAgentApp();
  const [view, setView] = useState("setup");

  useEffect(() => {
    if (view !== "live") {
      return;
    }
    if (app.isConnected || app.isConnecting) {
      return;
    }
    const timerId = window.setTimeout(() => {
      setView(app.summary ? "summary" : "setup");
    }, 0);
    return () => window.clearTimeout(timerId);
  }, [app.isConnected, app.isConnecting, app.summary, view]);

  return (
    <>
      {view === "setup" ? (
        <SessionSetup
          {...app}
          startSession={() => {
            setView("live");
            void app.startSession();
          }}
        />
      ) : null}
      {view === "live" ? <LiveAgentWorkspace {...app} /> : null}
      {view === "summary" ? (
        <SessionSummary
          summary={app.summary}
          sessionProfile={app.sessionProfile}
          connectionMeta={app.connectionMeta}
          onNewSession={() => {
            app.resetSession();
            setView("setup");
          }}
        />
      ) : null}
      <DebugPanel
        runtimeInfo={app.runtimeInfo}
        runtimeDebug={app.runtimeDebug}
        connectionMeta={app.connectionMeta}
        isConnected={app.isConnected}
        isConnecting={app.isConnecting}
        refreshRuntime={app.refreshRuntime}
      />
    </>
  );
}
