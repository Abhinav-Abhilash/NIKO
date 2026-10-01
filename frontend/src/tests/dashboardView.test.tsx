import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DashboardView } from '../components/DashboardView';
import { ApiService } from '../services/api';
import type { SystemMetrics } from '../types';

vi.mock('../services/api', () => ({
  ApiService: {
    getModelsStatus: vi.fn().mockResolvedValue({
      discovered: {
        gemini: { primary_model: 'gemini-2.0-flash' },
        groq: { primary_model: 'llama-3.3-70b-versatile' },
      },
      quotas: {
        gemini: { cooling_down: false },
        groq: { cooling_down: true, remaining_seconds: 45 },
      },
    }),
    getSchedules: vi.fn().mockResolvedValue([
      {
        id: 'task-1',
        name: 'Morning Diagnostics',
        task_type: 'cron',
        action_type: 'skill',
        action_payload: {},
        cron_expression: '0 8 * * *',
        status: 'active',
      },
    ]),
    getHealth: vi.fn().mockResolvedValue({
      status: 'healthy',
      uptime_seconds: 7200,
    }),
    toggleSchedule: vi.fn().mockResolvedValue(undefined),
    deleteSchedule: vi.fn().mockResolvedValue(undefined),
  },
}));

const mockMetrics: SystemMetrics = {
  coreOnline: true,
  cpuPercent: 24.5,
  ramUsageGb: 8.2,
  ramTotalGb: 32,
  pingMs: 12,
  activeSocket: 'IPC:///ws?hub',
  contextUsed: 3500,
  contextMax: 128000,
};

describe('DashboardView Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders hardware metrics and live telemetry widgets', async () => {
    const onRefresh = vi.fn();
    render(<DashboardView metrics={mockMetrics} onRefresh={onRefresh} />);

    expect(screen.getByText(/LIVE TELEMETRY & SYSTEM BENCHMARKS/i)).toBeInTheDocument();
    expect(screen.getByText('24.5%')).toBeInTheDocument();
    expect(screen.getByText('12 ms')).toBeInTheDocument();
  });

  it('renders live models status and cooldown warnings', async () => {
    render(<DashboardView metrics={mockMetrics} onRefresh={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText(/Model: gemini-2.0-flash/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Reset in: 45s/i)).toBeInTheDocument();
  });

  it('renders task queue and handles toggle and delete actions', async () => {
    render(<DashboardView metrics={mockMetrics} onRefresh={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Morning Diagnostics')).toBeInTheDocument();
    });

    const pauseBtn = screen.getByRole('button', { name: /Pause/i });
    await waitFor(async () => {
      fireEvent.click(pauseBtn);
    });
    expect(ApiService.toggleSchedule).toHaveBeenCalledWith('task-1', 'paused');

    const deleteBtn = screen.getByRole('button', { name: /Delete/i });
    await waitFor(async () => {
      fireEvent.click(deleteBtn);
    });
    expect(ApiService.deleteSchedule).toHaveBeenCalledWith('task-1');
  });
});

