import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { ApprovalModal } from '../components/ApprovalModal';
import type { ApprovalRequestItem } from '../types';

describe('ApprovalModal Component & Flow', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  const mockRequest: ApprovalRequestItem = {
    id: 'appr-123',
    requestId: 'req-99',
    toolName: 'run_subprocess',
    arguments: { command: 'dir', cwd: 'E:\\' },
    riskLevel: 'high',
    reason: 'Execute local shell command',
    status: 'pending',
    createdAt: new Date().toISOString(),
    timeoutSeconds: 30,
  };

  it('renders approval request details, risk badge, and arguments', () => {
    render(
      <ApprovalModal
        request={mockRequest}
        onApprove={vi.fn()}
        onReject={vi.fn()}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText('PERMISSION CONFIRMATION REQUIRED')).toBeInTheDocument();
    expect(screen.getByText('run_subprocess')).toBeInTheDocument();
    expect(screen.getByText(/high risk/i)).toBeInTheDocument();
    expect(screen.getByText(/"command": "dir"/)).toBeInTheDocument();
  });

  it('triggers onApprove callback when user clicks Approve & Execute', () => {
    const approveSpy = vi.fn();
    render(
      <ApprovalModal
        request={mockRequest}
        onApprove={approveSpy}
        onReject={vi.fn()}
        onClose={vi.fn()}
      />
    );

    const approveBtn = screen.getByRole('button', { name: /Approve & Execute/i });
    fireEvent.click(approveBtn);

    expect(approveSpy).toHaveBeenCalledWith('appr-123');
  });

  it('triggers onReject callback when user clicks Deny Execution', () => {
    const rejectSpy = vi.fn();
    render(
      <ApprovalModal
        request={mockRequest}
        onApprove={vi.fn()}
        onReject={rejectSpy}
        onClose={vi.fn()}
      />
    );

    const denyBtn = screen.getByRole('button', { name: /Deny Execution/i });
    fireEvent.click(denyBtn);

    expect(rejectSpy).toHaveBeenCalledWith('appr-123');
  });

  it('automatically triggers onReject when the countdown expires', () => {
    const rejectSpy = vi.fn();
    render(
      <ApprovalModal
        request={{ ...mockRequest, timeoutSeconds: 3 }}
        onApprove={vi.fn()}
        onReject={rejectSpy}
        onClose={vi.fn()}
      />
    );

    // Fast-forward 3 seconds
    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(rejectSpy).toHaveBeenCalledWith('appr-123');
  });
});
