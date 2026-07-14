import { useQuery, useQueryClient } from '@tanstack/react-query';
import { lazy, Suspense, type ReactNode } from 'react';
import {
  Bell,
  CalendarDays,
  Camera,
  History,
  Image,
  LogOut,
  Settings,
  Sparkles,
  ClipboardList,
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
  useParams,
} from 'react-router-dom';
import { getHealth } from './api/client';
import { AuthProvider, useAuth } from './api/AuthContext';
import { BrandLogo } from './components/BrandLogo';
import { RouteErrorBoundary } from './components/RouteErrorBoundary';
import { APP_VERSION } from './version';

const GITHUB_URL = 'https://github.com/ferges123/dailyFX';

const HistoryPage = lazy(() => import('./pages/History/HistoryPage'));
const SystemPage = lazy(() =>
  import('./pages/SystemPage').then((module) => ({
    default: module.SystemPage,
  })),
);
const StudioPage = lazy(() =>
  import('./pages/StudioPage').then((module) => ({
    default: module.StudioPage,
  })),
);
const SettingsPage = lazy(() =>
  import('./pages/Settings').then((module) => ({
    default: module.SettingsPage,
  })),
);
const FilterPresetsPage = lazy(() =>
  import('./pages/Presets').then((module) => ({
    default: module.FilterPresetsPage,
  })),
);
const EffectPresetsPage = lazy(() =>
  import('./pages/Presets').then((module) => ({
    default: module.EffectPresetsPage,
  })),
);
const NotificationPresetsPage = lazy(() =>
  import('./pages/Presets').then((module) => ({
    default: module.NotificationPresetsPage,
  })),
);
const AIEffectsPage = lazy(() =>
  import('./pages/AIEffects').then((module) => ({
    default: module.AIEffectsPage,
  })),
);
const SchedulesPage = lazy(() =>
  import('./pages/Schedules').then((module) => ({
    default: module.SchedulesPage,
  })),
);
const LoginPage = lazy(() =>
  import('./pages/Login').then((module) => ({
    default: module.LoginPage,
  })),
);

const GalleryPage = lazy(() =>
  import('./pages/Gallery').then((module) => ({
    default: module.GalleryPage,
  })),
);

function StatisticsTabRedirect() {
  const { tab } = useParams<{ tab?: string }>();
  return <Navigate to={`/system/${tab || 'statistics'}`} replace />;
}

function PageLoadingFallback() {
  return (
    <div className="rounded-lg border border-stone-200 bg-white/70 px-4 py-4 text-sm font-medium text-stone-600">
      Loading page...
    </div>
  );
}

function RouteView({ children }: { children: ReactNode }) {
  return (
    <RouteErrorBoundary>
      <Suspense fallback={<PageLoadingFallback />}>{children}</Suspense>
    </RouteErrorBoundary>
  );
}

function AppShell() {
  const { isAuthenticated, setToken } = useAuth();
  const queryClient = useQueryClient();
  const health = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    retry: false,
  });
  const location = useLocation();

  if (health.isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-stone-50">
        <div className="text-sm font-medium text-stone-600">Loading...</div>
      </div>
    );
  }

  const authRequiredByBackend = health.data?.auth_enabled;
  if (authRequiredByBackend && !isAuthenticated) {
    return (
      <RouteView>
        <LoginPage />
      </RouteView>
    );
  }

  const isHistoryRoute = location.pathname.startsWith('/history');
  const isStudioRoute = location.pathname.startsWith('/studio');
  const isSchedulesRoute = location.pathname.startsWith('/schedules');
  const isPresetsRoute = location.pathname.startsWith('/presets');
  const isSettingsRoute = location.pathname.startsWith('/settings');

  const isGalleryRoute = location.pathname.startsWith('/gallery');
  const isSystemRoute = location.pathname.startsWith('/system');

  function handleLogout() {
    setToken(null);
    queryClient.clear();
  }

  if (location.pathname === '/') {
    return <Navigate to="/gallery" replace />;
  }

  return (
    <div className="app-shell md:grid md:min-h-screen md:grid-cols-[18rem_minmax(0,1fr)]">
      <header className="sticky top-0 z-20 border-b border-white/70 bg-[rgba(248,246,239,0.82)] backdrop-blur-xl md:hidden">
        <div className="mx-auto flex items-center justify-between px-3 py-2">
          <div className="flex items-center gap-2 md:gap-3">
            <BrandLogo className="h-11 w-11" />
            <div>
              <h1 className="text-base font-semibold leading-none text-stone-950">
                DailyFX for immich
              </h1>
              <p className="mt-0.5 text-xs text-stone-500">
                Creative effect studio
              </p>
            </div>
          </div>
          {authRequiredByBackend && (
            <button
              type="button"
              onClick={handleLogout}
              className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-stone-200 bg-white/80 text-stone-500 shadow-xs transition hover:border-stone-300 hover:text-red-600"
              title="Log out"
            >
              <LogOut size={16} />
            </button>
          )}
        </div>
      </header>

      <aside className="hidden border-r border-white/70 bg-[rgba(248,246,239,0.72)] px-4 py-5 backdrop-blur-xl md:flex md:flex-col md:sticky md:top-0 md:h-screen">
        <div className="flex items-center gap-3 px-1">
          <BrandLogo className="h-16 w-16" />
          <div>
            <h1 className="text-lg font-semibold leading-none text-stone-950">
              DailyFX for immich
            </h1>
            <p className="mt-1 text-sm text-stone-500">
              Creative effect studio
            </p>
          </div>
        </div>

        <nav aria-label="Desktop navigation" className="mt-8 grid gap-1.5">
          <SidebarNavLink
            to="/gallery"
            active={isGalleryRoute}
            icon={<Image size={17} />}
          >
            Gallery
          </SidebarNavLink>
          <SidebarNavLink
            to="/history"
            active={isHistoryRoute}
            icon={<History size={17} />}
          >
            History
          </SidebarNavLink>
          <SidebarNavLink
            to="/schedules"
            active={isSchedulesRoute}
            icon={<CalendarDays size={17} />}
          >
            Schedules
          </SidebarNavLink>
          <SidebarNavLink
            to="/presets"
            active={isPresetsRoute}
            icon={<Sparkles size={17} />}
          >
            Presets
          </SidebarNavLink>
          <SidebarNavLink
            to="/studio"
            active={isStudioRoute}
            icon={<Camera size={17} />}
          >
            Studio
          </SidebarNavLink>
          <SidebarNavLink
            to="/system"
            active={isSystemRoute}
            icon={<ClipboardList size={17} />}
          >
            System
          </SidebarNavLink>
          <SidebarNavLink
            to="/settings"
            active={isSettingsRoute}
            icon={<Settings size={17} />}
          >
            Settings
          </SidebarNavLink>
        </nav>

        <div className="mt-auto pt-6">
          {authRequiredByBackend && (
            <button
              type="button"
              onClick={handleLogout}
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-stone-200 bg-white/80 text-sm font-semibold text-stone-600 shadow-xs transition hover:border-stone-300 hover:text-red-600"
              title="Log out"
            >
              <LogOut size={16} />
              Log out
            </button>
          )}
          <div className="mt-6 rounded-2xl border border-stone-200/70 bg-white/65 px-3 py-3 text-xs text-stone-500">
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 font-semibold text-stone-700 transition hover:text-emerald-800"
              title="Open DailyFX on GitHub"
            >
              <Bell size={13} />
              DailyFX {APP_VERSION}
            </a>
            <div className="mt-2 flex flex-wrap gap-x-2 gap-y-1">
              <a
                href="https://polyformproject.org/licenses/noncommercial/1.0.0/"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-emerald-800 hover:underline"
              >
                PolyForm Noncommercial License 1.0.0
              </a>
            </div>
          </div>
        </div>
      </aside>

      <div className="min-w-0">
        <main className="grid gap-3 px-3 py-3 pb-32 md:gap-4 md:px-5 md:py-5 md:pb-6">
          <Routes>
            <Route
              path="/history"
              element={
                <RouteView>
                  <HistoryPage />
                </RouteView>
              }
            />
            <Route
              path="/history/:taskId"
              element={
                <RouteView>
                  <HistoryPage />
                </RouteView>
              }
            />
            <Route
              path="/studio"
              element={
                <RouteView>
                  <StudioPage />
                </RouteView>
              }
            />
            <Route
              path="/system/:tab?"
              element={
                <RouteView>
                  <SystemPage />
                </RouteView>
              }
            />
            <Route
              path="/queue"
              element={<Navigate to="/system/queue" replace />}
            />
            <Route
              path="/schedules"
              element={
                <RouteView>
                  <SchedulesPage />
                </RouteView>
              }
            />
            <Route
              path="/schedules/new"
              element={
                <RouteView>
                  <SchedulesPage />
                </RouteView>
              }
            />
            <Route
              path="/schedules/:scheduleId/edit"
              element={
                <RouteView>
                  <SchedulesPage />
                </RouteView>
              }
            />
            <Route path="/presets" element={<PresetsLayout />}>
              <Route index element={<Navigate to="filters" replace />} />
              <Route
                path="filters"
                element={
                  <RouteView>
                    <FilterPresetsPage />
                  </RouteView>
                }
              />
              <Route
                path="effects"
                element={
                  <RouteView>
                    <EffectPresetsPage />
                  </RouteView>
                }
              />
              <Route
                path="ai-effects"
                element={
                  <RouteView>
                    <AIEffectsPage />
                  </RouteView>
                }
              />
              <Route
                path="notifications"
                element={
                  <RouteView>
                    <NotificationPresetsPage />
                  </RouteView>
                }
              />
            </Route>
            <Route
              path="/statistics"
              element={<Navigate to="/system/statistics" replace />}
            />
            <Route
              path="/statistics/:tab"
              element={<StatisticsTabRedirect />}
            />
            <Route
              path="/gallery"
              element={
                <RouteView>
                  <GalleryPage />
                </RouteView>
              }
            />
            <Route
              path="/audit"
              element={<Navigate to="/system/audit" replace />}
            />
            <Route
              path="/settings"
              element={
                <RouteView>
                  <SettingsPage />
                </RouteView>
              }
            />

            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </main>
      </div>

      <nav
        aria-label="Mobile navigation"
        className="fixed bottom-0 left-0 right-0 z-20 flex items-center justify-around border-t border-white/70 bg-[rgba(248,246,239,0.88)] px-2 py-1.5 shadow-[0_-8px_30px_rgba(36,29,16,0.08)] backdrop-blur-xl md:hidden"
      >
        <BottomNavLink to="/gallery" active={isGalleryRoute} label="Gallery">
          <Image size={18} />
        </BottomNavLink>
        <BottomNavLink to="/history" active={isHistoryRoute} label="History">
          <History size={18} />
        </BottomNavLink>
        <BottomNavLink
          to="/schedules"
          active={isSchedulesRoute}
          label="Schedules"
        >
          <CalendarDays size={18} />
        </BottomNavLink>
        <BottomNavLink to="/presets" active={isPresetsRoute} label="Presets">
          <Sparkles size={18} />
        </BottomNavLink>
        <BottomNavLink to="/studio" active={isStudioRoute} label="Studio">
          <Camera size={18} />
        </BottomNavLink>
        <BottomNavLink
          to="/system"
          active={isSystemRoute}
          label="System"
        >
          <ClipboardList size={18} />
        </BottomNavLink>
        <BottomNavLink
          to="/settings"
          active={location.pathname === '/settings'}
          label="Settings"
        >
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

function SidebarNavLink({
  to,
  active,
  icon,
  children,
}: {
  to: string;
  active: boolean;
  icon: ReactNode;
  children: ReactNode;
}) {
  const activeClass = active
    ? 'border-emerald-900/10 bg-emerald-800 text-white shadow-[0_10px_20px_rgba(15,81,50,0.18)]'
    : 'border-transparent text-stone-700 hover:border-stone-200 hover:bg-white/70 hover:text-stone-900';

  return (
    <NavLink
      to={to}
      className={`inline-flex h-11 items-center gap-2 rounded-xl border px-3 text-sm font-semibold transition ${activeClass}`}
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
      className={`flex-1 shrink-0 rounded-[0.8rem] py-1.5 px-3.5 text-center text-xs font-semibold transition-all ${
        active
          ? 'bg-white text-emerald-950 shadow-xs'
          : 'text-stone-600 hover:text-stone-900'
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
      <div className="app-surface p-1 flex gap-1.5 overflow-x-auto whitespace-nowrap [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <PresetSubnavLink
          to="/presets/filters"
          active={location.pathname === '/presets/filters'}
        >
          Filters
        </PresetSubnavLink>
        <PresetSubnavLink
          to="/presets/effects"
          active={location.pathname === '/presets/effects'}
        >
          Effects
        </PresetSubnavLink>
        <PresetSubnavLink
          to="/presets/ai-effects"
          active={location.pathname === '/presets/ai-effects'}
        >
          AI Effects
        </PresetSubnavLink>
        <PresetSubnavLink
          to="/presets/notifications"
          active={location.pathname === '/presets/notifications'}
        >
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
          active
            ? 'bg-emerald-100 text-emerald-800 shadow-xs'
            : 'text-stone-500'
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
        <div className="text-xs font-semibold uppercase tracking-[0.24em] text-stone-400">
          404
        </div>
        <h2 className="mt-2 text-2xl font-semibold text-stone-950">
          Page not found
        </h2>
        <p className="mt-2 text-sm leading-6 text-stone-500">
          The route you requested does not exist. Use the navigation to return
          to a supported section.
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          <Link to="/history" className="app-button-primary px-4 py-2 text-sm">
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
