import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import './styles.css';
import {
  persistOfflineQuery,
  restoreOfflineQueries,
  isPersistableQuery,
} from './offline/storage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000, // 30 seconds
      refetchOnWindowFocus: false,
    },
  },
});

async function bootstrap() {
  try {
    const persistedQueries = await restoreOfflineQueries();
    for (const entry of persistedQueries) {
      queryClient.setQueryData(entry.queryKey, entry.data, {
        updatedAt: entry.updatedAt,
      });
    }
  } catch {
    // IndexedDB is optional; the app remains usable with the in-memory cache.
  }

  queryClient.getQueryCache().subscribe((event) => {
    const query = event.query;
    if (event.type !== 'updated' || query.state.status !== 'success') return;
    if (!isPersistableQuery(query.queryKey)) return;
    void persistOfflineQuery(
      query.queryKey,
      query.state.data,
      query.state.dataUpdatedAt,
    );
  });

  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </React.StrictMode>,
  );
}

void bootstrap();
