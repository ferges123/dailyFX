import {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from 'react';
import { useQueryClient, type QueryClient } from '@tanstack/react-query';
import { registerOnUnauthorized } from './client';

interface AuthContextType {
  token: string | null;
  setToken: (token: string | null) => void;
  isAuthenticated: boolean;
  authError: string | null;
  clearAuthError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() =>
    localStorage.getItem('dailyfx_token'),
  );
  const [authError, setAuthError] = useState<string | null>(null);

  let queryClient: QueryClient | null = null;
  try {
    queryClient = useQueryClient();
  } catch {
    // QueryClientProvider not present in context (common in simple unit tests)
  }

  const setToken = (newToken: string | null) => {
    setAuthError(null);
    setTokenState(newToken);
    if (newToken) {
      localStorage.setItem('dailyfx_token', newToken);
    } else {
      localStorage.removeItem('dailyfx_token');
    }
  };

  useEffect(() => {
    if (!queryClient) return;
    registerOnUnauthorized(() => {
      setAuthError('Invalid token. Please try again.');
      setTokenState(null);
      localStorage.removeItem('dailyfx_token');
      queryClient.clear();
    });
  }, [queryClient]);

  const isAuthenticated = !!token;
  const clearAuthError = () => setAuthError(null);

  return (
    <AuthContext.Provider
      value={{ token, setToken, isAuthenticated, authError, clearAuthError }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
