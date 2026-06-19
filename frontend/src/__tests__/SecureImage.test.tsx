import { render, screen, waitFor } from '@testing-library/react';
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
});
