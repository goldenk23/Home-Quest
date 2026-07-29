import { useAppStore } from './store';
import { EmbeddedViewer } from './app/EmbeddedViewer';
import { SandboxView } from './app/SandboxView';
import { DevToolsPanel } from './domains/shared/components/DevToolsPanel';
import './App.css';

function RegularApp() {
  const activeView = useAppStore((state) => state.activeView);
  return (
    <>
      {activeView === 'sandbox' ? (
        <SandboxView />
      ) : (
        <div className="app-container" style={{ padding: '2rem' }}>
          <h1>Home Quest</h1>
          <p>The 2D/3D Architectural Vastu Engine</p>
          <p><em>Main application logic will go here.</em></p>
          <p>Check out the <strong>Developer Sandbox</strong> via the DevTools panel in the bottom right!</p>
        </div>
      )}
      <DevToolsPanel />
    </>
  );
}

export default function App() {
  return new URLSearchParams(window.location.search).get('embedded') === '1'
    ? <EmbeddedViewer />
    : <RegularApp />;
}
