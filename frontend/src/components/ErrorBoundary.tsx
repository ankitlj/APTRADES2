import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/** Top-level boundary so a render crash on one page shows a recoverable
 * fallback instead of a blank white screen. */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("UI error boundary caught an error:", error, info);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="app-error-boundary">
          <div className="state-card state-error" role="alert">
            <p className="state-title">This page hit an unexpected error</p>
            <p className="state-message">{this.state.error.message}</p>
            <button type="button" className="toolbar-button" onClick={() => window.location.reload()}>
              Reload app
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
