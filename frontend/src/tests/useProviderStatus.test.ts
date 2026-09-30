import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useProviderStatus } from '../hooks/useProviderStatus';
import { wsClient } from '../services/websocket';

describe('useProviderStatus hook', () => {
  it('initializes with clear status', () => {
    const { result } = renderHook(() => useProviderStatus());
    expect(result.current.isCoolingDown).toBe(false);
    expect(result.current.coolingRole).toBeNull();
    expect(result.current.shortestResetSeconds).toBeNull();
  });

  it('updates state when chat:cooldown_banner event is received', () => {
    const { result } = renderHook(() => useProviderStatus());

    act(() => {
      wsClient.emit('chat:cooldown_banner', {
        role: 'chat',
        shortest_reset_seconds: 42,
        message: 'all providers cooling down, shortest reset in 42s',
      });
    });

    expect(result.current.isCoolingDown).toBe(true);
    expect(result.current.coolingRole).toBe('chat');
    expect(result.current.shortestResetSeconds).toBe(42);
    expect(result.current.cooldownMessage).toBe('all providers cooling down, shortest reset in 42s');

    act(() => {
      result.current.clearCooldown();
    });

    expect(result.current.isCoolingDown).toBe(false);
    expect(result.current.coolingRole).toBeNull();
  });
});
