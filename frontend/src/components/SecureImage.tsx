import { memo, useEffect, useState } from 'react';
import { getAuthToken } from '../api/client';

interface SecureImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  src: string;
}

const MAX_BLOB_CACHE_ITEMS = 100;
const blobCache = new Map<string, string>();
const pendingFetches = new Map<string, Promise<string>>();

function cacheKey(src: string, token: string | null) {
  return `${token ?? ''}\n${src}`;
}

function cacheBlobUrl(key: string, url: string) {
  const existing = blobCache.get(key);
  if (existing) {
    URL.revokeObjectURL(existing);
    blobCache.delete(key);
  }

  blobCache.set(key, url);

  while (blobCache.size > MAX_BLOB_CACHE_ITEMS) {
    const oldestKey = blobCache.keys().next().value as string | undefined;
    if (!oldestKey) return;

    const oldestUrl = blobCache.get(oldestKey);
    if (oldestUrl) {
      URL.revokeObjectURL(oldestUrl);
    }
    blobCache.delete(oldestKey);
  }
}

export const SecureImage = memo(function SecureImage({
  src,
  ...props
}: SecureImageProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    if (!src) return;

    let isMounted = true;
    const token = getAuthToken();
    const key = cacheKey(src, token);

    // Check synchronous cache first
    const cached = blobCache.get(key);
    if (cached) {
      setBlobUrl(cached);
      setLoading(false);
      setError(false);
      return;
    }

    async function fetchImage() {
      try {
        setLoading(true);

        let promise = pendingFetches.get(key);
        if (!promise) {
          promise = (async () => {
            try {
              const headers: Record<string, string> = {};
              if (token) {
                headers['Authorization'] = `Bearer ${token}`;
              }

              const response = await fetch(src, { headers });
              if (!response.ok) throw new Error('Failed to fetch image');

              const blob = await response.blob();
              const url = URL.createObjectURL(blob);
              cacheBlobUrl(key, url);
              return url;
            } finally {
              pendingFetches.delete(key);
            }
          })();
          pendingFetches.set(key, promise);
        }

        const url = await promise;

        if (isMounted) {
          setBlobUrl(url);
          setError(false);
        }
      } catch {
        if (isMounted) {
          setError(true);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchImage();

    return () => {
      isMounted = false;
    };
  }, [src]);

  if (error) {
    return (
      <div
        className={`${props.className} flex items-center justify-center bg-stone-100 text-stone-400`}
      >
        <span className="text-xs">Failed to load</span>
      </div>
    );
  }

  if (loading || !blobUrl) {
    return (
      <div
        className={`${props.className} animate-pulse rounded-[inherit] bg-stone-100/90`}
      />
    );
  }

  return <img src={blobUrl} {...props} />;
});
