import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useApprovals } from '../hooks/useApprovals';
import { wsClient } from '../services/websocket';
import { ApiService } from '../services/api';

vi.mock('../services/api', () => ({
  ApiService: {
    respondToApproval: vi.fn().mockResolvedValue({ status: 'success' }),
  },
}));

describe('useApprovals hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initializes without any pending approvals', () => {
    const { result } = renderHook(() => useApprovals());
    expect(result.current.hasPendingApproval).toBe(false);
    expect(result.current.pendingApproval).toBeNull();
    expect(result.current.remainingSeconds).toBe(30);
  });

  it('receives approval request from websocket and invokes onApprovalArrive', () => {
    const onArrive = vi.fn();
    const { result } = renderHook(() => useApprovals({ onApprovalArrive: onArrive, defaultCountdownSeconds: 30 }));

    act(() => {
      wsClient.emit('approval:request', {
        approval_id: 'app_test_123',
        skill_name: 'open_app',
        arguments: { app_name: 'notepad' },
        timeout_seconds: 30,
      });
    });

    expect(result.current.hasPendingApproval).toBe(true);
    expect(result.current.pendingApproval?.approvalId).toBe('app_test_123');
    expect(result.current.pendingApproval?.skillName).toBe('open_app');
    expect(onArrive).toHaveBeenCalledTimes(1);
    expect(onArrive).toHaveBeenCalledWith(
      expect.objectContaining({ approvalId: 'app_test_123', skillName: 'open_app' })
    );
  });

  it('approves on Enter key press', async () => {
    const { result } = renderHook(() => useApprovals());

    act(() => {
      wsClient.emit('approval:request', {
        approval_id: 'app_enter_123',
        skill_name: 'open_app',
      });
    });

    expect(result.current.hasPendingApproval).toBe(true);

    await act(async () => {
      const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true });
      window.dispatchEvent(event);
    });

    expect(ApiService.respondToApproval).toHaveBeenCalledWith('app_enter_123', 'approve');
    expect(result.current.hasPendingApproval).toBe(false);
  });

  it('denies on Escape key press', async () => {
    const { result } = renderHook(() => useApprovals());

    act(() => {
      wsClient.emit('approval:request', {
        approval_id: 'app_esc_123',
        skill_name: 'open_app',
      });
    });

    expect(result.current.hasPendingApproval).toBe(true);

    await act(async () => {
      const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true });
      window.dispatchEvent(event);
    });

    expect(ApiService.respondToApproval).toHaveBeenCalledWith('app_esc_123', 'deny');
    expect(result.current.hasPendingApproval).toBe(false);
  });

  it('supports session persistence approval', async () => {
    const { result } = renderHook(() => useApprovals());

    act(() => {
      wsClient.emit('approval:request', {
        approval_id: 'app_sess_123',
        skill_name: 'open_app',
      });
    });

    await act(async () => {
      await result.current.approve('session');
    });

    expect(ApiService.respondToApproval).toHaveBeenCalledWith('app_sess_123', 'approve');
    const stored = JSON.parse(sessionStorage.getItem('niko_session_allowed_skills') || '[]');
    expect(stored).toContain('open_app');
  });
});
