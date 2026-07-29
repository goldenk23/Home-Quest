import React, { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { ViewerCanvas } from '@/domains/viewer/components/ViewerCanvas';
import { useVastuAnalysis } from '@/domains/vastu/hooks/useVastuAnalysis';
import { useAppStore } from '@/store';
import {
  importVastuLayout,
  MAX_VASTU_FILE_BYTES,
  type ImportReport,
} from '@/store/persistence/importVastu';

interface WebViewBridge {
  addEventListener(type: 'message', listener: (event: MessageEvent<unknown>) => void): void;
  removeEventListener(type: 'message', listener: (event: MessageEvent<unknown>) => void): void;
  postMessage(message: unknown): void;
}

type HostWindow = Window & { chrome?: { webview?: WebViewBridge } };
type PreviewStatus =
  | { kind: 'idle'; message: string }
  | { kind: 'loading'; message: string }
  | { kind: 'ready'; message: string }
  | { kind: 'error'; message: string };

const getBridge = () => (window as HostWindow).chrome?.webview;

class ViewerErrorBoundary extends React.Component<
  { children: ReactNode },
  { error: string | null }
> {
  state = { error: null as string | null };

  static getDerivedStateFromError(error: Error) {
    return { error: error.message || 'WebGL rendering failed' };
  }

  render() {
    if (this.state.error) {
      return <EmptyMessage title="3D rendering failed" detail={this.state.error} />;
    }
    return this.props.children;
  }
}

const shell: CSSProperties = {
  height: '100vh',
  minHeight: 0,
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
  color: '#e5e7eb',
  background: '#0f172a',
};

const toolbar: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  flexWrap: 'wrap',
  gap: 8,
  padding: '8px 10px',
  borderBottom: '1px solid #334155',
  background: '#111827',
};

const button = (active = false): CSSProperties => ({
  border: `1px solid ${active ? '#f59e0b' : '#475569'}`,
  borderRadius: 5,
  padding: '6px 10px',
  color: '#f8fafc',
  background: active ? '#92400e' : '#1e293b',
  cursor: 'pointer',
});

function EmptyMessage({ title, detail }: { title: string; detail: string }) {
  return (
    <div style={{ display: 'grid', placeItems: 'center', height: '100%', padding: 32, textAlign: 'center' }}>
      <div>
        <div style={{ fontSize: 20, fontWeight: 700 }}>{title}</div>
        <div style={{ marginTop: 8, color: '#cbd5e1', maxWidth: 680 }}>{detail}</div>
      </div>
    </div>
  );
}

function reportText(report: ImportReport): string {
  const warnings = [
    ...report.unmapped.map((name) => `unmapped furniture '${name}' omitted from 3D`),
    ...report.residuals,
  ];
  return `${report.rooms} rooms · ${report.walls} walls · ${report.openings} openings · ` +
    `${report.furniture} furniture${warnings.length ? ` · ${warnings.join('; ')}` : ''}`;
}

export function EmbeddedViewer() {
  useVastuAnalysis();
  const cameraMode = useAppStore((state) => state.cameraMode);
  const renderQuality = useAppStore((state) => state.renderQuality);
  const setCameraMode = useAppStore((state) => state.setCameraMode);
  const setRenderQuality = useAppStore((state) => state.setRenderQuality);
  const triggerCameraReset = useAppStore((state) => state.triggerCameraReset);
  const hasWalls = useAppStore((state) => Object.keys(state.walls).length > 0);
  const [status, setStatus] = useState<PreviewStatus>({
    kind: 'idle',
    message: 'Waiting for the current VastuCraft plan…',
  });
  const [report, setReport] = useState<ImportReport | null>(null);
  const [walking, setWalking] = useState(false);
  const [controlError, setControlError] = useState<string | null>(null);
  const latestRequest = useRef(0);
  const active = useRef(true);

  useEffect(() => {
    const bridge = getBridge();
    if (!bridge) {
      setStatus({
        kind: 'error',
        message: 'This viewer must be opened from the VastuCraft Pro 3D Viewer tab.',
      });
      return;
    }

    const postStatus = (message: unknown) => bridge.postMessage(message);
    let acknowledged = false;
    const announceReady = () => {
      if (!acknowledged) bridge.postMessage({ type: 'ready' });
    };
    const readyTimer = window.setInterval(announceReady, 500);
    const onMessage = (event: MessageEvent<unknown>) => {
      if (!event.data || typeof event.data !== 'object') return;
      const message = event.data as Record<string, unknown>;

      if (message.type === 'deactivate') {
        active.current = false;
        if (document.pointerLockElement) void document.exitPointerLock();
        useAppStore.getState().setCameraMode('orbit');
        return;
      }
      if (message.type === 'host-error' && typeof message.error === 'string') {
        setStatus({ kind: 'error', message: message.error });
        return;
      }
      if (
        message.type !== 'load-layout' ||
        !Number.isSafeInteger(message.requestId) ||
        typeof message.payloadJson !== 'string'
      ) return;

      const requestId = message.requestId as number;
      if (requestId <= latestRequest.current) return;
      acknowledged = true;
      window.clearInterval(readyTimer);
      latestRequest.current = requestId;
      active.current = true;
      setStatus({ kind: 'loading', message: 'Validating and converting the latest plan…' });
      postStatus({ type: 'status', requestId, state: 'loading' });

      requestAnimationFrame(() => {
        if (!active.current || requestId !== latestRequest.current) return;
        try {
          if (new TextEncoder().encode(message.payloadJson as string).byteLength > MAX_VASTU_FILE_BYTES) {
            throw new Error(`Layout message is larger than ${MAX_VASTU_FILE_BYTES / 1024 / 1024} MB`);
          }
          const layout: unknown = JSON.parse(message.payloadJson as string);
          if (!active.current || requestId !== latestRequest.current) return;
          const nextReport = importVastuLayout(layout);
          setReport(nextReport);
          setStatus({ kind: 'ready', message: '3D preview is up to date.' });
          useAppStore.getState().triggerCameraReset();
          postStatus({ type: 'status', requestId, state: 'ready', report: nextReport });
        } catch (error) {
          const reason = error instanceof Error ? error.message : String(error);
          setStatus({ kind: 'error', message: reason });
          postStatus({ type: 'status', requestId, state: 'error', error: reason });
        }
      });
    };

    bridge.addEventListener('message', onMessage);
    announceReady();
    return () => {
      active.current = false;
      window.clearInterval(readyTimer);
      bridge.removeEventListener('message', onMessage);
      if (document.pointerLockElement) void document.exitPointerLock();
      useAppStore.getState().setCameraMode('orbit');
    };
  }, []);

  useEffect(() => {
    const onLockChange = () => setWalking(Boolean(document.pointerLockElement));
    const onLockError = () => {
      setControlError('Walkthrough could not capture the pointer. Click the 3D canvas again, or use Orbit mode.');
    };
    document.addEventListener('pointerlockchange', onLockChange);
    document.addEventListener('pointerlockerror', onLockError);
    return () => {
      document.removeEventListener('pointerlockchange', onLockChange);
      document.removeEventListener('pointerlockerror', onLockError);
    };
  }, []);

  const chooseWalkthrough = () => {
    if (typeof document.documentElement.requestPointerLock !== 'function') {
      setControlError('Pointer lock is unavailable in this browser runtime. Use Orbit mode or install WebView2 Runtime.');
      return;
    }
    setControlError(null);
    setCameraMode('firstPerson');
  };

  const requestRefresh = () => {
    const bridge = getBridge();
    if (bridge) {
      setStatus({ kind: 'loading', message: 'Requesting the latest plan from VastuCraft Pro…' });
      bridge.postMessage({ type: 'refresh-request' });
    } else {
      setStatus({ kind: 'error', message: 'The VastuCraft Pro host bridge is unavailable.' });
    }
  };

  return (
    <main style={shell}>
      <div style={toolbar}>
        <strong style={{ marginRight: 4 }}>3D Preview</strong>
        <button style={button(cameraMode === 'orbit')} aria-pressed={cameraMode === 'orbit'} onClick={() => setCameraMode('orbit')}>
          Orbit
        </button>
        <button style={button(cameraMode === 'firstPerson')} aria-pressed={cameraMode === 'firstPerson'} onClick={chooseWalkthrough}>
          Walkthrough
        </button>
        <button style={button()} onClick={triggerCameraReset}>Reset camera</button>
        <span style={{ width: 1, alignSelf: 'stretch', background: '#475569', margin: '0 2px' }} />
        {(['low', 'medium', 'high'] as const).map((quality) => (
          <button
            key={quality}
            style={button(renderQuality === quality)}
            aria-pressed={renderQuality === quality}
            onClick={() => setRenderQuality(quality)}
          >
            {quality[0].toUpperCase() + quality.slice(1)}
          </button>
        ))}
        <button style={{ ...button(), marginLeft: 'auto' }} onClick={requestRefresh}>Refresh 3D</button>
      </div>

      <div
        role={status.kind === 'error' ? 'alert' : 'status'}
        style={{
          padding: '6px 10px',
          fontSize: 13,
          color: status.kind === 'error' ? '#fecaca' : '#cbd5e1',
          background: status.kind === 'error' ? '#7f1d1d' : '#1e293b',
          borderBottom: '1px solid #334155',
        }}
      >
        {status.message}
        {report && <span style={{ marginLeft: 8, opacity: 0.9 }}>{reportText(report)}</span>}
      </div>

      {controlError && (
        <div role="alert" style={{ padding: '6px 10px', fontSize: 13, color: '#fde68a', background: '#78350f' }}>
          {controlError}
        </div>
      )}

      <div style={{ position: 'relative', flex: 1, minHeight: 0 }}>
        <ViewerErrorBoundary>
          <ViewerCanvas />
        </ViewerErrorBoundary>
        {hasWalls && cameraMode === 'firstPerson' && !walking && (
          <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', pointerEvents: 'none' }}>
            <div style={{ maxWidth: 520, padding: 16, borderRadius: 8, textAlign: 'center', background: 'rgba(15,23,42,.88)' }}>
              <strong>Click the 3D canvas to start walking</strong>
              <div style={{ marginTop: 6, fontSize: 13, color: '#cbd5e1' }}>
                Mouse to look · hold left/right mouse to move · WASD or arrows · Shift to sprint · Escape to release
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
