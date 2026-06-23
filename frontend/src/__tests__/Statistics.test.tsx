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
  { effect_id: 'duotone', title: 'Duotone', total_runs: 5, likes: 3, dislikes: 1 },
  { effect_id: 'ai_anime', title: 'Anime AI', total_runs: 10, likes: 8, dislikes: 2 },
  { effect_id: 'vignette', title: 'Vignette', total_runs: 2, likes: 1, dislikes: 0 },
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
    
    // Check tabs and their badges
    const standardTab = screen.getByRole('button', { name: /Standard/i });
    expect(standardTab).toHaveTextContent('Standard2'); // 2 standard effects: duotone, vignette

    const aiTab = screen.getByRole('button', { name: /AI/i });
    expect(aiTab).toHaveTextContent('AI1'); // 1 AI effect: ai_anime

    // Initially in Standard tab, should show standard effects, not AI ones
    expect(screen.getByText('Duotone')).toBeInTheDocument();
    expect(screen.getByText('Vignette')).toBeInTheDocument();
    expect(screen.queryByText('Anime AI')).not.toBeInTheDocument();

    // Click on AI tab
    fireEvent.click(screen.getByText('AI'));

    // Should now show AI effects, not standard ones
    expect(screen.getByText('Anime AI')).toBeInTheDocument();
    expect(screen.queryByText('Duotone')).not.toBeInTheDocument();
    expect(screen.queryByText('Vignette')).not.toBeInTheDocument();
  });
});
