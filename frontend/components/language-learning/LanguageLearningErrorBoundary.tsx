"use client";

import { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class LanguageLearningErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log error to console in development
    if (process.env.NODE_ENV === "development") {
      console.error("LanguageLearning Error:", error, errorInfo);
    }

    // Call optional error handler
    this.props.onError?.(error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div className="flex min-h-[100dvh] items-center justify-center bg-bg-primary px-6">
            <div className="mx-auto max-w-md text-center">
              <div className="mb-4 flex justify-center">
                <div className="w-16 h-16 rounded-full bg-accent-danger/10 flex items-center justify-center">
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" className="text-accent-danger">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
                    <path d="M12 8V12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    <circle cx="12" cy="16" r="1" fill="currentColor" />
                  </svg>
                </div>
              </div>
              <h2 className="font-display text-xl text-text-primary mb-2">
                Something went wrong
              </h2>
              <p className="font-body text-sm text-text-secondary mb-4">
                {this.state.error?.message || "An unexpected error occurred"}
              </p>
              <div className="flex flex-col gap-2">
                <button
                  onClick={() => this.setState({ hasError: false, error: null })}
                  className="rounded-full bg-accent-primary px-6 py-2.5 font-ui text-sm font-medium text-accent-foreground transition-colors hover:bg-accent-primary/90"
                >
                  Try Again
                </button>
                <a
                  href="/brief"
                  className="rounded-full border border-rule bg-bg-surface px-6 py-2.5 font-ui text-sm text-accent-primary transition-colors hover:bg-bg-surface-2"
                >
                  Back to briefings
                </a>
              </div>
            </div>
          </div>
        )
      );
    }

    return this.props.children;
  }
}
