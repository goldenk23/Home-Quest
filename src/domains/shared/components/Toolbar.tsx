// src/domains/shared/components/Toolbar.tsx

import React from 'react';
import { useAppStore } from '@/store';
import { announce } from './ScreenReaderAnnouncer';

type Tool = 'select' | 'wall' | 'furniture' | 'pan' | 'measure';

interface ToolConfig {
  id: Tool;
  label: string;
  shortcut: string;
  icon: string;
  description: string;
}

const TOOLS: ToolConfig[] = [
  { id: 'select', label: 'Select', shortcut: 'S', icon: '⊡', description: 'Select and move entities' },
  { id: 'wall', label: 'Draw Wall', shortcut: 'W', icon: '━', description: 'Click to place wall endpoints' },
  { id: 'furniture', label: 'Place Furniture', shortcut: 'F', icon: '▣', description: 'Choose and place furniture items' },
  { id: 'pan', label: 'Pan View', shortcut: 'H', icon: '✋', description: 'Click and drag to pan the canvas' },
  { id: 'measure', label: 'Measure', shortcut: 'M', icon: '↔', description: 'Measure distances between points' },
];

export const Toolbar: React.FC = () => {
  const activeTool = useAppStore((s) => s.activeTool);
  const setActiveTool = useAppStore((s) => s.setActiveTool);

  const handleToolChange = (tool: Tool) => {
    setActiveTool(tool);
    announce(`${TOOLS.find((t) => t.id === tool)?.label} tool activated`);
  };

  return (
    <nav aria-label="Drawing Tools" role="toolbar" className="flex gap-1 px-2">
      {TOOLS.map((tool) => (
        <button
          key={tool.id}
          onClick={() => handleToolChange(tool.id)}
          aria-label={`${tool.label} (${tool.shortcut})`}
          aria-pressed={activeTool === tool.id}
          aria-describedby={`tool-desc-${tool.id}`}
          title={`${tool.label} (${tool.shortcut})`}
          className={`w-10 h-10 flex items-center justify-center rounded-md text-lg transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 ${
            activeTool === tool.id ? 'bg-blue-600 text-white' : 'bg-neutral-700 text-neutral-300 hover:bg-neutral-600'
          }`}
        >
          {tool.icon}
          <span id={`tool-desc-${tool.id}`} className="sr-only">{tool.description}</span>
        </button>
      ))}
    </nav>
  );
};
