import {
  cleanupOutdatedCaches,
  createHandlerBoundToURL,
  precacheAndRoute,
} from 'workbox-precaching';
import { CacheableResponsePlugin } from 'workbox-cacheable-response';
import { ExpirationPlugin } from 'workbox-expiration';
import { NavigationRoute, registerRoute } from 'workbox-routing';
import { CacheFirst } from 'workbox-strategies';

// Precache list injected by vite-plugin-pwa
precacheAndRoute(self.__WB_MANIFEST || []);

// Immediately clean up old caches from previous builds
cleanupOutdatedCaches();

const IMAGE_CACHE_NAME = 'dailyfx-images-v1';
const imageCacheStrategy = new CacheFirst({
  cacheName: IMAGE_CACHE_NAME,
  plugins: [
    new CacheableResponsePlugin({ statuses: [200] }),
    new ExpirationPlugin({
      maxEntries: 250,
      maxAgeSeconds: 60 * 60 * 24 * 30,
      purgeOnQuotaError: true,
    }),
  ],
});

const isDailyFxImage = ({ request, url }) => {
  if (request.method !== 'GET' || url.origin !== self.location.origin)
    return false;
  return (
    /^\/api\/immich\/assets\/[^/]+\/thumbnail$/.test(url.pathname) ||
    /^\/api\/generation\/history\/[^/]+\/image$/.test(url.pathname) ||
    /^\/api\/generation\/examples\//.test(url.pathname)
  );
};

// SecureImage uses fetch(), so these routes also cover authenticated image loads.
registerRoute(isDailyFxImage, imageCacheStrategy);

// Keep client-side routes working after a cold start without a network.
registerRoute(
  new NavigationRoute(createHandlerBoundToURL('/index.html'), {
    denylist: [/^\/api\//],
  }),
);

self.addEventListener('message', (event) => {
  if (event.data?.type !== 'CLEAR_DAILYFX_OFFLINE_CACHES') return;
  event.waitUntil(caches.delete(IMAGE_CACHE_NAME));
});

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
    icon: '/pwa-192x192.png',
    badge: '/pwa-192x192.png',
    image: data.image || undefined,
    data: { url: data.url || '/' },
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'dailyFX', options),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || '/';

  event.waitUntil(
    clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        for (const client of clientList) {
          if (client.url.includes(targetUrl) && 'focus' in client) {
            return client.focus();
          }
        }
        if (clients.openWindow) {
          return clients.openWindow(targetUrl);
        }
      }),
  );
});
