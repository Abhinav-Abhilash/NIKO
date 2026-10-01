import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { PlaceholderOverlay } from '../components/PlaceholderOverlay';
import { wsClient } from '../services/websocket';
import { ApiService } from '../services/api';

vi.mock('../services/api', () => ({
  ApiService: {
    respondToApproval: vi.fn().mockResolvedValue({ status: 'success' }),
  },
}));

describe('PlaceholderOverlay component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the unstyled input and allows sending message', () => {
    const sendChatSpy = vi.spyOn(wsClient, 'sendChat').mockImplementation(() => {});
    render(<PlaceholderOverlay />);

    const input = screen.getByPlaceholderText(/Ask NIKO/i);
    const submitBtn = screen.getByRole('button', { name: /Send/i });

    fireEvent.change(input, { target: { value: 'what time is it and how is my CPU' } });
    fireEvent.click(submitBtn);

    expect(sendChatSpy).toHaveBeenCalledWith(
      expect.stringContaining('req_'),
      'what time is it and how is my CPU',
      undefined,
      undefined,
      undefined
    );
  });

  it('renders approval dialog and triggers approve on Enter or button click', async () => {
    render(<PlaceholderOverlay />);

    act(() => {
      wsClient.emit('approval:request', {
        approval_id: 'app_ph_123',
        skill_name: 'open_app',
        arguments: { app_name: 'notepad' },
        timeout_seconds: 30,
      });
    });

    expect(screen.getByText(/CONFIRMATION REQUIRED/i)).toBeInTheDocument();
    expect(screen.getByText(/open_app/i)).toBeInTheDocument();

    const approveBtn = screen.getByRole('button', { name: /Approve \(Enter\)/i });
    await act(async () => {
      fireEvent.click(approveBtn);
    });

    expect(ApiService.respondToApproval).toHaveBeenCalledWith('app_ph_123', 'approve');
  });

  it('allows denying approval request via button', async () => {
    render(<PlaceholderOverlay />);

    act(() => {
      wsClient.emit('approval:request', {
        approval_id: 'app_deny_456',
        skill_name: 'open_app',
        arguments: { app_name: 'calc' },
      });
    });

    const denyBtn = screen.getByRole('button', { name: /Deny \(Esc\)/i });
    await act(async () => {
      fireEvent.click(denyBtn);
    });

    expect(ApiService.respondToApproval).toHaveBeenCalledWith('app_deny_456', 'deny');
  });

  it('toggles between compact and expanded HUD mode', () => {
    render(<PlaceholderOverlay />);
    const toggleBtn = screen.getByRole('button', { name: /Expand/i });
    expect(toggleBtn).toBeInTheDocument();

    fireEvent.click(toggleBtn);
    expect(screen.getByRole('button', { name: /Compact/i })).toBeInTheDocument();
  });
});

