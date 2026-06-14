import { Component, type ErrorInfo, type ReactNode } from 'react';
import { logger } from '../utils/logger';

type RouteErrorBoundaryProps = {
  children: ReactNode;
};

type RouteErrorBoundaryState = {
  hasError: boolean;
};

export class RouteErrorBoundary extends Component<
  RouteErrorBoundaryProps,
  RouteErrorBoundaryState
> {
  state: RouteErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): RouteErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    logger.error('Route render failed', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <section className="rounded-lg border border-red-200 bg-red-50 px-4 py-4 text-red-900">
          <h2 className="text-base font-semibold">
            This page could not be rendered.
          </h2>
          <p className="mt-1 text-sm text-red-700">
            Reload the page to retry the current route.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-3 inline-flex h-9 items-center rounded-md border border-red-200 bg-white px-3 text-sm font-semibold text-red-800 transition hover:border-red-300 hover:bg-red-100"
          >
            Reload page
          </button>
        </section>
      );
    }

    return this.props.children;
  }
}
