import { useEffect, useState } from 'react';
import { getAuthToken } from '../api/client';

interface SecureImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  src: string;
}

export function SecureImage({ src, ...props }: SecureImageProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    if (!src) return;

    let isMounted = true;
    let createdUrl: string | null = null;
    const token = getAuthToken();

    async function fetchImage() {
      try {
        setLoading(true);
        const headers: Record<string, string> = {};
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(src, { headers });
        if (!response.ok) throw new Error('Failed to fetch image');

        const blob = await response.blob();
        if (isMounted) {
          const url = URL.createObjectURL(blob);
          createdUrl = url;
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
      if (createdUrl) {
        URL.revokeObjectURL(createdUrl);
      }
    };
  }, [src]);

  if (error) {
    return (
      <div className={`${props.className} flex items-center justify-center bg-stone-100 text-stone-400`}>
        <span className="text-xs">Failed to load</span>
      </div>
    );
  }

  if (loading || !blobUrl) {
    return (
      <div className={`${props.className} animate-pulse rounded-[inherit] bg-stone-100/90`} />
    );
  }

  return <img src={blobUrl} {...props} />;
}
