import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.unmock('../components/SecureImage');

const makeResponse = () =>
  ({
    ok: true,
    blob: () => Promise.resolve(new Blob(['image'], { type: 'image/png' })),
  }) as Response;

describe('SecureImage', () => {
  let token: string | null;
  let objectUrlCount: number;

  beforeEach(() => {
    vi.resetModules();
    token = 'token-a';
    objectUrlCount = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(makeResponse())),
    );
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation((key) =>
      key === 'dailyfx_token' ? token : null,
    );
    vi.spyOn(URL, 'createObjectURL').mockImplementation(() => {
      objectUrlCount += 1;
      return `blob:test-${objectUrlCount}`;
    });
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  async function loadSecureImage() {
    return import('../components/SecureImage');
  }

  it('retries a source after a failed fetch instead of reusing the rejected pending request', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, blob: vi.fn() })
      .mockResolvedValueOnce(makeResponse());
    vi.stubGlobal('fetch', fetchMock);
    const { SecureImage } = await loadSecureImage();

    const first = render(<SecureImage src="/api/image-a" alt="first" />);
    await screen.findByText('Failed to load');
    first.unmount();

    render(<SecureImage src="/api/image-a" alt="second" />);

    await waitFor(() =>
      expect(screen.getByAltText('second')).toHaveAttribute(
        'src',
        'blob:test-1',
      ),
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('evicts old blob URLs and revokes them when the cache limit is exceeded', async () => {
    const { SecureImage } = await loadSecureImage();

    for (let index = 0; index < 105; index += 1) {
      const view = render(
        <SecureImage src={`/api/image-${index}`} alt={`image-${index}`} />,
      );
      await waitFor(() =>
        expect(screen.getByAltText(`image-${index}`)).toHaveAttribute(
          'src',
          `blob:test-${index + 1}`,
        ),
      );
      view.unmount();
    }

    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(5);
    expect(URL.revokeObjectURL).toHaveBeenNthCalledWith(1, 'blob:test-1');
    expect(URL.revokeObjectURL).toHaveBeenNthCalledWith(5, 'blob:test-5');
  });

  it('refreshes recency on cache hit so recently read entries survive eviction', async () => {
    const { SecureImage } = await loadSecureImage();

    // Fill 100 items: image-0 to image-99
    for (let index = 0; index < 100; index += 1) {
      const view = render(
        <SecureImage src={`/api/lru-${index}`} alt={`lru-${index}`} />,
      );
      await waitFor(() =>
        expect(screen.getByAltText(`lru-${index}`)).toHaveAttribute(
          'src',
          `blob:test-${index + 1}`,
        ),
      );
      view.unmount();
    }

    // Access image-0 again (cache hit - should refresh recency)
    const hitView = render(<SecureImage src="/api/lru-0" alt="lru-0-hit" />);
    await waitFor(() =>
      expect(screen.getByAltText('lru-0-hit')).toHaveAttribute(
        'src',
        'blob:test-1',
      ),
    );
    hitView.unmount();

    // Now insert item 101 (lru-100), triggering 1 eviction.
    // Since lru-0 was recently accessed, lru-1 (blob:test-2) should be evicted first.
    const newView = render(
      <SecureImage src="/api/lru-100" alt="lru-100" />,
    );
    await waitFor(() =>
      expect(screen.getByAltText('lru-100')).toHaveAttribute(
        'src',
        'blob:test-101',
      ),
    );
    newView.unmount();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test-2');
    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith('blob:test-1');
  });

  it('does not reuse a cached blob URL after the auth token changes', async () => {
    const { SecureImage } = await loadSecureImage();

    const first = render(<SecureImage src="/api/private-image" alt="first" />);
    await waitFor(() =>
      expect(screen.getByAltText('first')).toHaveAttribute(
        'src',
        'blob:test-1',
      ),
    );
    first.unmount();

    token = 'token-b';
    render(<SecureImage src="/api/private-image" alt="second" />);

    await waitFor(() =>
      expect(screen.getByAltText('second')).toHaveAttribute(
        'src',
        'blob:test-2',
      ),
    );
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  describe('lazy loading with IntersectionObserver', () => {
    interface MockObserver {
      options?: IntersectionObserverInit;
      triggerIntersect: (isIntersecting?: boolean) => void;
      disconnect: ReturnType<typeof vi.fn>;
    }

    let mockObserverInstances: MockObserver[] = [];

    beforeEach(() => {
      mockObserverInstances = [];
      class MockIntersectionObserver {
        callback: IntersectionObserverCallback;
        options?: IntersectionObserverInit;
        elements: Element[] = [];
        disconnect = vi.fn(() => {
          this.elements = [];
        });
        observe = vi.fn((el: Element) => {
          this.elements.push(el);
        });
        unobserve = vi.fn((el: Element) => {
          this.elements = this.elements.filter((e) => e !== el);
        });
        takeRecords = vi.fn(() => []);
        root = null;
        rootMargin = '0px';
        thresholds = [];

        constructor(
          callback: IntersectionObserverCallback,
          options?: IntersectionObserverInit,
        ) {
          this.callback = callback;
          this.options = options;
          mockObserverInstances.push(this);
        }

        triggerIntersect(isIntersecting = true) {
          this.callback(
            this.elements.map((target) => ({
              isIntersecting,
              target,
              boundingClientRect: target.getBoundingClientRect(),
              intersectionRatio: isIntersecting ? 1 : 0,
              intersectionRect: target.getBoundingClientRect(),
              rootBounds: null,
              time: Date.now(),
            })),
            this as unknown as IntersectionObserver,
          );
        }
      }

      vi.stubGlobal('IntersectionObserver', MockIntersectionObserver);
    });

    it('renders placeholder without calling fetch when loading="lazy"', async () => {
      const fetchMock = vi.fn(() => Promise.resolve(makeResponse()));
      vi.stubGlobal('fetch', fetchMock);
      const { SecureImage } = await loadSecureImage();

      render(<SecureImage src="/api/lazy-1" alt="lazy image" loading="lazy" />);

      expect(fetchMock).not.toHaveBeenCalled();
      expect(screen.queryByAltText('lazy image')).not.toBeInTheDocument();
    });

    it('calls fetch after the observer reports intersection', async () => {
      const fetchMock = vi.fn(() => Promise.resolve(makeResponse()));
      vi.stubGlobal('fetch', fetchMock);
      const { SecureImage } = await loadSecureImage();

      render(<SecureImage src="/api/lazy-2" alt="lazy image 2" loading="lazy" />);

      expect(fetchMock).not.toHaveBeenCalled();
      expect(mockObserverInstances).toHaveLength(1);
      expect(mockObserverInstances[0]?.options?.rootMargin).toBe('300px');

      act(() => {
        mockObserverInstances[0].triggerIntersect(true);
      });

      await waitFor(() =>
        expect(screen.getByAltText('lazy image 2')).toHaveAttribute(
          'src',
          'blob:test-1',
        ),
      );
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it('eager or default loading calls fetch immediately', async () => {
      const fetchMock = vi.fn(() => Promise.resolve(makeResponse()));
      vi.stubGlobal('fetch', fetchMock);
      const { SecureImage } = await loadSecureImage();

      render(<SecureImage src="/api/eager-1" alt="eager image" loading="eager" />);

      await waitFor(() =>
        expect(screen.getByAltText('eager image')).toHaveAttribute(
          'src',
          'blob:test-1',
        ),
      );
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it('multiple intersection notifications trigger at most one request', async () => {
      const fetchMock = vi.fn(() => Promise.resolve(makeResponse()));
      vi.stubGlobal('fetch', fetchMock);
      const { SecureImage } = await loadSecureImage();

      render(<SecureImage src="/api/lazy-multi" alt="lazy multi" loading="lazy" />);

      act(() => {
        mockObserverInstances[0].triggerIntersect(true);
        mockObserverInstances[0].triggerIntersect(true);
      });

      await waitFor(() =>
        expect(screen.getByAltText('lazy multi')).toHaveAttribute(
          'src',
          'blob:test-1',
        ),
      );
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it('disconnects the observer on unmount', async () => {
      const { SecureImage } = await loadSecureImage();

      const view = render(
        <SecureImage src="/api/lazy-unmount" alt="unmount" loading="lazy" />,
      );

      expect(mockObserverInstances).toHaveLength(1);
      const observer = mockObserverInstances[0];

      view.unmount();
      expect(observer.disconnect).toHaveBeenCalled();
    });

    it('includes decoding="async" by default unless overridden', async () => {
      const { SecureImage } = await loadSecureImage();

      const { unmount } = render(
        <SecureImage src="/api/decoding-default" alt="decoding default" />,
      );

      await waitFor(() => {
        const img = screen.getByAltText('decoding default');
        expect(img).toHaveAttribute('decoding', 'async');
      });
      unmount();

      render(
        <SecureImage
          src="/api/decoding-override"
          alt="decoding override"
          decoding="sync"
        />,
      );

      await waitFor(() => {
        const img = screen.getByAltText('decoding override');
        expect(img).toHaveAttribute('decoding', 'sync');
      });
    });
  });
});

