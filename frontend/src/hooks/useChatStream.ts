import { useState, useEffect, useCallback, useRef } from 'react';
import { wsClient } from '../services/websocket';

export interface ToolCallItem {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  status: 'running' | 'completed' | 'failed' | 'awaiting_approval';
  result?: unknown;
  error?: string;
}

export interface ChatMessageItem {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  isStreaming?: boolean;
  status: 'pending' | 'streaming' | 'completed' | 'failed' | 'cancelled';
  toolCalls?: ToolCallItem[];
  timestamp: string;
}

export interface ChatStreamState {
  messages: ChatMessageItem[];
  isStreaming: boolean;
  streamingRequestId: string | null;
  activeToolCalls: ToolCallItem[];
  error: string | null;
}

export interface ChatStreamActions {
  sendMessage: (content: string, options?: { role?: string; elevatedMode?: boolean; conversationId?: string }) => string;
  cancelStream: () => void;
  clearMessages: () => void;
}

export type UseChatStreamReturn = ChatStreamState & ChatStreamActions;

export function useChatStream(): UseChatStreamReturn {
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [streamingRequestId, setStreamingRequestId] = useState<string | null>(null);
  const [activeToolCalls, setActiveToolCalls] = useState<ToolCallItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  const activeReqIdRef = useRef<string | null>(null);
  activeReqIdRef.current = streamingRequestId;

  const sendMessage = useCallback((content: string, options?: { role?: string; elevatedMode?: boolean; conversationId?: string }): string => {
    const trimmed = content.trim();
    if (!trimmed) return '';

    const reqId = `req_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const nowIso = new Date().toISOString();

    const userMessage: ChatMessageItem = {
      id: `usr_${Date.now()}`,
      role: 'user',
      content: trimmed,
      status: 'completed',
      timestamp: nowIso,
    };

    const assistantMessage: ChatMessageItem = {
      id: `ast_${Date.now()}`,
      role: 'assistant',
      content: '',
      isStreaming: true,
      status: 'streaming',
      toolCalls: [],
      timestamp: nowIso,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsStreaming(true);
    setStreamingRequestId(reqId);
    setActiveToolCalls([]);
    setError(null);

    // Make sure WebSocket is connected
    wsClient.connect();
    wsClient.sendChat(reqId, trimmed, options?.conversationId, options?.role, options?.elevatedMode);

    return reqId;
  }, []);

  const cancelStream = useCallback(() => {
    const curId = activeReqIdRef.current;
    if (curId) {
      wsClient.cancelChat(curId);
      setIsStreaming(false);
      setStreamingRequestId(null);
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.role === 'assistant' && last.status === 'streaming') {
          return [
            ...prev.slice(0, -1),
            { ...last, isStreaming: false, status: 'cancelled' },
          ];
        }
        return prev;
      });
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setIsStreaming(false);
    setStreamingRequestId(null);
    setActiveToolCalls([]);
    setError(null);
  }, []);

  // Bind WebSocket events
  useEffect(() => {
    const unsubChunk = wsClient.on('chat:chunk', (data: { request_id?: string; chunk?: string }) => {
      const chunkText = data.chunk || '';
      setMessages((prev) => {
        const lastIdx = prev.length - 1;
        if (lastIdx < 0) return prev;
        const last = prev[lastIdx];
        if (last.role === 'assistant') {
          const updated: ChatMessageItem = {
            ...last,
            content: last.content + chunkText,
          };
          return [...prev.slice(0, lastIdx), updated];
        }
        return prev;
      });
    });

    const unsubToolCall = wsClient.on('chat:tool_call', (data: { request_id?: string; name?: string; tool_call_id?: string; arguments?: Record<string, unknown> }) => {
      const tc: ToolCallItem = {
        id: data.tool_call_id || `tc_${Date.now()}`,
        name: data.name || 'unknown_tool',
        arguments: data.arguments || {},
        status: 'running',
      };

      setActiveToolCalls((prev) => [...prev, tc]);

      setMessages((prev) => {
        const lastIdx = prev.length - 1;
        if (lastIdx < 0) return prev;
        const last = prev[lastIdx];
        if (last.role === 'assistant') {
          const existingTools = last.toolCalls || [];
          return [
            ...prev.slice(0, lastIdx),
            { ...last, toolCalls: [...existingTools, tc] },
          ];
        }
        return prev;
      });
    });

    const unsubToolResult = wsClient.on('chat:tool_result', (data: { request_id?: string; name?: string; tool_call_id?: string; result?: unknown; error?: string; status?: string }) => {
      const toolId = data.tool_call_id;
      const status = data.status === 'failed' || data.error ? 'failed' : 'completed';

      setActiveToolCalls((prev) => prev.filter((t) => t.id !== toolId && t.name !== data.name));

      setMessages((prev) => {
        const lastIdx = prev.length - 1;
        if (lastIdx < 0) return prev;
        const last = prev[lastIdx];
        if (last.role === 'assistant' && last.toolCalls) {
          const updatedTools = last.toolCalls.map((t) => {
            if ((toolId && t.id === toolId) || (!toolId && t.name === data.name)) {
              return { ...t, status: status as 'completed' | 'failed', result: data.result, error: data.error };
            }
            return t;
          });
          return [...prev.slice(0, lastIdx), { ...last, toolCalls: updatedTools }];
        }
        return prev;
      });
    });

    const unsubDone = wsClient.on('chat:done', (_data: { request_id?: string; response?: unknown }) => {
      setIsStreaming(false);
      setStreamingRequestId(null);
      setActiveToolCalls([]);
      setMessages((prev) => {
        const lastIdx = prev.length - 1;
        if (lastIdx < 0) return prev;
        const last = prev[lastIdx];
        if (last.role === 'assistant') {
          return [
            ...prev.slice(0, lastIdx),
            { ...last, isStreaming: false, status: 'completed' },
          ];
        }
        return prev;
      });
    });

    const unsubError = wsClient.on('chat:error', (data: { request_id?: string; error?: string }) => {
      const errMsg = data.error || 'Chat streaming failed';
      setError(errMsg);
      setIsStreaming(false);
      setStreamingRequestId(null);
      setActiveToolCalls([]);
      setMessages((prev) => {
        const lastIdx = prev.length - 1;
        if (lastIdx < 0) return prev;
        const last = prev[lastIdx];
        if (last.role === 'assistant') {
          return [
            ...prev.slice(0, lastIdx),
            { ...last, isStreaming: false, status: 'failed', content: last.content || `Error: ${errMsg}` },
          ];
        }
        return prev;
      });
    });

    const unsubCancelAck = wsClient.on('chat:cancel_ack', () => {
      setIsStreaming(false);
      setStreamingRequestId(null);
      setActiveToolCalls([]);
    });

    return () => {
      unsubChunk();
      unsubToolCall();
      unsubToolResult();
      unsubDone();
      unsubError();
      unsubCancelAck();
    };
  }, []);

  return {
    messages,
    isStreaming,
    streamingRequestId,
    activeToolCalls,
    error,
    sendMessage,
    cancelStream,
    clearMessages,
  };
}
