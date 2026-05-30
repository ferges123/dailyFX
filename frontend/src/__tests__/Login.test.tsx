import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
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
  it('renders input and submit button', () => {
    render(
      <AuthProvider>
        <TestApp />
      </AuthProvider>
    );
    expect(screen.getByPlaceholderText('Enter your token')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Authenticate' })).toBeInTheDocument();
  });

  it('authenticates when token is submitted', () => {
    localStorage.removeItem('dailyfx_token');
    render(
      <AuthProvider>
        <TestApp />
      </AuthProvider>
    );

    const input = screen.getByPlaceholderText('Enter your token');
    const button = screen.getByRole('button', { name: 'Authenticate' });

    fireEvent.change(input, { target: { value: 'my-secret-token' } });
    fireEvent.click(button);

    expect(screen.getByTestId('auth-success')).toHaveTextContent('Authenticated: my-secret-token');
    expect(localStorage.getItem('dailyfx_token')).toBe('my-secret-token');
  });
});
