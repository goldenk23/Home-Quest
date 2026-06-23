// src/domains/shared/components/EmptyState.tsx

import React from 'react';

interface EmptyStateProps {
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
  icon?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ title, description, action, icon }) => (
  <div className="flex flex-col items-center justify-center h-full p-8 text-center">
    {icon && <div className="text-4xl mb-4 text-neutral-500" aria-hidden="true">{icon}</div>}
    <h3 className="text-lg font-medium text-neutral-300 mb-2">{title}</h3>
    <p className="text-neutral-500 text-sm max-w-xs mb-4">{description}</p>
    {action && (
      <button onClick={action.onClick} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm transition-colors">
        {action.label}
      </button>
    )}
  </div>
);
