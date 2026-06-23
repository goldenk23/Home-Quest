// src/domains/vastu/components/VastuPanel.tsx

import React, { useState } from 'react';
import { useAppStore } from '@/store';
import { VASTU_RULES_LIST, DIR_NAME, type VastuRecommendation } from '../services/scoring';
import type { VastuDirection } from '../services/zones';

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
        <p style={{ color: '#64748b', fontSize: '0.9rem', margin: '0 0 1rem' }}>
          Draw a closed loop of walls (and assign rooms) to see a Vastu score here.
        </p>
        <VastuRulesReference />
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

      <VastuRulesReference />
    </div>
  );
};

/** Short direction codes (e.g. "NE") for compact rule rows. */
function dirCodes(dirs: VastuDirection[]): string {
  return dirs.length ? dirs.join(', ') : '—';
}

/**
 * Always-visible reference of the authentic Vastu placement rules, so users can see the
 * ideal direction for every room type without first drawing a plan. Collapsible to keep
 * the panel compact.
 */
const VastuRulesReference: React.FC = () => {
  const [open, setOpen] = useState(false);

  return (
    <div style={{ marginTop: '1rem', borderTop: '1px solid #e2e8f0', paddingTop: '0.75rem' }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          width: '100%',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: 0,
          font: 'inherit',
        }}
        aria-expanded={open}
      >
        <span style={subHeadingStyle}>📖 Vastu Rules Reference</span>
        <span style={{ color: '#94a3b8', fontSize: '0.8rem' }}>{open ? '▲ Hide' : '▼ Show'}</span>
      </button>

      {open && (
        <>
          <p style={{ fontSize: '0.75rem', color: '#94a3b8', margin: '6px 0 8px' }}>
            Traditional placements (Vastu Purusha Mandala). The centre (Brahmasthan) should stay open.
          </p>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
            <thead>
              <tr style={{ textAlign: 'left', color: '#94a3b8' }}>
                <th style={thStyle}>Room</th>
                <th style={thStyle}>Ideal</th>
                <th style={thStyle}>OK</th>
                <th style={thStyle}>Avoid</th>
              </tr>
            </thead>
            <tbody>
              {VASTU_RULES_LIST.map(({ roomType, roomName, rule }) => (
                <tr key={roomType} style={{ borderTop: '1px solid #f1f5f9' }} title={rule.note}>
                  <td style={{ ...tdStyle, color: '#334155', fontWeight: 600 }}>{roomName}</td>
                  <td style={{ ...tdStyle, color: '#16a34a', fontWeight: 600 }}>{dirCodes(rule.ideal)}</td>
                  <td style={{ ...tdStyle, color: '#d97706' }}>{dirCodes(rule.acceptable)}</td>
                  <td style={{ ...tdStyle, color: '#dc2626' }}>{dirCodes(rule.adverse)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '8px', lineHeight: 1.5 }}>
            {Object.entries(DIR_NAME).map(([code, name]) => (
              <span key={code} style={{ marginRight: '8px', whiteSpace: 'nowrap' }}>
                <strong>{code}</strong>= {name.replace(/\s*\(.*\)/, '')}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

const thStyle: React.CSSProperties = { padding: '4px 6px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.03em', fontSize: '0.68rem' };
const tdStyle: React.CSSProperties = { padding: '4px 6px', verticalAlign: 'top' };

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
