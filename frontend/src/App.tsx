import { useQuery, useQueryClient } from '@tanstack/react-query';
import { type ReactNode } from 'react';
import {
  Bell,
  CalendarDays,
  Filter,
  History,
  LogOut,
  Settings,
  Sparkles,
} from 'lucide-react';
import {
  BrowserRouter,
  Link,
  Navigate,
  NavLink,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom';
import HistoryPage from './pages/History/HistoryPage';
import { SettingsPage } from './pages/Settings';
import { FilterPresetsPage, EffectPresetsPage, NotificationPresetsPage } from './pages/Presets';
import { SchedulesPage } from './pages/Schedules';
import { LoginPage } from './pages/Login';
import { getHealth } from './api/client';
import { AuthProvider, useAuth } from './api/AuthContext';

function AppShell() {
  const { isAuthenticated, setToken } = useAuth();
  const queryClient = useQueryClient();
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, retry: false });
  const location = useLocation();

  const authRequiredByBackend = health.data?.auth_enabled;
  if (authRequiredByBackend && !isAuthenticated) {
    return <LoginPage />;
  }

  const isPresetsRoute = location.pathname.startsWith('/presets');

  function handleLogout() {
    setToken(null);
    queryClient.clear();
  }

  return (
    <div className="min-h-screen bg-[#f7f8f4] text-stone-950">
      <header className="sticky top-0 z-10 border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <div>
            <h1 className="text-xl font-semibold">DailyFX for immich</h1>
            <p className="text-sm text-stone-500">Creative effect studio</p>
          </div>
          <div className="flex items-center gap-2">
            {authRequiredByBackend && (
              <button
                type="button"
                onClick={handleLogout}
                className="md:hidden inline-flex h-9 w-9 items-center justify-center rounded-md text-stone-500 transition-colors hover:bg-stone-100 hover:text-red-600"
                title="Log out"
              >
                <LogOut size={16} />
              </button>
            )}
            <nav className="hidden items-center gap-2 md:flex">
              <HeaderNavLink to="/history" icon={<History size={16} />}>
                History
              </HeaderNavLink>
              <HeaderNavLink to="/schedules" icon={<CalendarDays size={16} />}>
                Schedules
              </HeaderNavLink>
              <HeaderNavLink to="/presets/filters" icon={<Filter size={16} />}>
                Filters
              </HeaderNavLink>
              <HeaderNavLink to="/presets/effects" icon={<Sparkles size={16} />}>
                Effects
              </HeaderNavLink>
              <HeaderNavLink to="/presets/notifications" icon={<Bell size={16} />}>
                Notifications
              </HeaderNavLink>
              <HeaderNavLink to="/settings" icon={<Settings size={16} />}>
                Settings
              </HeaderNavLink>
              {authRequiredByBackend && (
                <>
                  <div className="mx-2 h-6 w-px bg-stone-200" />
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="inline-flex h-9 w-9 items-center justify-center rounded-md text-stone-500 transition-colors hover:bg-stone-100 hover:text-red-600"
                    title="Log out"
                  >
                    <LogOut size={16} />
                  </button>
                </>
              )}
            </nav>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-5xl gap-4 px-4 py-4 pb-24 md:pb-4">
        {isPresetsRoute && (
          <div className="flex rounded-lg bg-stone-200/60 p-1 md:hidden">
            <PresetSubnavLink to="/presets/filters" active={location.pathname === '/presets/filters'}>
              Filters
            </PresetSubnavLink>
            <PresetSubnavLink to="/presets/effects" active={location.pathname === '/presets/effects'}>
              Effects
            </PresetSubnavLink>
            <PresetSubnavLink to="/presets/notifications" active={location.pathname === '/presets/notifications'}>
              Notifications
            </PresetSubnavLink>
          </div>
        )}

        <Routes>
          <Route path="/" element={<Navigate to="/history" replace />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/schedules" element={<SchedulesPage />} />
          <Route path="/presets" element={<Navigate to="/presets/filters" replace />} />
          <Route path="/presets/filters" element={<FilterPresetsPage />} />
          <Route path="/presets/effects" element={<EffectPresetsPage />} />
          <Route path="/presets/notifications" element={<NotificationPresetsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route
            path="*"
            element={
              <NotFoundPage />
            }
          />
        </Routes>
      </main>

      <footer className="mx-auto max-w-5xl px-4 pb-28 pt-4 text-center text-xs text-stone-400 md:pb-6 md:pt-8 border-t border-stone-200/50">
        <p className="flex items-center justify-center gap-1.5 flex-wrap">
          <span>DailyFX 0.0.1</span>
          <span className="text-stone-300">•</span>
          <a
            href="https://github.com/ferges123/dailyFX"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-emerald-800 hover:underline"
          >
            GitHub
          </a>
          <span className="text-stone-300">•</span>
          <a
            href="https://polyformproject.org/licenses/noncommercial/1.0.0/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-emerald-800 hover:underline"
          >
            PolyForm Noncommercial License 1.0.0
          </a>
        </p>
      </footer>

      <nav className="fixed bottom-0 left-0 right-0 z-20 flex items-center justify-around border-t border-stone-200 bg-white/90 px-2 py-2 shadow-[0_-4px_12px_rgba(0,0,0,0.05)] backdrop-blur-md md:hidden">
        <BottomNavLink to="/history" active={location.pathname === '/history'} label="History">
          <History size={20} />
        </BottomNavLink>
        <BottomNavLink to="/schedules" active={location.pathname === '/schedules'} label="Schedules">
          <CalendarDays size={20} />
        </BottomNavLink>
        <BottomNavLink to="/presets/filters" active={isPresetsRoute} label="Presets">
          <Sparkles size={20} />
        </BottomNavLink>
        <BottomNavLink to="/settings" active={location.pathname === '/settings'} label="Settings">
          <Settings size={20} />
        </BottomNavLink>
      </nav>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppShell />
      </AuthProvider>
    </BrowserRouter>
  );
}

function HeaderNavLink({
  to,
  icon,
  children,
}: {
  to: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium ${
          isActive ? 'bg-emerald-800 text-white' : 'text-stone-700 hover:bg-stone-100'
        }`
      }
    >
      {icon}
      {children}
    </NavLink>
  );
}

function PresetSubnavLink({
  to,
  active,
  children,
}: {
  to: string;
  active: boolean;
  children: ReactNode;
}) {
  return (
    <Link
      to={to}
      className={`flex-1 rounded-md py-1.5 text-center text-xs font-semibold transition-all ${
        active ? 'bg-white text-emerald-950 shadow-sm' : 'text-stone-600 hover:text-stone-900'
      }`}
    >
      {children}
    </Link>
  );
}

function BottomNavLink({
  active,
  to,
  label,
  children,
}: {
  active: boolean;
  to: string;
  label: string;
  children: ReactNode;
}) {
  return (
    <Link
      to={to}
      className={`flex flex-col items-center justify-center gap-0.5 rounded-md px-3 text-[10px] font-semibold transition-colors ${
        active ? 'text-emerald-800' : 'text-stone-500 hover:text-stone-800'
      }`}
    >
      <div
        className={`flex h-6 w-10 items-center justify-center rounded-full transition-colors ${
          active ? 'bg-emerald-50 text-emerald-800' : 'text-stone-500'
        }`}
      >
        {children}
      </div>
      <span>{label}</span>
    </Link>
  );
}

function NotFoundPage() {
  return (
    <section className="grid min-h-[40vh] place-items-center">
      <div className="w-full max-w-md rounded-xl border border-stone-200 bg-white p-6 text-center shadow-sm">
        <div className="text-xs font-semibold uppercase tracking-[0.22em] text-stone-400">404</div>
        <h2 className="mt-2 text-2xl font-semibold text-stone-950">Page not found</h2>
        <p className="mt-2 text-sm text-stone-500">
          The route you requested does not exist. Use the navigation to return to a supported section.
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          <Link
            to="/history"
            className="inline-flex items-center justify-center rounded-md bg-emerald-800 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-900"
          >
            Go to history
          </Link>
          <Link
            to="/presets/filters"
            className="inline-flex items-center justify-center rounded-md border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50"
          >
            Browse presets
          </Link>
        </div>
      </div>
    </section>
  );
}
