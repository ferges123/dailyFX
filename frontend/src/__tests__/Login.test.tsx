import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AuthProvider, useAuth } from '../api/AuthContext';
import { LoginPage } from '../pages/Login';

function TestApp() {
  const { isAuthenticated, token } = useAuth();
  return (
    <div>
      {isAuthenticated ? (
        <span data-testid="auth-success">Authenticated: {token}</span>
      ) : (
        <LoginPage />
      )}
    </div>
  );
}

describe('LoginPage', () => {
  beforeEach(() => {
    localStorage.removeItem('dailyfx_token');
    vi.restoreAllMocks();
  });

  it('renders input and submit button', () => {
    render(
      <AuthProvider>
        <TestApp />
      </AuthProvider>,
    );
    expect(screen.getByPlaceholderText('Enter your token')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Authenticate' }),
    ).toBeInTheDocument();
  });

  it('authenticates when token is valid', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(null, { status: 200 }),
    );

    render(
      <AuthProvider>
        <TestApp />
      </AuthProvider>,
    );

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

    render(
      <AuthProvider>
        <TestApp />
      </AuthProvider>,
    );

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
});
