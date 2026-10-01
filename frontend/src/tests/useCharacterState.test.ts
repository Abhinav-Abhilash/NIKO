import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useCharacterState } from '../hooks/useCharacterState';

describe('useCharacterState hook', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useFakeTimers();
  });

  it('maps idle AI state to IDLE semantic state, STANDING posture, and NEUTRAL emotion', () => {
    const { result } = renderHook(() =>
      useCharacterState({
        orbState: 'idle',
        isListening: false,
        isSpeaking: false,
        isStreaming: false,
        hasPendingApproval: false,
        activeToolCallsCount: 0,
      })
    );

    expect(result.current.semanticState).toBe('ASSISTANT_IDLE');
    expect(result.current.posture).toBe('STANDING');
    expect(result.current.emotion).toBe('NEUTRAL');
  });

  it('maps voice listening to ASSISTANT_LISTENING and CURIOUS emotion', () => {
    const { result } = renderHook(() =>
      useCharacterState({
        orbState: 'idle',
        isListening: true,
        isSpeaking: false,
        isStreaming: false,
        hasPendingApproval: false,
        activeToolCallsCount: 0,
      })
    );

    expect(result.current.semanticState).toBe('ASSISTANT_LISTENING');
    expect(result.current.emotion).toBe('CURIOUS');
  });

  it('maps tool activity to ASSISTANT_WORKING and SITTING posture', () => {
    const { result } = renderHook(() =>
      useCharacterState({
        orbState: 'acting',
        isListening: false,
        isSpeaking: false,
        isStreaming: false,
        hasPendingApproval: false,
        activeToolCallsCount: 1,
      })
    );

    expect(result.current.semanticState).toBe('ASSISTANT_WORKING');
    expect(result.current.posture).toBe('SITTING');
  });

  it('handles drag-and-drop state lifecycle', () => {
    const { result } = renderHook(() =>
      useCharacterState({
        orbState: 'idle',
        isListening: false,
        isSpeaking: false,
        isStreaming: false,
        hasPendingApproval: false,
        activeToolCallsCount: 0,
        initialX: 100,
        initialY: 200,
      })
    );

    expect(result.current.position).toEqual({ x: 100, y: 200 });

    // Start drag
    act(() => {
      result.current.startDrag({
        clientX: 100,
        clientY: 200,
        pointerId: 1,
        target: document.createElement('div'),
      } as unknown as React.PointerEvent);
    });

    expect(result.current.isDragging).toBe(true);
    expect(result.current.posture).toBe('DRAGGED');

    // Move drag
    act(() => {
      result.current.onDrag({
        clientX: 150,
        clientY: 250,
      } as unknown as React.PointerEvent);
    });

    expect(result.current.position).toEqual({ x: 150, y: 250 });

    // End drag
    const clickCb = vi.fn();
    act(() => {
      result.current.endDrag(
        {
          pointerId: 1,
          target: document.createElement('div'),
        } as unknown as React.PointerEvent,
        clickCb
      );
    });

    expect(result.current.isDragging).toBe(false);
  });
});
