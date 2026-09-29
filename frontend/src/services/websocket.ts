export type WebSocketEventListener = (payload: any) => void;

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private listeners: Map<string, Set<WebSocketEventListener>> = new Map();
  private isIntentionalClose = false;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 15;
  private reconnectDelay = 1000;
  private heartbeatInterval: number | null = null;
  private isConnected = false;
  private url: string;

  constructor() {
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = import.meta.env.VITE_WS_HOST || 'localhost:7421';
    this.url = `${wsProto}//${wsHost}/ws`;
  }

  public connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isIntentionalClose = false;
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
        this.emit('connection_status', { connected: true });
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const type = data.type || (data.topic && data.event_type ? `${data.topic}:${data.event_type}` : 'message');
          this.emit(type, data);
        } catch (err) {
          console.error('Failed to parse incoming WS message:', err);
        }
      };

      this.ws.onclose = (event) => {
        this.isConnected = false;
        this.stopHeartbeat();
        this.emit('connection_status', { connected: false, code: event.code, reason: event.reason });
        if (!this.isIntentionalClose) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = (err) => {
        console.warn('WebSocket encountered error:', err);
        this.emit('error', err);
      };
    } catch (error) {
      console.error('Error instantiating WebSocket:', error);
      this.scheduleReconnect();
    }
  }

  public disconnect(): void {
    this.isIntentionalClose = true;
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.isConnected = false;
  }

  public send(data: Record<string, unknown>): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn('WebSocket not connected, failed to send payload:', data);
    }
  }

  public sendChat(requestId: string, content: string, conversationId?: string, role?: string, elevatedMode?: boolean): void {
    this.send({
      type: 'chat',
      request_id: requestId,
      content,
      conversation_id: conversationId,
      role,
      elevated_mode: elevatedMode,
    });
  }

  public cancelChat(requestId: string): void {
    this.send({
      type: 'chat:cancel',
      request_id: requestId,
    });
  }

  public on(event: string, listener: WebSocketEventListener): () => void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(listener);

    return () => {
      this.listeners.get(event)?.delete(listener);
    };
  }

  public emit(event: string, payload: unknown): void {
    const eventListeners = this.listeners.get(event);
    if (eventListeners) {
      eventListeners.forEach((listener) => {
        try {
          listener(payload);
        } catch (err) {
          console.error(`Error in WS listener for event '${event}':`, err);
        }
      });
    }

    // Global listener catch-all
    const allListeners = this.listeners.get('*');
    if (allListeners) {
      allListeners.forEach((listener) => {
        try {
          listener({ event, payload });
        } catch (err) {
          console.error('Error in wildcard WS listener:', err);
        }
      });
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatInterval = window.setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.send({ type: 'ping', timestamp: Date.now() });
      }
    }, 15000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval !== null) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.warn('Max WebSocket reconnect attempts reached.');
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1), 20000);
    setTimeout(() => {
      if (!this.isIntentionalClose && (!this.ws || this.ws.readyState === WebSocket.CLOSED)) {
        this.connect();
      }
    }, delay);
  }

  public getStatus(): boolean {
    return this.isConnected;
  }
}

export const wsClient = new WebSocketClient();
