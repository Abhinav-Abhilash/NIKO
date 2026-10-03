import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSpritePetBehavior } from '../hooks/useSpritePetBehavior';

describe('useSpritePetBehavior hook', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('State Priority Resolution', () => {
    it('prioritizes waiting_approval above all other states', () => {
      const { result } = renderHook(() =>
        useSpritePetBehavior({
          hasPendingApproval: true,
          error: 'Critical failure',
          isCoolingDown: true,
          activeToolCallsCount: 3,
          orbState: 'confirm',
          isStreaming: true,
          isSpeaking: true,
          lastToolStatus: 'error',
        })
      );

      expect(result.current.activeState).toBe('waiting_approval');
    });

    it('prioritizes error above cooldown, acting, thinking, speaking, and success', () => {
      const { result } = renderHook(() =>
        useSpritePetBehavior({
          hasPendingApproval: false,
          error: 'LLM Rate limit error',
          isCoolingDown: true,
          activeToolCallsCount: 2,
          orbState: 'acting',
          isStreaming: true,
          isSpeaking: true,
          lastToolStatus: 'error',
        })
      );

      expect(result.current.activeState).toBe('error');
    });

    it('prioritizes quota cooldown above acting, thinking, speaking, and success', () => {
      const { result } = renderHook(() =>
        useSpritePetBehavior({
          hasPendingApproval: false,
          error: null,
          isCoolingDown: true,
          activeToolCallsCount: 2,
          orbState: 'acting',
          isStreaming: true,
          isSpeaking: true,
        })
      );

      expect(result.current.activeState).toBe('cooldown');
    });

    it('prioritizes acting above thinking, speaking, and success', () => {
      const { result } = renderHook(() =>
        useSpritePetBehavior({
          hasPendingApproval: false,
          error: null,
          isCoolingDown: false,
          activeToolCallsCount: 1,
          orbState: 'acting',
          isStreaming: true,
          isSpeaking: true,
        })
      );

      expect(result.current.activeState).toBe('acting');
    });

    it('prioritizes thinking above speaking and success', () => {
      const { result } = renderHook(() =>
        useSpritePetBehavior({
          hasPendingApproval: false,
          error: null,
          isCoolingDown: false,
          activeToolCallsCount: 0,
          orbState: 'thinking',
          isStreaming: true,
          isSpeaking: true,
        })
      );

      expect(result.current.activeState).toBe('thinking');
    });

    it('prioritizes speaking above success and idle', () => {
      const { result } = renderHook(() =>
        useSpritePetBehavior({
          hasPendingApproval: false,
          error: null,
          isCoolingDown: false,
          activeToolCallsCount: 0,
          orbState: 'idle',
          isStreaming: false,
          isSpeaking: true,
          lastToolStatus: 'success',
        })
      );

      expect(result.current.activeState).toBe('speaking');
    });

    it('prioritizes success when tool completes', () => {
      const { result } = renderHook(() =>
        useSpritePetBehavior({
          hasPendingApproval: false,
          error: null,
          isCoolingDown: false,
          activeToolCallsCount: 0,
          orbState: 'idle',
          isStreaming: false,
          isSpeaking: false,
          lastToolStatus: 'success',
        })
      );

      expect(result.current.activeState).toBe('success');
    });

    it('defaults to idle when no backend activity occurs', () => {
      const { result } = renderHook(() =>
        useSpritePetBehavior({
          hasPendingApproval: false,
          error: null,
          isCoolingDown: false,
          activeToolCallsCount: 0,
          orbState: 'idle',
          isStreaming: false,
          isSpeaking: false,
          lastToolStatus: null,
        })
      );

      expect(result.current.activeState).toBe('idle');
      expect(result.current.isAsleep).toBe(false);
      expect(result.current.isSitting).toBe(false);
    });
  });

  describe('Inactivity Sleep Timer with Fake Timers', () => {
    it('transitions to sitting and then sleeping after inactivity timeout', () => {
      const inactivityMs = 60 * 1000; // 1 minute for test
      const { result } = renderHook(() =>
        useSpritePetBehavior({
          inactivityTimeoutMs: inactivityMs,
        })
      );

      expect(result.current.activeState).toBe('idle');

      // Advance by 60 seconds
      act(() => {
        vi.advanceTimersByTime(60000);
      });

      expect(result.current.isSitting).toBe(true);
      expect(result.current.activeState).toBe('sitting');

      // Advance by another 4.5 seconds -> transitions to deep sleep
      act(() => {
        vi.advanceTimersByTime(4500);
      });

      expect(result.current.isAsleep).toBe(true);
      expect(result.current.activeState).toBe('sleeping');

      // Waking up resets back to idle
      act(() => {
        result.current.wakeUp();
      });

      expect(result.current.isAsleep).toBe(false);
      expect(result.current.activeState).toBe('idle');
    });

    it('supports triggerSleepNow dev shortcut', () => {
      const { result } = renderHook(() =>
        useSpritePetBehavior({
          inactivityTimeoutMs: 300000,
        })
      );

      act(() => {
        result.current.triggerSleepNow();
      });

      expect(result.current.isAsleep).toBe(true);
      expect(result.current.activeState).toBe('sleeping');
    });
  });

  describe('Click Reactions & Anti-Spam Cooldown', () => {
    it('triggers a reaction on click and enforces cooldown', () => {
      const { result } = renderHook(() =>
        useSpritePetBehavior({
          clickReactionCooldownMs: 1800,
        })
      );

      let firstReaction: string | null = null;
      act(() => {
        firstReaction = result.current.handleClick();
      });

      expect(firstReaction).not.toBeNull();
      expect(['happy', 'startled', 'annoyed']).toContain(firstReaction);
      expect(result.current.isReacting).toBe(true);

      // Immediate second click should be throttled by cooldown
      let secondReaction: string | null = null;
      act(() => {
        secondReaction = result.current.handleClick();
      });

      expect(secondReaction).toBeNull();

      // Advance time past cooldown
      act(() => {
        vi.advanceTimersByTime(1900);
      });

      expect(result.current.isReacting).toBe(false);

      // Third click after cooldown should succeed
      let thirdReaction: string | null = null;
      act(() => {
        thirdReaction = result.current.handleClick();
      });

      expect(thirdReaction).not.toBeNull();
    });
  });

  describe('Direction Mirroring', () => {
    it('allows changing direction between left and right', () => {
      const { result } = renderHook(() => useSpritePetBehavior());

      expect(result.current.direction).toBe('left');

      act(() => {
        result.current.setDirection('right');
      });

      expect(result.current.direction).toBe('right');
    });
  });
});
