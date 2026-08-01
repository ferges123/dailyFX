import type { QueryKey } from '@tanstack/react-query';

const DB_NAME = 'dailyfx-offline';
const DB_VERSION = 1;
const QUERY_STORE = 'queries';
const DB_TIMEOUT_MS = 1500;

export const OFFLINE_CACHE_BUSTER = '0.20.6';

export interface PersistedOfflineQuery {
  id: string;
  queryKey: QueryKey;
  data: unknown;
  updatedAt: number;
  buster: string;
}

const PERSISTED_QUERY_PREFIXES = new Set([
  'generation-history',
  'generation-history-detail',
  'schedules',
  'people-presets',
  'effect-presets',
  'notification-presets',
]);

export function isPersistableQuery(queryKey: QueryKey): boolean {
  const prefix = queryKey[0];
  return typeof prefix === 'string' && PERSISTED_QUERY_PREFIXES.has(prefix);
}

function queryId(queryKey: QueryKey): string {
  return JSON.stringify(queryKey);
}

function withTimeout<T>(promise: Promise<T>): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) => {
      window.setTimeout(
        () => reject(new Error('Offline storage timeout')),
        DB_TIMEOUT_MS,
      );
    }),
  ]);
}

function openDatabase(): Promise<IDBDatabase> {
  if (typeof indexedDB === 'undefined') {
    return Promise.reject(new Error('IndexedDB is unavailable'));
  }

  return withTimeout(
    new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onerror = () =>
        reject(request.error ?? new Error('Unable to open offline storage'));
      request.onupgradeneeded = () => {
        if (!request.result.objectStoreNames.contains(QUERY_STORE)) {
          request.result.createObjectStore(QUERY_STORE, { keyPath: 'id' });
        }
      };
      request.onsuccess = () => resolve(request.result);
    }),
  );
}

export async function restoreOfflineQueries(): Promise<
  PersistedOfflineQuery[]
> {
  const database = await openDatabase();
  try {
    return await withTimeout(
      new Promise((resolve, reject) => {
        const request = database
          .transaction(QUERY_STORE, 'readonly')
          .objectStore(QUERY_STORE)
          .getAll();
        request.onerror = () =>
          reject(request.error ?? new Error('Unable to restore offline data'));
        request.onsuccess = () => {
          const entries = (request.result as PersistedOfflineQuery[]).filter(
            (entry) => entry.buster === OFFLINE_CACHE_BUSTER,
          );
          resolve(entries);
        };
      }),
    );
  } finally {
    database.close();
  }
}

export async function persistOfflineQuery(
  queryKey: QueryKey,
  data: unknown,
  updatedAt: number,
): Promise<void> {
  if (!isPersistableQuery(queryKey)) return;

  const database = await openDatabase();
  try {
    await withTimeout(
      new Promise<void>((resolve, reject) => {
        const request = database
          .transaction(QUERY_STORE, 'readwrite')
          .objectStore(QUERY_STORE)
          .put({
            id: queryId(queryKey),
            queryKey,
            data,
            updatedAt,
            buster: OFFLINE_CACHE_BUSTER,
          } satisfies PersistedOfflineQuery);
        request.onerror = () =>
          reject(request.error ?? new Error('Unable to persist offline data'));
        request.onsuccess = () => resolve();
      }),
    );
  } finally {
    database.close();
  }
}

export async function clearOfflineStorage(): Promise<void> {
  if (typeof indexedDB === 'undefined') return;
  await withTimeout(
    new Promise<void>((resolve, reject) => {
      const request = indexedDB.deleteDatabase(DB_NAME);
      request.onerror = () =>
        reject(request.error ?? new Error('Unable to clear offline data'));
      request.onsuccess = () => resolve();
      request.onblocked = () => resolve();
    }),
  );
}

export function clearOfflineImageCaches(): void {
  if (typeof navigator === 'undefined' || !navigator.serviceWorker) return;
  navigator.serviceWorker.controller?.postMessage({
    type: 'CLEAR_DAILYFX_OFFLINE_CACHES',
  });
}
