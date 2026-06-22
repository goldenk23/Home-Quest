// src/domains/vastu/components/VastuPanel.tsx

import React from 'react';
import { useAppStore } from '@/store';
import type { VastuRecommendation } from '../services/scoring';

/** Severity → icon + label, so meaning never relies on color alone (accessibility). */
const SEVERITY_META: Record<VastuRecommendation['severity'], { icon: string; label: string; color: string }> = {
  critical: { icon: '⛔', label: 'Critical', color: '#dc2626' },
  warning: { icon: '⚠️', label: 'Warning', color: '#d97706' },
  suggestion: { icon: '💡', label: 'Suggestion', color: '#2563eb' },
};

function scoreColor(score: number): string {
  if (score >= 80) return '#16a34a';
  if (score >= 50) return '#d97706';
  return '#dc2626';
}

function scoreBand(score: number): string {
  if (score >= 80) return 'Excellent';
  if (score >= 50) return 'Fair';
  return 'Needs work';
}

/**
 * Displays the cached Vastu score (computed by `useVastuAnalysis`). Shows the overall
 * score, a per-room breakdown, and recommendations. Score is communicated with text +
 * icon, never color alone.
 */
export const VastuPanel: React.FC = () => {
  const vastuScore = useAppStore((s) => s.vastuScore);

  if (!vastuScore) {
    return (
      <div style={panelStyle}>
        <h3 style={titleStyle}>🧭 Vastu Analysis</h3>
        <p style={{ color: '#64748b', fontSize: '0.9rem', margin: 0 }}>
          Draw a closed loop of walls (and assign rooms) to see a Vastu score here.
        </p>
      </div>
    );
  }

  const overall = Math.round(vastuScore.overall);
  const roomScores = Object.values(vastuScore.roomScores);

  return (
    <div style={panelStyle}>
      <h3 style={titleStyle}>🧭 Vastu Analysis</h3>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginBottom: '1rem' }}>
        <span style={{ fontSize: '2rem', fontWeight: 700, color: scoreColor(overall) }}>{overall}</span>
        <span style={{ color: '#64748b', fontSize: '0.9rem' }}>/ 100 — {scoreBand(overall)}</span>
      </div>

      {roomScores.length === 0 ? (
        <p style={{ color: '#64748b', fontSize: '0.85rem' }}>
          No rooms detected yet. Close a wall loop to create a room.
        </p>
      ) : (
        <div style={{ marginBottom: '1rem' }}>
          <div style={subHeadingStyle}>Rooms ({roomScores.length})</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {roomScores.map((rs) => (
              <div
                key={rs.roomId}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: '0.85rem',
                  padding: '4px 8px',
                  background: '#f8fafc',
                  borderRadius: '4px',
                  borderLeft: `3px solid ${scoreColor(rs.score)}`,
                }}
              >
                <span style={{ color: '#334155' }}>
                  {rs.isIdeal ? '✓ ' : ''}
                  <strong style={{ textTransform: 'capitalize' }}>{rs.roomType}</strong>
                  <span style={{ color: '#94a3b8' }}> · {rs.direction}</span>
                </span>
                <span style={{ fontWeight: 600, color: scoreColor(rs.score) }}>{rs.score}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {vastuScore.recommendations.length > 0 && (
        <div>
          <div style={subHeadingStyle}>Recommendations</div>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {vastuScore.recommendations.map((rec, i) => {
              const meta = SEVERITY_META[rec.severity];
              return (
                <li key={`${rec.roomId}-${i}`} style={{ fontSize: '0.82rem', color: '#475569', display: 'flex', gap: '6px' }}>
                  <span title={meta.label} aria-label={meta.label}>{meta.icon}</span>
                  <span>
                    <strong style={{ color: meta.color }}>{meta.label}:</strong> {rec.message}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
};

const panelStyle: React.CSSProperties = {
  padding: '1rem',
  background: '#fff',
  borderRadius: '8px',
  border: '1px solid #e2e8f0',
};

const titleStyle: React.CSSProperties = {
  margin: '0 0 0.75rem 0',
  fontSize: '1rem',
};

const subHeadingStyle: React.CSSProperties = {
  fontSize: '0.72rem',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  color: '#94a3b8',
  marginBottom: '6px',
};
