import React from 'react';
import { render, screen } from '@testing-library/react';
import { test, expect } from 'vitest';
import { SystemPage } from '../pages/SystemPage';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

test('renders system page tab options', () => {
    render(
        <QueryClientProvider client={queryClient}>
            <SystemPage />
        </QueryClientProvider>
    );
    expect(screen.getAllByText(/Generation Queue/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Audit Log/i)).toBeInTheDocument();
});
