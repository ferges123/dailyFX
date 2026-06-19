import { memo, useEffect, useState } from 'react';
import { getAuthToken } from '../api/client';

interface SecureImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  src: string;
}

const blobCache = new Map<string, string>();
const pendingFetches = new Map<string, Promise<string>>();

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

    // Check synchronous cache first
    const cached = blobCache.get(src);
    if (cached) {
      setBlobUrl(cached);
      setLoading(false);
      setError(false);
      return;
    }

    const token = getAuthToken();

    async function fetchImage() {
      try {
        setLoading(true);

        let promise = pendingFetches.get(src);
        if (!promise) {
          promise = (async () => {
            const headers: Record<string, string> = {};
            if (token) {
              headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(src, { headers });
            if (!response.ok) throw new Error('Failed to fetch image');

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            blobCache.set(src, url);
            pendingFetches.delete(src);
            return url;
          })();
          pendingFetches.set(src, promise);
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
