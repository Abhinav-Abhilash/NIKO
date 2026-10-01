import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useVoiceEngine } from '../hooks/useVoiceEngine';
import { wsClient } from '../services/websocket';

describe('useVoiceEngine hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(wsClient, 'send').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('initializes with default voice states', () => {
    const { result } = renderHook(() => useVoiceEngine());
    expect(result.current.isListening).toBe(false);
    expect(result.current.isSpeaking).toBe(false);
    expect(result.current.isBargeInActive).toBe(false);
    expect(result.current.audioLevel).toBe(0);
    expect(result.current.error).toBeNull();
  });

  it('handles barge-in interruption and dispatches WS event', () => {
    const onBargeIn = vi.fn();
    const { result } = renderHook(() => useVoiceEngine({ onBargeIn }));

    act(() => {
      result.current.triggerBargeIn();
    });

    expect(result.current.isBargeInActive).toBe(true);
    expect(result.current.isSpeaking).toBe(false);
    expect(onBargeIn).toHaveBeenCalled();
    expect(wsClient.send).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'voice:barge_in',
        action: 'flush_audio_queue',
      })
    );
  });

  it('speaks sentences and queues them', () => {
    const { result } = renderHook(() => useVoiceEngine());

    act(() => {
      result.current.speakSentence('Hello operator!');
    });

    expect(result.current.flushAudioQueue).toBeDefined();

    act(() => {
      result.current.flushAudioQueue();
    });
    expect(result.current.isSpeaking).toBe(false);
  });
});
