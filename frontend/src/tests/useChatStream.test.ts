import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useChatStream } from '../hooks/useChatStream';
import { wsClient } from '../services/websocket';

describe('useChatStream hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initializes with empty state', () => {
    const { result } = renderHook(() => useChatStream());
    expect(result.current.messages).toHaveLength(0);
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.streamingRequestId).toBeNull();
    expect(result.current.activeToolCalls).toHaveLength(0);
    expect(result.current.error).toBeNull();
  });

  it('initiates streaming and handles incoming chunks and tool calls', () => {
    const sendChatSpy = vi.spyOn(wsClient, 'sendChat').mockImplementation(() => {});
    const { result } = renderHook(() => useChatStream());

    let reqId = '';
    act(() => {
      reqId = result.current.sendMessage('Hello world');
    });

    expect(result.current.isStreaming).toBe(true);
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0].content).toBe('Hello world');
    expect(sendChatSpy).toHaveBeenCalledWith(reqId, 'Hello world', undefined, undefined, undefined);

    // Receive streaming chunk
    act(() => {
      wsClient.emit('chat:chunk', { request_id: reqId, chunk: 'Hi ' });
    });
    expect(result.current.messages[1].content).toBe('Hi ');

    act(() => {
      wsClient.emit('chat:chunk', { request_id: reqId, chunk: 'there!' });
    });
    expect(result.current.messages[1].content).toBe('Hi there!');

    // Receive tool call
    act(() => {
      wsClient.emit('chat:tool_call', {
        request_id: reqId,
        name: 'datetime',
        tool_call_id: 'tc_1',
        arguments: {},
      });
    });
    expect(result.current.activeToolCalls).toHaveLength(1);
    expect(result.current.messages[1].toolCalls).toHaveLength(1);

    // Receive tool result
    act(() => {
      wsClient.emit('chat:tool_result', {
        request_id: reqId,
        name: 'datetime',
        tool_call_id: 'tc_1',
        result: { time: '12:00:00' },
        status: 'completed',
      });
    });
    expect(result.current.activeToolCalls).toHaveLength(0);
    expect(result.current.messages[1].toolCalls?.[0].status).toBe('completed');

    // Done event
    act(() => {
      wsClient.emit('chat:done', { request_id: reqId });
    });
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.messages[1].status).toBe('completed');
  });

  it('cancels an in-flight stream', () => {
    const cancelChatSpy = vi.spyOn(wsClient, 'cancelChat').mockImplementation(() => {});
    const { result } = renderHook(() => useChatStream());

    let reqId = '';
    act(() => {
      reqId = result.current.sendMessage('Slow request');
    });
    expect(result.current.isStreaming).toBe(true);

    act(() => {
      result.current.cancelStream();
    });

    expect(cancelChatSpy).toHaveBeenCalledWith(reqId);
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.messages[1].status).toBe('cancelled');
  });
});
