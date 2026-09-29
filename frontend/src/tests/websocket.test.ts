import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { WebSocketClient } from '../services/websocket';

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  public readyState: number = MockWebSocket.CONNECTING;
  public url: string;
  public onopen: (() => void) | null = null;
  public onmessage: ((event: { data: string }) => void) | null = null;
  public onclose: ((event: { code: number; reason: string }) => void) | null = null;
  public onerror: ((error: any) => void) | null = null;
  public sentData: string[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sentData.push(data);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose({ code: 1000, reason: 'Normal Closure' });
    }
  }

  simulateOpen() {
    this.readyState = MockWebSocket.OPEN;
    if (this.onopen) this.onopen();
  }

  simulateMessage(data: Record<string, unknown>) {
    if (this.onmessage) this.onmessage({ data: JSON.stringify(data) });
  }

  simulateError(err: any) {
    if (this.onerror) this.onerror(err);
  }
}

describe('WebSocketClient Service', () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('connects to the configured websocket URL and emits connection_status', () => {
    const client = new WebSocketClient();
    const statusSpy = vi.fn();
    client.on('connection_status', statusSpy);

    client.connect();
    expect(MockWebSocket.instances.length).toBe(1);

    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    expect(client.getStatus()).toBe(true);
    expect(statusSpy).toHaveBeenCalledWith({ connected: true });
  });

  it('starts sending heartbeat pings after connection opens', () => {
    const client = new WebSocketClient();
    client.connect();

    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    // Advance 15 seconds
    vi.advanceTimersByTime(15000);
    expect(ws.sentData.length).toBe(1);
    const pingPayload = JSON.parse(ws.sentData[0]);
    expect(pingPayload.type).toBe('ping');
    expect(pingPayload.timestamp).toBeDefined();
  });

  it('routes incoming messages to subscribed event listeners', () => {
    const client = new WebSocketClient();
    const chunkSpy = vi.fn();
    client.on('chat:chunk', chunkSpy);

    client.connect();
    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    ws.simulateMessage({
      type: 'chat:chunk',
      request_id: 'req-1',
      chunk: 'Hello world',
    });

    expect(chunkSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'chat:chunk',
        request_id: 'req-1',
        chunk: 'Hello world',
      })
    );
  });

  it('attempts reconnection with backoff when socket drops unexpectedly', () => {
    const client = new WebSocketClient();
    client.connect();

    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    // Unexpected close
    ws.close();
    expect(client.getStatus()).toBe(false);

    // Timer advances by reconnect delay (1000ms)
    vi.advanceTimersByTime(1000);
    expect(MockWebSocket.instances.length).toBe(2);
  });

  it('formats and sends chat requests and cancellation payloads', () => {
    const client = new WebSocketClient();
    client.connect();

    const ws = MockWebSocket.instances[0];
    ws.simulateOpen();

    client.sendChat('req-42', 'Explain quantum physics', 'conv-1', 'reasoning', true);
    expect(ws.sentData.length).toBe(1);
    expect(JSON.parse(ws.sentData[0])).toEqual({
      type: 'chat',
      request_id: 'req-42',
      content: 'Explain quantum physics',
      conversation_id: 'conv-1',
      role: 'reasoning',
      elevated_mode: true,
    });

    client.cancelChat('req-42');
    expect(ws.sentData.length).toBe(2);
    expect(JSON.parse(ws.sentData[1])).toEqual({
      type: 'chat:cancel',
      request_id: 'req-42',
    });
  });
});
