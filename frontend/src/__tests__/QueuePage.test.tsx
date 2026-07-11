import React from 'react';
import { render, screen } from '@testing-library/react';
import { test, expect } from 'vitest';
import { QueuePage } from '../pages/QueuePage';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

test('renders queue page title', () => {
    render(
        <QueryClientProvider client={queryClient}>
            <QueuePage />
        </QueryClientProvider>
    );
    expect(screen.getByText(/Generation Queue/i)).toBeInTheDocument();
});
