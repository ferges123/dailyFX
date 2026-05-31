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
  Outlet,
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
    <div className="app-shell">
      <header className="sticky top-0 z-20 border-b border-white/70 bg-[rgba(248,246,239,0.82)] backdrop-blur-xl">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-3 py-2 md:px-4 md:py-3">
          <div className="flex items-center gap-2 md:gap-3">
            <div className="flex h-9 w-9 md:h-11 md:w-11 items-center justify-center rounded-xl md:rounded-2xl border border-emerald-900/10 bg-emerald-900 text-white shadow-[0_14px_28px_rgba(15,81,50,0.22)]">
              <Sparkles className="h-4.5 w-4.5 md:h-[18px] md:w-[18px]" />
            </div>
            <div>
              <h1 className="text-lg md:text-xl font-semibold leading-none text-stone-950">DailyFX for immich</h1>
              <p className="mt-0.5 md:mt-1 text-xs md:text-sm text-stone-500">Creative effect studio</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {authRequiredByBackend && (
              <button
                type="button"
                onClick={handleLogout}
                className="md:hidden inline-flex h-10 w-10 items-center justify-center rounded-xl border border-stone-200 bg-white/80 text-stone-500 shadow-sm transition hover:border-stone-300 hover:text-red-600"
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
              <HeaderNavLink to="/presets" icon={<Sparkles size={16} />}>
                Presets
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
                    className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-stone-200 bg-white/80 text-stone-500 shadow-sm transition hover:border-stone-300 hover:text-red-600"
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

      <main className="mx-auto grid max-w-5xl gap-3 px-3 py-3 pb-24 md:gap-4 md:px-4 md:py-4 md:pb-6">
        {/* Subnavigation is now handled contextually inside PresetsLayout for both desktop and mobile */}

        <Routes>
          <Route path="/" element={<Navigate to="/history" replace />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/schedules" element={<SchedulesPage />} />
          <Route path="/presets" element={<PresetsLayout />}>
            <Route index element={<Navigate to="filters" replace />} />
            <Route path="filters" element={<FilterPresetsPage />} />
            <Route path="effects" element={<EffectPresetsPage />} />
            <Route path="notifications" element={<NotificationPresetsPage />} />
          </Route>
          <Route path="/settings" element={<SettingsPage />} />
          <Route
            path="*"
            element={
              <NotFoundPage />
            }
          />
        </Routes>
      </main>

      <footer className="mx-auto max-w-5xl px-3 pb-24 pt-3 text-center text-xs text-stone-400 md:pb-6 md:pt-8">
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

      <nav className="fixed bottom-0 left-0 right-0 z-20 flex items-center justify-around border-t border-white/70 bg-[rgba(248,246,239,0.88)] px-2 py-1.5 shadow-[0_-8px_30px_rgba(36,29,16,0.08)] backdrop-blur-xl md:hidden">
        <BottomNavLink to="/history" active={location.pathname === '/history'} label="History">
          <History size={18} />
        </BottomNavLink>
        <BottomNavLink to="/schedules" active={location.pathname === '/schedules'} label="Schedules">
          <CalendarDays size={18} />
        </BottomNavLink>
        <BottomNavLink to="/presets" active={isPresetsRoute} label="Presets">
          <Sparkles size={18} />
        </BottomNavLink>
        <BottomNavLink to="/settings" active={location.pathname === '/settings'} label="Settings">
          <Settings size={18} />
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
        `inline-flex h-10 items-center gap-2 rounded-xl px-3 text-sm font-semibold transition ${
          isActive
            ? 'border border-emerald-900/10 bg-emerald-800 text-white shadow-[0_10px_20px_rgba(15,81,50,0.18)]'
            : 'border border-transparent text-stone-700 hover:border-stone-200 hover:bg-white/70 hover:text-stone-900'
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
      className={`flex-1 rounded-[0.8rem] py-1.5 text-center text-xs font-semibold transition-all ${
        active ? 'bg-white text-emerald-950 shadow-sm' : 'text-stone-600 hover:text-stone-900'
      }`}
    >
      {children}
    </Link>
  );
}

function PresetsLayout() {
  const location = useLocation();
  return (
    <div className="grid gap-3">
      <div className="app-surface p-1 flex gap-1.5">
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
      <Outlet />
    </div>
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
      className={`flex flex-col items-center justify-center gap-0 rounded-xl px-2 py-0.5 text-[9px] font-semibold transition-colors ${
        active ? 'text-emerald-800' : 'text-stone-500 hover:text-stone-800'
      }`}
    >
      <div
        className={`flex h-5 w-9 items-center justify-center rounded-full transition-colors ${
          active ? 'bg-emerald-100 text-emerald-800 shadow-sm' : 'text-stone-500'
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
    <section className="grid min-h-[40vh] place-items-center px-4 py-10">
      <div className="w-full max-w-md rounded-3xl border border-stone-200/80 bg-white/85 p-7 text-center shadow-[0_18px_48px_rgba(36,29,16,0.08)] backdrop-blur-md">
        <div className="text-xs font-semibold uppercase tracking-[0.24em] text-stone-400">404</div>
        <h2 className="mt-2 text-2xl font-semibold text-stone-950">Page not found</h2>
        <p className="mt-2 text-sm leading-6 text-stone-500">
          The route you requested does not exist. Use the navigation to return to a supported section.
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          <Link
            to="/history"
            className="app-button-primary px-4 py-2 text-sm"
          >
            Go to history
          </Link>
          <Link
            to="/presets/filters"
            className="app-button-secondary px-4 py-2 text-sm"
          >
            Browse presets
          </Link>
        </div>
      </div>
    </section>
  );
}
