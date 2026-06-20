import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AuthProvider, useAuth } from '../api/AuthContext';
import { request } from '../api/base';
import { LoginPage } from '../pages/Login';

function TestApp() {
  const { isAuthenticated, token } = useAuth();
  const [requestError, setRequestError] = useState('');
  return (
    <div>
      {isAuthenticated ? (
        <>
          <span data-testid="auth-success">Authenticated: {token}</span>
          <button
            type="button"
            onClick={async () => {
              try {
                await request('/api/protected');
              } catch {
                setRequestError('request failed');
              }
            }}
          >
            Call protected API
          </button>
          {requestError && <span>{requestError}</span>}
        </>
      ) : (
        <LoginPage />
      )}
    </div>
  );
}

function renderWithAuth() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <TestApp />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe('LoginPage', () => {
  beforeEach(() => {
    localStorage.removeItem('dailyfx_token');
    vi.restoreAllMocks();
  });

  it('renders input and submit button', () => {
    renderWithAuth();
    expect(screen.getByPlaceholderText('Enter your token')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Authenticate' }),
    ).toBeInTheDocument();
  });

  it('shows the DailyFX logo on the login card', () => {
    renderWithAuth();

    expect(screen.getByRole('img', { name: 'DailyFX logo' })).toHaveAttribute(
      'src',
      '/logo_light.png',
    );
  });

  it('authenticates when token is valid', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(null, { status: 200 }),
    );

    renderWithAuth();

    const input = screen.getByPlaceholderText('Enter your token');
    const button = screen.getByRole('button', { name: 'Authenticate' });

    fireEvent.change(input, { target: { value: 'my-secret-token' } });
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByTestId('auth-success')).toHaveTextContent(
        'Authenticated: my-secret-token',
      );
    });
    expect(localStorage.getItem('dailyfx_token')).toBe('my-secret-token');
  });

  it('shows error when token is invalid', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(null, { status: 401 }),
    );

    renderWithAuth();

    const input = screen.getByPlaceholderText('Enter your token');
    const button = screen.getByRole('button', { name: 'Authenticate' });

    fireEvent.change(input, { target: { value: 'wrong-token' } });
    fireEvent.click(button);

    await waitFor(() => {
      expect(
        screen.getByText('Invalid token. Please try again.'),
      ).toBeInTheDocument();
    });
    expect(screen.queryByTestId('auth-success')).not.toBeInTheDocument();
    expect(localStorage.getItem('dailyfx_token')).toBeNull();
  });

  it('clears a stored invalid token and shows an invalid token message after a 401', async () => {
    localStorage.setItem('dailyfx_token', 'stale-token');
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    renderWithAuth();

    expect(screen.getByTestId('auth-success')).toHaveTextContent(
      'Authenticated: stale-token',
    );

    fireEvent.click(screen.getByRole('button', { name: 'Call protected API' }));

    expect(
      await screen.findByText('Invalid token. Please try again.'),
    ).toBeInTheDocument();
    expect(localStorage.getItem('dailyfx_token')).toBeNull();
  });
});
