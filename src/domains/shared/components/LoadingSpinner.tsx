// src/domains/shared/components/LoadingSpinner.tsx

import React from 'react';

interface LoadingSpinnerProps {
  label?: string;
  size?: 'sm' | 'md' | 'lg';
}

/** Accessible spinner; the label is both shown and exposed to screen readers. */
export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ label = 'Loading…', size = 'md' }) => {
  const sizes = { sm: 'w-4 h-4', md: 'w-8 h-8', lg: 'w-12 h-12' };
  return (
    <div className="flex flex-col items-center justify-center h-full w-full gap-3" role="status" aria-label={label} aria-live="polite">
      <svg className={`${sizes[size]} animate-spin text-blue-500`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      <p className="text-neutral-400 text-sm">{label}</p>
    </div>
  );
};
