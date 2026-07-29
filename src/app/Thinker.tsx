import React, { useEffect, useRef, useState } from 'react';
import { generateFloorPlan, type FloorPlanMessage } from '../services/floorPlanApi';

export interface LayoutApplyResult {
  applied: boolean;
  message: string;
}

interface ThinkerProps {
  onApply: (layout: unknown) => Promise<LayoutApplyResult>;
}

const button = (primary = false): React.CSSProperties => ({
  border: 0, borderRadius: 7, padding: '0.55rem 0.85rem', cursor: 'pointer',
  background: primary ? '#4f46e5' : '#e2e8f0', color: primary ? '#fff' : '#1e293b', fontWeight: 700,
});

export const Thinker: React.FC<ThinkerProps> = ({ onApply }) => {
  const [messages, setMessages] = useState<FloorPlanMessage[]>([]);
  const [prompt, setPrompt] = useState('');
  const [latestLayout, setLatestLayout] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('Describe the house, plot size, rooms, orientation, and priorities.');
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const apply = async (layout: unknown) => {
    const result = await onApply(layout);
    setStatus(result.message);
    return result.applied;
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const text = prompt.trim();
    if (!text || busy) return;
    const nextMessages: FloorPlanMessage[] = [...messages, { role: 'user' as const, content: text }].slice(-24);
    setMessages(nextMessages);
    setPrompt('');
    setBusy(true);
    setStatus(latestLayout ? 'Thinking through your revision…' : 'Designing and validating the floor plan…');
    controller.current = new AbortController();
    try {
      const result = await generateFloorPlan({ messages: nextMessages, previousLayout: latestLayout, signal: controller.current.signal });
      setLatestLayout(result.layout);
      setMessages([...nextMessages, { role: 'assistant', content: result.assistantMessage }]);
      const applied = await apply(result.layout);
      if (!applied) setStatus('The design is ready but was not applied. Use “Apply latest” when ready.');
    } catch (error) {
      if ((error as Error).name !== 'AbortError') setStatus(`Generation failed: ${(error as Error).message}`);
      else setStatus('Generation cancelled.');
    } finally {
      setBusy(false);
      controller.current = null;
    }
  };

  const reapply = async () => {
    if (!latestLayout) return;
    try { await apply(latestLayout); }
    catch (error) { setStatus(`Could not apply layout: ${(error as Error).message}`); }
  };

  const download = () => {
    if (!latestLayout) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(latestLayout, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `home-quest-ai-${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const reset = () => {
    controller.current?.abort();
    setMessages([]);
    setLatestLayout(undefined);
    setPrompt('');
    setStatus('Started a new design conversation.');
  };

  return (
    <section id="ai-layout-generator" style={{ padding: '1rem', background: '#fff', borderRadius: 10, boxShadow: '0 1px 3px rgba(0,0,0,.08)', border: '1px solid #c7d2fe' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center', marginBottom: '0.75rem' }}>
        <div>
          <h2 style={{ margin: 0, color: '#312e81', fontSize: '1rem' }}>✨ Thinker — AI floor-plan architect</h2>
          <p style={{ margin: '0.25rem 0 0', color: '#64748b', fontSize: '0.8rem' }}>
            Generates native VastuCraft JSON, validates it, and renders it in the existing 2D/3D views.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          <button type="button" style={{ ...button(), opacity: latestLayout ? 1 : 0.5 }} disabled={!latestLayout || busy} onClick={() => void reapply()}>Apply latest</button>
          <button type="button" style={{ ...button(), opacity: latestLayout ? 1 : 0.5 }} disabled={!latestLayout} onClick={download}>Download JSON</button>
          <button type="button" style={button()} onClick={reset}>New design</button>
        </div>
      </div>

      {messages.length > 0 && (
        <div aria-live="polite" style={{ maxHeight: 190, overflowY: 'auto', padding: '0.5rem', background: '#f8fafc', borderRadius: 8, marginBottom: '0.65rem' }}>
          {messages.map((message, index) => (
            <div key={`${message.role}-${index}`} style={{ margin: '0.35rem 0', fontSize: '0.82rem', color: '#334155' }}>
              <strong style={{ color: message.role === 'user' ? '#0369a1' : '#6d28d9' }}>{message.role === 'user' ? 'You' : 'Thinker'}:</strong>{' '}
              {message.content}
            </div>
          ))}
        </div>
      )}

      <form onSubmit={submit}>
        <textarea
          id="ai-layout-prompt"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          maxLength={4000}
          disabled={busy}
          rows={3}
          placeholder={latestLayout ? 'Ask for a revision, e.g. “Move the kitchen southeast and enlarge the living room.”' : 'Example: Design a north-facing 40×60 ft, 3-bedroom Vastu home with parking, puja room, open kitchen, and good ventilation.'}
          style={{ width: '100%', boxSizing: 'border-box', resize: 'vertical', padding: '0.7rem', borderRadius: 8, border: '1px solid #cbd5e1', font: 'inherit' }}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginTop: '0.55rem', flexWrap: 'wrap' }}>
          <button type="submit" style={{ ...button(true), opacity: !prompt.trim() || busy ? 0.55 : 1 }} disabled={!prompt.trim() || busy}>
            {busy ? 'Working…' : latestLayout ? 'Refine layout' : 'Generate layout'}
          </button>
          {busy && <button type="button" style={button()} onClick={() => controller.current?.abort()}>Cancel</button>}
          <span role="status" style={{ color: status.startsWith('Generation failed') ? '#b91c1c' : '#64748b', fontSize: '0.78rem' }}>{status}</span>
        </div>
      </form>
    </section>
  );
};
