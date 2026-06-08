# PWA Support Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Transform the DailyFX frontend into an installable Progressive Web App (PWA) with offline shell support while preserving its Web Push notification system.

**Architecture:** We will use `vite-plugin-pwa` in `injectManifest` mode, moving the existing service worker logic to `frontend/src/sw.js` and integrating it with Workbox precaching. The plugin will handle manifest generation and Service Worker compilation during the Vite build.

**Tech Stack:** React 19, Vite, TypeScript, vite-plugin-pwa, Workbox, Nginx

---

### Task 1: Add dependencies

**Files:**
- Modify: `frontend/package.json`

**Step 1: Write the failing test**
Since this is a configuration change, we will check that the build succeeds and the dependency is installed.
Run `npm run build` in `frontend/` to establish a baseline.

**Step 2: Run test to verify it fails**
Run command:
`cd frontend && npm install -D vite-plugin-pwa`

**Step 3: Write minimal implementation**
Ensure `vite-plugin-pwa` is listed in `devDependencies` of `frontend/package.json`.

**Step 4: Run test to verify it passes**
Run command:
`cd frontend && npm run build`
Expected output: Successful build without errors.

**Step 5: Commit**
```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add vite-plugin-pwa dependency"
```

---

### Task 2: Configure Vite PWA Plugin

**Files:**
- Modify: `frontend/vite.config.ts`

**Step 1: Write the failing test**
Verify that building does not yet output PWA manifest or sw assets.
Run `npm run build` and check that `frontend/dist/manifest.webmanifest` does not exist.

**Step 2: Run test to verify it fails**
Run: `ls frontend/dist/manifest.webmanifest`
Expected: File not found error.

**Step 3: Write minimal implementation**
Modify `frontend/vite.config.ts` to import and configure `vite-plugin-pwa` in `injectManifest` mode:

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  base: '/',
  plugins: [
    react(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.js',
      registerType: 'autoUpdate',
      injectManifest: {
        injectionPoint: 'self.__WB_MANIFEST',
      },
      manifest: {
        name: 'DailyFX for Immich',
        short_name: 'DailyFX',
        description: 'Turn your static photo library into a creative, AI-powered playground.',
        theme_color: '#065f46',
        background_color: '#f5f5f4',
        display: 'standalone',
        orientation: 'portrait',
        icons: [
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: 'icon.svg',
            sizes: 'any',
            type: 'image/svg+xml',
            purpose: 'any maskable',
          }
        ],
      },
    })
  ],
  server: {
    proxy: {
      '/api': 'http://localhost:8438',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test-setup.ts',
    testTimeout: 20000,
  },
});
```

**Step 4: Run test to verify it passes**
(Note: Task 3 is required to make the build pass, as `injectManifest` expects `frontend/src/sw.js` to exist). Proceed to Task 3.

---

### Task 3: Migrate and enhance Service Worker

**Files:**
- Create: `frontend/src/sw.js`
- Delete: `frontend/public/sw.js`

**Step 1: Write the failing test**
Verify build fails if `frontend/src/sw.js` does not exist.
Run `cd frontend && npm run build` - it should fail with "filename src/sw.js is not found".

**Step 2: Run test to verify it fails**
Run build. Expected: Compilation failure.

**Step 3: Write minimal implementation**
Create `frontend/src/sw.js` by merging the existing push notifications code with Workbox precaching:

```javascript
import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching';

// Precache list injected by vite-plugin-pwa
precacheAndRoute(self.__WB_MANIFEST || []);

// Immediately clean up old caches from previous builds
cleanupOutdatedCaches();

// Web Push listeners
self.addEventListener('push', (event) => {
  if (!event.data) return;
  
  let data;
  try {
    data = event.data.json();
  } catch {
    data = { title: 'dailyFX', body: event.data.text() };
  }

  const options = {
    body: data.body || '',
    icon: '/favicon.ico',
    badge: '/favicon.ico',
    image: data.image || undefined,
    data: { url: data.url || '/' }
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'dailyFX', options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || '/';
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(targetUrl) && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
```

Delete the legacy static `frontend/public/sw.js`.

**Step 4: Run test to verify it passes**
Run `cd frontend && npm run build`.
Expected: Build passes, `frontend/dist/sw.js` and `frontend/dist/manifest.webmanifest` are created.

**Step 5: Commit**
```bash
git add frontend/vite.config.ts frontend/src/sw.js
git rm frontend/public/sw.js
git commit -m "feat: migrate and configure custom service worker with Workbox precaching"
```

---

### Task 4: Add PWA App Icons

**Files:**
- Create: `frontend/public/icon.svg`
- Create: `frontend/public/pwa-192x192.png`
- Create: `frontend/public/pwa-512x512.png`

**Step 1: Write the failing test**
Verify that build warnings/errors appear if these icons are missing (as they are specified in the manifest).

**Step 2: Run test to verify it fails**
Build the app. Check if build outputs warnings/errors about missing manifest assets.

**Step 3: Write minimal implementation**
Create a beautiful SVG camera/creative filter icon at `frontend/public/icon.svg`:

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#065f46;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#047857;stop-opacity:1" />
    </linearGradient>
  </defs>
  <!-- Background -->
  <rect width="512" height="512" rx="128" fill="url(#grad)" />
  <!-- Camera Lens / Aperture shape -->
  <circle cx="256" cy="256" r="120" fill="none" stroke="#ffffff" stroke-width="24" />
  <circle cx="256" cy="256" r="80" fill="none" stroke="#ffffff" stroke-width="12" stroke-dasharray="40 15" />
  <!-- Camera Body Outline -->
  <path d="M140 180h40l20-30h112l20 30h40c22 0 40 18 40 40v160c0 22-18 40-40 40H140c-22 0-40-18-40-40V220c0-22 18-40 40-40z" fill="none" stroke="#ffffff" stroke-width="24" stroke-linejoin="round" />
  <!-- Flash Dot -->
  <circle cx="360" cy="220" r="16" fill="#ffffff" />
</svg>
```

We will also generate corresponding PNG files `frontend/public/pwa-192x192.png` and `frontend/public/pwa-512x512.png` by converting this SVG, or generating a high-quality icon using the image generation tool.

**Step 4: Run test to verify it passes**
Verify that files exist:
`ls frontend/public/icon.svg frontend/public/pwa-192x192.png frontend/public/pwa-512x512.png`

**Step 5: Commit**
```bash
git add frontend/public/icon.svg frontend/public/pwa-192x192.png frontend/public/pwa-512x512.png
git commit -m "style: add PWA icons"
```

---

### Task 5: Update Service Worker registration in Presets

**Files:**
- Modify: `frontend/src/pages/Presets.tsx`

**Step 1: Write the failing test**
Run the existing frontend tests to make sure there are no compiler issues.
`cd frontend && npm test`

**Step 2: Run test to verify it fails**
Verify if any typescript compiling issues exist before editing.

**Step 3: Write minimal implementation**
In `frontend/src/pages/Presets.tsx`, remove the manual service worker registration:

```diff
-  useEffect(() => {
-    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
-    navigator.serviceWorker.register('/sw.js').then(reg => {
-      reg.pushManager.getSubscription().then(sub => {
-        if (sub) { setPushSub(sub); setPushStatus('subscribed'); }
-      });
-    });
-  }, []);
+  useEffect(() => {
+    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
+    navigator.serviceWorker.ready.then(reg => {
+      reg.pushManager.getSubscription().then(sub => {
+        if (sub) { setPushSub(sub); setPushStatus('subscribed'); }
+      });
+    });
+  }, []);
```

**Step 4: Run test to verify it passes**
Run `cd frontend && npm run build` and `npm test` to verify code compiles and all tests pass.

**Step 5: Commit**
```bash
git add frontend/src/pages/Presets.tsx
git commit -m "refactor: use navigator.serviceWorker.ready for push notification status"
```

---

### Task 6: Add HTML Meta Tags

**Files:**
- Modify: `frontend/index.html`

**Step 1: Write the failing test**
Check `frontend/index.html` to confirm it lacks theme-color and PWA meta tags.

**Step 2: Run test to verify it fails**
`grep "theme-color" frontend/index.html` (returns empty).

**Step 3: Write minimal implementation**
Modify `frontend/index.html` to add tags:

```diff
   <head>
     <meta charset="UTF-8" />
     <meta name="viewport" content="width=device-width, initial-scale=1.0" />
     <title>DailyFX for immich</title>
+    <link rel="icon" type="image/svg+xml" href="/icon.svg" />
+    <link rel="apple-touch-icon" href="/pwa-192x192.png" />
+    <meta name="theme-color" content="#065f46" />
+    <meta name="mobile-web-app-capable" content="yes" />
+    <meta name="apple-mobile-web-app-capable" content="yes" />
+    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
+    <meta name="apple-mobile-web-app-title" content="DailyFX" />
   </head>
```

**Step 4: Run test to verify it passes**
Verify tags exist.

**Step 5: Commit**
```bash
git add frontend/index.html
git commit -m "feat: add PWA mobile web app capabilities and metadata to index.html"
```
