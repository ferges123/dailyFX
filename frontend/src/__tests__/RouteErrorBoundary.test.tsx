import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RouteErrorBoundary } from '../components/RouteErrorBoundary';

function CrashingRoute(): never {
  throw new Error('route exploded');
}

describe('RouteErrorBoundary', () => {
  let consoleError: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleError.mockRestore();
  });

  it('renders a route-scoped fallback when a child route crashes', () => {
    render(
      <RouteErrorBoundary>
        <CrashingRoute />
      </RouteErrorBoundary>,
    );

    expect(screen.getByText('This page could not be rendered.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reload page' })).toBeInTheDocument();
  });
});
