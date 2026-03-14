import LiveAgentWorkspace from "./components/LiveAgentWorkspace";
import useLiveAgentApp from "./hooks/useLiveAgentApp";

export default function App() {
  const app = useLiveAgentApp();
  return <LiveAgentWorkspace {...app} />;
}
