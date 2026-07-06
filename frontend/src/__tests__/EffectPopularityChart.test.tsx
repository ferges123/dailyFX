import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { EffectPopularityChart } from '../pages/Statistics/EffectPopularityChart';
import type * as client from '../api/client';

// Mock Recharts to render a simple HTML representation of the chart data
vi.mock('recharts', () => {
  return {
    ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
    BarChart: ({ data, children }: any) => (
      <div data-testid="bar-chart">
        {data?.map((item: any) => (
          <div key={item.effect_id} data-testid="chart-item">
            {item.title}: {item.total_runs}
          </div>
        ))}
        {children}
      </div>
    ),
    Bar: ({ children }: any) => <div data-testid="bar">{children}</div>,
    LabelList: () => <div data-testid="labellist" />,
    XAxis: () => <div data-testid="xaxis" />,
    YAxis: () => <div data-testid="yaxis" />,
    CartesianGrid: () => <div data-testid="cartesiangrid" />,
    Tooltip: () => <div data-testid="tooltip" />,
  };
});

const mockStats: client.EffectStats[] = [
  {
    effect_id: 'cyanotype',
    title: 'Cyanotype',
    total_runs: 5,
    likes: 3,
    dislikes: 1,
    rating_count: 4,
    unrated_count: 1,
    like_rate: 75,
    quality_score: 75,
    quality_label: 'good',
    pending_review_runs: 0,
    uploaded_runs: 4,
    rejected_runs: 0,
    failed_runs: 1,
    last_run_at: '2026-01-03T09:45:00Z',
  },
  {
    effect_id: 'ai_anime',
    title: 'AI Anime',
    total_runs: 12,
    likes: 8,
    dislikes: 2,
    rating_count: 10,
    unrated_count: 2,
    like_rate: 80,
    quality_score: 80,
    quality_label: 'excellent',
    pending_review_runs: 0,
    uploaded_runs: 10,
    rejected_runs: 0,
    failed_runs: 2,
    last_run_at: '2026-01-04T11:00:00Z',
  },
  {
    effect_id: 'glitch',
    title: 'Glitch',
    total_runs: 0,
    likes: 0,
    dislikes: 0,
    rating_count: 0,
    unrated_count: 0,
    like_rate: null,
    quality_score: 0,
    quality_label: 'insufficient_data',
    pending_review_runs: 0,
    uploaded_runs: 0,
    rejected_runs: 0,
    failed_runs: 0,
    last_run_at: null,
  }
];

describe('EffectPopularityChart', () => {
  it('renders standard effects with total_runs > 0 and hides AI effects', () => {
    render(<EffectPopularityChart stats={mockStats} activeTab="standard" />);
    expect(screen.getByText('Cyanotype: 5')).toBeInTheDocument();
    expect(screen.queryByText(/AI Anime/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Glitch/)).not.toBeInTheDocument();
  });

  it('renders AI effects with total_runs > 0 and hides standard effects', () => {
    render(<EffectPopularityChart stats={mockStats} activeTab="ai" />);
    expect(screen.getByText('AI Anime: 12')).toBeInTheDocument();
    expect(screen.queryByText(/Cyanotype/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Glitch/)).not.toBeInTheDocument();
  });

  it('returns null if there are no effects with runs', () => {
    const { container } = render(<EffectPopularityChart stats={[]} activeTab="standard" />);
    expect(container.firstChild).toBeNull();
  });
});
