// src/app/ErrorBoundary.tsx

import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { AppError } from '@/utils/errors';
import { captureException } from './monitoring';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback: ReactNode | ((error: Error, reset: () => void) => ReactNode);
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  level: 'global' | 'domain' | 'component';
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    captureException(error, {
      level: this.props.level === 'global' ? 'fatal' : 'error',
      tags: {
        boundary_level: this.props.level,
        ...(error instanceof AppError ? { error_code: error.code } : {}),
      },
      extra: {
        componentStack: errorInfo.componentStack,
        ...(error instanceof AppError ? { error_context: error.context, recoverable: error.recoverable } : {}),
      },
    });
    this.props.onError?.(error, errorInfo);
  }

  reset = (): void => this.setState({ hasError: false, error: null });

  render(): ReactNode {
    if (this.state.hasError) {
      const { fallback } = this.props;
      return typeof fallback === 'function' ? fallback(this.state.error!, this.reset) : fallback;
    }
    return this.props.children;
  }
}
