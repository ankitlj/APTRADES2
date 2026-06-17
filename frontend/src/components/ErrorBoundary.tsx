import { Component, type ErrorInfo, type ReactNode } from "react";

import { AlertTriangle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

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
        <div className="mx-auto mt-12 flex max-w-lg flex-col items-center gap-4 px-4 text-center">
          <Card className="w-full">
            <CardContent className="flex flex-col items-center gap-3 py-10">
              <AlertTriangle className="h-10 w-10 text-destructive" aria-hidden="true" />
              <div role="alert">
                <p className="text-lg font-semibold text-foreground">
                  This page hit an unexpected error
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {this.state.error.message}
                </p>
              </div>
              <button
                type="button"
                className="mt-2 inline-flex h-9 items-center justify-center rounded-md border bg-background px-4 text-sm font-medium shadow-xs hover:bg-accent hover:text-accent-foreground"
                onClick={() => window.location.reload()}
                aria-label="Reload application"
              >
                Reload app
              </button>
            </CardContent>
          </Card>
        </div>
      );
    }
    return this.props.children;
  }
}
