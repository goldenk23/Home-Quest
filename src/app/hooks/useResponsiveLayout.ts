// src/app/hooks/useResponsiveLayout.ts

import { useState, useEffect } from 'react';

export type LayoutMode = 'desktop' | 'tablet-landscape' | 'tablet-portrait' | 'mobile';

interface LayoutConfig {
  mode: LayoutMode;
  showSidebar: boolean;
  showViewer: boolean;
  editorFullWidth: boolean;
  panelPosition: 'right' | 'bottom' | 'overlay';
}

const BREAKPOINTS = { mobile: 640, tabletPortrait: 768, tabletLandscape: 1024, desktop: 1280 };

function getLayoutConfig(): LayoutConfig {
  const width = window.innerWidth;
  if (width >= BREAKPOINTS.desktop) return { mode: 'desktop', showSidebar: true, showViewer: true, editorFullWidth: false, panelPosition: 'right' };
  if (width >= BREAKPOINTS.tabletLandscape) return { mode: 'tablet-landscape', showSidebar: false, showViewer: true, editorFullWidth: false, panelPosition: 'overlay' };
  if (width >= BREAKPOINTS.tabletPortrait) return { mode: 'tablet-portrait', showSidebar: false, showViewer: false, editorFullWidth: true, panelPosition: 'bottom' };
  return { mode: 'mobile', showSidebar: false, showViewer: false, editorFullWidth: true, panelPosition: 'bottom' };
}

/** Recomputes the layout config on resize. */
export function useResponsiveLayout(): LayoutConfig {
  const [config, setConfig] = useState<LayoutConfig>(getLayoutConfig());
  useEffect(() => {
    const onResize = () => setConfig(getLayoutConfig());
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return config;
}
