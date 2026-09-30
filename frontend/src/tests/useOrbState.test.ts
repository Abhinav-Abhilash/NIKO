import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useOrbState } from '../hooks/useOrbState';

describe('useOrbState hook', () => {
  it('resolves to idle when no streams or approvals are in flight', () => {
    const { result } = renderHook(() =>
      useOrbState({ hasPendingApproval: false, isStreaming: false, activeToolCallsCount: 0 })
    );
    expect(result.current.orbState).toBe('idle');
    expect(result.current.isIdle).toBe(true);
    expect(result.current.isThinking).toBe(false);
    expect(result.current.isActing).toBe(false);
    expect(result.current.isConfirm).toBe(false);
  });

  it('resolves to thinking when streaming text', () => {
    const { result } = renderHook(() =>
      useOrbState({ hasPendingApproval: false, isStreaming: true, activeToolCallsCount: 0 })
    );
    expect(result.current.orbState).toBe('thinking');
    expect(result.current.isThinking).toBe(true);
  });

  it('resolves to acting when tools are executing', () => {
    const { result } = renderHook(() =>
      useOrbState({ hasPendingApproval: false, isStreaming: true, activeToolCallsCount: 2 })
    );
    expect(result.current.orbState).toBe('acting');
    expect(result.current.isActing).toBe(true);
  });

  it('prioritizes confirm over acting and thinking when an approval is pending', () => {
    const { result } = renderHook(() =>
      useOrbState({ hasPendingApproval: true, isStreaming: true, activeToolCallsCount: 1 })
    );
    expect(result.current.orbState).toBe('confirm');
    expect(result.current.isConfirm).toBe(true);
  });
});
