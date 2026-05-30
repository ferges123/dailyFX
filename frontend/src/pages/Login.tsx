import { useState } from 'react';
import { Lock } from 'lucide-react';
import { useAuth } from '../api/AuthContext';

export function LoginPage() {
  const [inputToken, setInputToken] = useState('');
  const { setToken } = useAuth();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputToken.trim()) {
      setToken(inputToken.trim());
    }
  };

  return (
    <div className="flex min-h-[60vh] items-center justify-center px-4">
      <div className="w-full max-w-md rounded-xl border border-stone-200 bg-white p-8 shadow-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-50 text-emerald-700">
            <Lock size={24} />
          </div>
          <h2 className="text-2xl font-semibold text-stone-900">Protected Access</h2>
          <p className="mt-2 text-stone-500">Please enter your application access token to continue.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="token" className="block text-sm font-medium text-stone-700">
              Access Token
            </label>
            <input
              id="token"
              type="password"
              value={inputToken}
              onChange={(e) => setInputToken(e.target.value)}
              placeholder="Enter your token"
              className="mt-1 block w-full rounded-lg border border-stone-300 bg-stone-50 px-4 py-2 text-stone-900 focus:border-emerald-500 focus:ring-emerald-500 outline-none transition-colors"
              required
            />
          </div>
          <button
            type="submit"
            className="w-full rounded-lg bg-emerald-800 px-4 py-2.5 font-medium text-white hover:bg-emerald-900 transition-colors focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
          >
            Authenticate
          </button>
        </form>
        
        <div className="mt-6 text-center text-xs text-stone-400">
          Tip: Check your <code>.env</code> file for <code>APP_ACCESS_TOKEN</code>.
        </div>
      </div>
    </div>
  );
}
