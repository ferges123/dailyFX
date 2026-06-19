import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { AIEffectsPage } from '../pages/AIEffects';
import * as client from '../api/client';

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    getAIEffects: vi.fn(),
    createAIEffect: vi.fn(),
    updateAIEffect: vi.fn(),
    deleteAIEffect: vi.fn(),
    duplicateAIEffect: vi.fn(),
    resetAIEffect: vi.fn(),
    exportAIEffects: vi.fn(),
    importAIEffects: vi.fn(),
  };
});

const mockEffects: client.AIEffect[] = [
  {
    id: 'portrait_classic',
    title: 'Portrait Classic',
    description: 'Classic portrait enhancement.',
    display_group: 'Portrait',
    positive_prompt: 'enhancing portrait',
    negative_prompt: 'blurry',
    custom_prompt_placeholder: null,
    enabled: true,
    hidden: false,
    source: 'builtin',
    builtin_hash: 'hash1',
    latest_builtin_hash: 'hash1',
    user_modified_at: null,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
  },
  {
    id: 'illustration_comic',
    title: 'Comic Illustration',
    description: 'Turn image into a comic style.',
    display_group: 'Illustration',
    positive_prompt: 'comic book style',
    negative_prompt: 'realistic',
    custom_prompt_placeholder: 'superhero style',
    enabled: true,
    hidden: false,
    source: 'custom',
    builtin_hash: null,
    latest_builtin_hash: null,
    user_modified_at: null,
    created_at: '2026-06-02T00:00:00Z',
    updated_at: '2026-06-02T00:00:00Z',
  },
];

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AIEffectsPage />
      </BrowserRouter>
    </QueryClientProvider>,
  );
}

describe('AIEffectsPage CRUD and Modals', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(client.getAIEffects).mockResolvedValue(mockEffects);
  });

  it('renders standard layout and filter options', async () => {
    renderPage();
    expect(await screen.findByText('Portrait Classic')).toBeInTheDocument();
    expect(screen.getByText('Comic Illustration')).toBeInTheDocument();
    expect(
      screen.getByRole('combobox', { name: 'AI effects group filter' }),
    ).toBeInTheDocument();
  });

  it('handles creating a custom AI effect and validation issues', async () => {
    vi.mocked(client.createAIEffect).mockResolvedValue({
      id: 'custom_retro',
      title: 'Retro Style',
      description: 'Retro look',
      display_group: 'Artistic',
      positive_prompt: 'vintage colors',
      negative_prompt: 'modern',
      custom_prompt_placeholder: null,
      enabled: true,
      hidden: false,
      source: 'custom',
      builtin_hash: null,
      latest_builtin_hash: null,
      user_modified_at: null,
      created_at: '2026-06-18T00:00:00Z',
      updated_at: '2026-06-18T00:00:00Z',
    });

    renderPage();

    const newBtn = await screen.findByRole('button', { name: /New effect/i });
    fireEvent.click(newBtn);

    // Save button starts disabled due to validation requirements
    const saveBtn = screen.getByRole('button', { name: /Save/i });
    expect(saveBtn).toBeDisabled();

    // Fill form
    fireEvent.change(screen.getByLabelText(/ID/i, { selector: 'input' }), {
      target: { value: 'custom_retro' },
    });
    fireEvent.change(screen.getByLabelText(/Title/i, { selector: 'input' }), {
      target: { value: 'Retro Style' },
    });
    fireEvent.change(
      screen.getByLabelText(/Positive prompt/i, { selector: 'textarea' }),
      {
        target: { value: 'vintage colors' },
      },
    );
    fireEvent.change(
      screen.getByLabelText(/Description/i, { selector: 'input' }),
      {
        target: { value: 'Retro look' },
      },
    );
    fireEvent.change(screen.getByLabelText(/Group/i, { selector: 'input' }), {
      target: { value: 'Artistic' },
    });

    expect(saveBtn).not.toBeDisabled();
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(client.createAIEffect).toHaveBeenCalledWith({
        id: 'custom_retro',
        title: 'Retro Style',
        description: 'Retro look',
        display_group: 'Artistic',
        positive_prompt: 'vintage colors',
        negative_prompt: null,
        custom_prompt_placeholder: null,
        enabled: true,
      });
    });
  });

  it('handles editing an AI effect', async () => {
    vi.mocked(client.updateAIEffect).mockResolvedValue({
      ...mockEffects[1],
      title: 'Comic Style Updated',
    });

    renderPage();

    const editBtn = await screen.findByRole('button', {
      name: 'Edit Comic Illustration',
    });
    fireEvent.click(editBtn);

    const titleInput = screen.getByLabelText(/Title/i, { selector: 'input' });
    fireEvent.change(titleInput, { target: { value: 'Comic Style Updated' } });

    const saveBtn = screen.getByRole('button', { name: /Save/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(client.updateAIEffect).toHaveBeenCalledWith(
        'illustration_comic',
        expect.objectContaining({
          title: 'Comic Style Updated',
        }),
      );
    });
  });

  it('triggers duplication with modal confirmation', async () => {
    vi.mocked(client.duplicateAIEffect).mockResolvedValue({
      ...mockEffects[1],
      id: 'illustration_comic_copy',
      title: 'Comic Illustration (Copy)',
    });

    renderPage();

    const menuBtn = await screen.findByRole('button', {
      name: 'More actions for Comic Illustration',
    });
    fireEvent.click(menuBtn);

    const dupBtn = screen.getByRole('button', {
      name: 'Duplicate Comic Illustration',
    });
    fireEvent.click(dupBtn);

    // Verify modal is open
    expect(screen.getByText('Duplicate AI Effect')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Are you sure you want to duplicate "Comic Illustration"?',
      ),
    ).toBeInTheDocument();

    const confirmBtn = screen.getByRole('button', { name: 'Duplicate' });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(client.duplicateAIEffect).toHaveBeenCalledWith(
        'illustration_comic',
      );
    });
  });

  it('triggers reset with modal warning for built-in effects', async () => {
    vi.mocked(client.resetAIEffect).mockResolvedValue(mockEffects[0]);

    renderPage();

    const menuBtn = await screen.findByRole('button', {
      name: 'More actions for Portrait Classic',
    });
    fireEvent.click(menuBtn);

    const resetBtn = screen.getByRole('button', {
      name: 'Reset Portrait Classic',
    });
    fireEvent.click(resetBtn);

    // Verify Warning Modal
    expect(screen.getByText('Reset AI Effect')).toBeInTheDocument();

    const confirmBtn = screen.getByRole('button', { name: 'Reset' });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(client.resetAIEffect).toHaveBeenCalledWith('portrait_classic');
    });
  });

  it('triggers delete/disable with modal warning and cancels it', async () => {
    renderPage();

    const menuBtn = await screen.findByRole('button', {
      name: 'More actions for Comic Illustration',
    });
    fireEvent.click(menuBtn);

    const deleteBtn = screen.getByRole('button', {
      name: 'Delete Comic Illustration',
    });
    fireEvent.click(deleteBtn);

    // Verify Modal
    expect(screen.getByText('Delete AI Effect')).toBeInTheDocument();

    const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
    fireEvent.click(cancelBtn);

    // Verify delete was not called and modal is closed
    expect(client.deleteAIEffect).not.toHaveBeenCalled();
    expect(screen.queryByText('Delete AI Effect')).not.toBeInTheDocument();
  });
});
