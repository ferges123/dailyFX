import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { StatisticsPage } from '../pages/Statistics';
import * as client from '../api/client';

vi.mock('../api/client', () => ({
  getEffectStats: vi.fn(),
}));

const mockStats: client.EffectStats[] = [
  {
    effect_id: 'duotone',
    title: 'Duotone',
    total_runs: 8,
    likes: 4,
    dislikes: 1,
    rating_count: 5,
    unrated_count: 3,
    like_rate: 80,
    quality_score: 80,
    quality_label: 'excellent',
    pending_review_runs: 2,
    uploaded_runs: 5,
    rejected_runs: 1,
    failed_runs: 0,
    last_run_at: '2026-01-03T09:45:00Z',
  },
  {
    effect_id: 'ai_anime',
    title: 'Anime AI',
    total_runs: 10,
    likes: 2,
    dislikes: 3,
    rating_count: 5,
    unrated_count: 5,
    like_rate: 40,
    quality_score: 40,
    quality_label: 'mixed',
    pending_review_runs: 1,
    uploaded_runs: 6,
    rejected_runs: 3,
    failed_runs: 0,
    last_run_at: '2026-01-04T11:00:00Z',
  },
  {
    effect_id: 'vignette',
    title: 'Vignette',
    total_runs: 2,
    likes: 1,
    dislikes: 0,
    rating_count: 1,
    unrated_count: 1,
    like_rate: 100,
    quality_score: 0,
    quality_label: 'insufficient_data',
    pending_review_runs: 1,
    uploaded_runs: 1,
    rejected_runs: 0,
    failed_runs: 0,
    last_run_at: null,
  },
];

function renderPage(initialRoute = '/statistics/standard') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <Routes>
          <Route path="/statistics/:tab" element={<StatisticsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('StatisticsPage Tabs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(client.getEffectStats).mockResolvedValue(mockStats);
  });

  it('renders standard and AI tabs and filters correctly', async () => {
    renderPage();
    
    // Check page title
    expect(await screen.findByText('Effect Statistics')).toBeInTheDocument();

    expect(screen.getByText('Total runs')).toBeInTheDocument();
    expect(screen.getByText('11 rated')).toBeInTheDocument();
    expect(screen.getByText('Best rated')).toBeInTheDocument();
    expect(screen.getAllByText('Duotone')[0]).toBeInTheDocument();
    expect(screen.getByText('Needs attention')).toBeInTheDocument();
    
    // Check tabs and their badges
    const standardTab = screen.getByRole('button', { name: /Standard/i });
    expect(standardTab).toHaveTextContent('Standard2'); // 2 standard effects: duotone, vignette

    const aiTab = screen.getByRole('button', { name: /AI/i });
    expect(aiTab).toHaveTextContent('AI1'); // 1 AI effect: ai_anime

    // Initially in Standard tab, should show standard effects, not AI ones
    expect(screen.getByRole('link', { name: 'Duotone' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Vignette' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Anime AI' })).not.toBeInTheDocument();

    expect(screen.getByText('Excellent')).toBeInTheDocument();
    expect(screen.getAllByText('80% liked')[0]).toBeInTheDocument();
    expect(screen.getByText('3 unrated')).toBeInTheDocument();
    expect(screen.getByText('Not enough ratings')).toBeInTheDocument();

    // Click on AI tab
    fireEvent.click(screen.getByText('AI'));

    // Should now show AI effects, not standard ones
    expect(screen.getByRole('link', { name: 'Anime AI' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Duotone' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Vignette' })).not.toBeInTheDocument();

    expect(screen.getByText('Mixed')).toBeInTheDocument();
    expect(screen.getByText('40% liked')).toBeInTheDocument();
    expect(screen.getByText('5 unrated')).toBeInTheDocument();
  });
});
