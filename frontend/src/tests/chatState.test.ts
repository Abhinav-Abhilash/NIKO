import { describe, it, expect } from 'vitest';
import type { ChatMessage, ToolCallItem } from '../types';

describe('Chat State Reducer & Logic', () => {
  it('correctly appends streaming chunks to the active assistant message', () => {
    let messages: ChatMessage[] = [
      {
        id: 'msg-1',
        role: 'user',
        content: 'Hello',
        timestamp: new Date().toISOString(),
      },
    ];

    const chunk1 = 'Hello ';
    const chunk2 = 'from ';
    const chunk3 = 'NIKO!';

    // Simulate first chunk arriving
    const handleChunk = (prev: ChatMessage[], chunk: string): ChatMessage[] => {
      const lastMsg = prev[prev.length - 1];
      if (lastMsg && lastMsg.role === 'assistant' && lastMsg.isStreaming) {
        return [
          ...prev.slice(0, -1),
          { ...lastMsg, content: lastMsg.content + chunk },
        ];
      }
      return [
        ...prev,
        {
          id: 'msg-assist-1',
          role: 'assistant',
          content: chunk,
          timestamp: new Date().toISOString(),
          isStreaming: true,
        },
      ];
    };

    messages = handleChunk(messages, chunk1);
    expect(messages.length).toBe(2);
    expect(messages[1].content).toBe('Hello ');
    expect(messages[1].isStreaming).toBe(true);

    messages = handleChunk(messages, chunk2);
    expect(messages.length).toBe(2);
    expect(messages[1].content).toBe('Hello from ');

    messages = handleChunk(messages, chunk3);
    expect(messages.length).toBe(2);
    expect(messages[1].content).toBe('Hello from NIKO!');
  });

  it('updates tool call state and result payload on tool completion', () => {
    const initialTool: ToolCallItem = {
      id: 'tc-101',
      name: 'datetime',
      arguments: {},
      status: 'running',
    };

    let messages: ChatMessage[] = [
      {
        id: 'msg-2',
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
        toolCalls: [initialTool],
        isStreaming: true,
      },
    ];

    // Tool result event arrives
    const handleToolResult = (
      prev: ChatMessage[],
      toolName: string,
      result: any,
      status: 'completed' | 'failed'
    ): ChatMessage[] => {
      const lastMsg = prev[prev.length - 1];
      if (!lastMsg || !lastMsg.toolCalls) return prev;

      const updatedTools = lastMsg.toolCalls.map((tc) => {
        if (tc.name === toolName) {
          return {
            ...tc,
            result,
            status,
          };
        }
        return tc;
      });

      return [...prev.slice(0, -1), { ...lastMsg, toolCalls: updatedTools }];
    };

    messages = handleToolResult(messages, 'datetime', { utc: '2026-09-29T20:00:00Z' }, 'completed');
    expect(messages[0].toolCalls![0].status).toBe('completed');
    expect(messages[0].toolCalls![0].result).toEqual({ utc: '2026-09-29T20:00:00Z' });
  });

  it('detects untrusted external content tags and tags message as external', () => {
    const rawUserPrompt = 'Summary of: <untrusted_external_content>Suspicious data</untrusted_external_content>';
    const isExternal = rawUserPrompt.includes('<untrusted_external_content>');

    const userMsg: ChatMessage = {
      id: 'usr-1',
      role: 'user',
      content: rawUserPrompt,
      timestamp: new Date().toISOString(),
      isExternal,
    };

    expect(userMsg.isExternal).toBe(true);
  });
});
