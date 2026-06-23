// src/app/hooks/useAccessibilityPreferences.ts

import { useEffect, useState } from 'react';

export interface A11yPreferences {
  prefersReducedMotion: boolean;
  prefersHighContrast: boolean;
  prefersColorScheme: 'light' | 'dark';
}

/** Reflects OS/browser a11y settings so components can dial down motion, bump contrast, etc. */
export function useAccessibilityPreferences(): A11yPreferences {
  const [prefs, setPrefs] = useState<A11yPreferences>({
    prefersReducedMotion: false,
    prefersHighContrast: false,
    prefersColorScheme: 'dark',
  });

  useEffect(() => {
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const contrast = window.matchMedia('(prefers-contrast: more)');
    const scheme = window.matchMedia('(prefers-color-scheme: light)');
    const update = () =>
      setPrefs({
        prefersReducedMotion: motion.matches,
        prefersHighContrast: contrast.matches,
        prefersColorScheme: scheme.matches ? 'light' : 'dark',
      });
    update();
    motion.addEventListener('change', update);
    contrast.addEventListener('change', update);
    scheme.addEventListener('change', update);
    return () => {
      motion.removeEventListener('change', update);
      contrast.removeEventListener('change', update);
      scheme.removeEventListener('change', update);
    };
  }, []);

  return prefs;
}
