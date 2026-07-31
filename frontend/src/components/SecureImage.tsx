import { memo, useEffect, useRef, useState } from 'react';
import { LoaderCircle } from 'lucide-react';
import { getAuthToken } from '../api/client';

interface SecureImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  src: string;
  showLoadingIndicator?: boolean;
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
  loading,
  decoding = 'async',
  showLoadingIndicator = false,
  ...props
}: SecureImageProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState<boolean>(false);
  const [loadingImg, setLoadingImg] = useState<boolean>(true);
  const [shouldFetch, setShouldFetch] = useState<boolean>(() => {
    if (loading !== 'lazy') return true;
    return typeof IntersectionObserver === 'undefined';
  });

  const placeholderRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (
      shouldFetch ||
      loading !== 'lazy' ||
      typeof IntersectionObserver === 'undefined'
    ) {
      return;
    }

    const el = placeholderRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const isIntersecting = entries.some(
          (entry) => entry.isIntersecting || entry.intersectionRatio > 0,
        );
        if (isIntersecting) {
          setShouldFetch(true);
          observer.disconnect();
        }
      },
      { rootMargin: '300px' },
    );

    observer.observe(el);

    return () => {
      observer.disconnect();
    };
  }, [loading, shouldFetch]);

  useEffect(() => {
    if (!src || !shouldFetch) return;

    let isMounted = true;
    const token = getAuthToken();
    const key = cacheKey(src, token);

    // Check synchronous cache first and refresh recency
    const cached = blobCache.get(key);
    if (cached) {
      blobCache.delete(key);
      blobCache.set(key, cached);
      setBlobUrl(cached);
      setLoadingImg(false);
      setError(false);
      return;
    }

    async function fetchImage() {
      try {
        setLoadingImg(true);

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
          setLoadingImg(false);
        }
      }
    }

    fetchImage();

    return () => {
      isMounted = false;
    };
  }, [src, shouldFetch]);

  if (error) {
    return (
      <div
        className={`${props.className ?? ''} flex items-center justify-center bg-stone-100 text-stone-400`}
      >
        <span className="text-xs">Failed to load</span>
      </div>
    );
  }

  if (loadingImg || !blobUrl) {
    return (
      <div
        ref={placeholderRef}
        className={`${props.className ?? ''} relative flex items-center justify-center rounded-[inherit] ${showLoadingIndicator ? 'bg-transparent' : 'animate-pulse bg-stone-100/90'}`}
      >
        {showLoadingIndicator && (
          <div
            role="status"
            className="pointer-events-none flex flex-col items-center justify-center gap-2 text-white/80"
          >
            <LoaderCircle
              size={30}
              aria-hidden="true"
              className="animate-spin motion-reduce:animate-none"
            />
            <span className="sr-only">Loading image...</span>
          </div>
        )}
      </div>
    );
  }

  return <img src={blobUrl} loading={loading} decoding={decoding} {...props} />;
});
