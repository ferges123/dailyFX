import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { StudioPage } from '../pages/StudioPage';
import * as client from '../api/client';

vi.mock('../api/client', async () => {
  return {
    getStudioModules: vi.fn(async () => [
      {
        name: 'pencil_sketch',
        label: 'Pencil Sketch',
        description: 'Sketch effect',
        display_group: 'Artistic',
        default_weight: 1,
        default_config: {},
        config_schema: [],
      },
      {
        name: 'ai_anime',
        label: 'AI Anime',
        description: 'AI style',
        display_group: 'Illustration',
        default_weight: 1,
        default_config: {},
        config_schema: [],
      },
    ]),
    createStudioPreview: vi.fn(),
    createStudioPreviewFromImmich: vi.fn(),
    getImmichAlbums: vi.fn(async () => ({
      items: [
        {
          id: 'immich-album-123',
          album_name: 'Summer 2026',
          asset_count: 5,
          thumbnail_asset_id: 'immich-asset-123',
        },
      ],
      total: 1,
      count: 1,
      pages: 1,
      current_page: 1,
    })),
    getImmichAssets: vi.fn(async () => ({
      items: [
        {
          id: 'immich-asset-123',
          original_file_name: 'sunset.jpg',
          created_at: '2026-06-26T12:00:00Z',
          updated_at: null,
          mime_type: 'image/jpeg',
          asset_type: 'IMAGE',
          people: [],
        },
      ],
      total: 1,
      count: 1,
      next_page: null,
    })),
    getImmichAssetThumbnailUrl: vi.fn(
      (id: string) => `/api/immich/assets/${id}/thumbnail`,
    ),
    getApiUrl: (path: string) => path,
  };
});

// Mock URL.createObjectURL and URL.revokeObjectURL
const createObjectURLMock = vi.fn(() => 'mock-object-url');
const revokeObjectURLMock = vi.fn();
beforeEach(() => {
  window.URL.createObjectURL = createObjectURLMock;
  window.URL.revokeObjectURL = revokeObjectURLMock;
});
afterEach(() => {
  vi.clearAllMocks();
});

function renderStudio() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <StudioPage />
    </QueryClientProvider>,
  );
}

describe('StudioPage', () => {
  it('renders upload and AI-capable effect controls', async () => {
    renderStudio();

    expect(await screen.findByText('Studio')).toBeInTheDocument();
    expect(await screen.findByText('Pencil Sketch')).toBeInTheDocument();
    expect(await screen.findByText('AI Anime')).toBeInTheDocument();
    expect(screen.getByLabelText('AI Vision metadata')).toBeInTheDocument();
    expect(screen.getByLabelText('AI prompt enrichment')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /create preview/i }),
    ).toBeDisabled();
  });

  it('renders source image preview and handles drag and drop', async () => {
    renderStudio();
    const dropzone = await screen.findByText('Choose image');

    // Simulate drag over
    fireEvent.dragOver(dropzone);

    // Simulate drop
    const file = new File(['dummy content'], 'test-image.jpg', {
      type: 'image/jpeg',
    });
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file],
      },
    });

    // Expect the preview image to render using the mocked object URL
    const previewImg = await screen.findByAltText('Source preview');
    expect(previewImg).toBeInTheDocument();
    expect(previewImg).toHaveAttribute('src', 'mock-object-url');
    expect(screen.getByText('test-image.jpg')).toBeInTheDocument();
    expect(createObjectURLMock).toHaveBeenCalledWith(file);
  });

  it('renders dropdown options grouped by display category', async () => {
    renderStudio();
    const dropdown = await screen.findByRole('combobox');
    await screen.findByText('Pencil Sketch');
    expect(
      dropdown.querySelector('optgroup[label="Artistic"]'),
    ).toBeInTheDocument();
    expect(
      dropdown.querySelector('optgroup[label="Illustration"]'),
    ).toBeInTheDocument();
  });

  it('submits preview for local file upload', async () => {
    renderStudio();
    const dropzone = await screen.findByText('Choose image');

    const file = new File(['dummy content'], 'test-image.jpg', {
      type: 'image/jpeg',
    });
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file],
      },
    });

    const createBtn = screen.getByRole('button', { name: /create preview/i });
    expect(createBtn).not.toBeDisabled();

    fireEvent.click(createBtn);

    await waitFor(() => {
      expect(client.createStudioPreview).toHaveBeenCalledWith(
        file,
        'ai_anime',
        {},
        { aiVisionEnabled: false, promptEnrichmentEnabled: false },
      );
    });
  });

  it('opens Immich browser modal and selects an asset', async () => {
    renderStudio();

    const browseBtn = await screen.findByRole('button', {
      name: /browse immich/i,
    });
    expect(browseBtn).toBeInTheDocument();

    // Click browse button to open modal
    fireEvent.click(browseBtn);

    // Modal header should be visible with Album view instructions
    expect(
      await screen.findByText('Select an album to browse its photos'),
    ).toBeInTheDocument();

    // Find the album Summer 2026 and click it
    const albumCard = await screen.findByText('Summer 2026');
    expect(albumCard).toBeInTheDocument();
    fireEvent.click(albumCard);

    // After entering the album, the asset thumbnail should render
    const assetThumb = await screen.findByAltText('sunset.jpg');
    expect(assetThumb).toBeInTheDocument();
    expect(assetThumb).toHaveAttribute(
      'src',
      '/api/immich/assets/immich-asset-123/thumbnail',
    );

    // Click the asset thumbnail to select it
    fireEvent.click(assetThumb);

    // Modal should close, and the selected asset info should be in the upload zone
    expect(
      screen.queryByText('Select an album to browse its photos'),
    ).not.toBeInTheDocument();
    expect(await screen.findByText('sunset.jpg')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Immich Photo (Click or drag to change to local upload)',
      ),
    ).toBeInTheDocument();

    // Create preview button should be enabled
    const createBtn = screen.getByRole('button', { name: /create preview/i });
    expect(createBtn).not.toBeDisabled();

    // Click Create preview
    fireEvent.click(createBtn);

    await waitFor(() => {
      expect(client.createStudioPreviewFromImmich).toHaveBeenCalledWith(
        'immich-asset-123',
        'ai_anime',
        {},
        { aiVisionEnabled: false, promptEnrichmentEnabled: false },
      );
    });
  });
});
