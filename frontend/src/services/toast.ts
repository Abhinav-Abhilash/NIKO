export interface ToastItem {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error' | 'undo';
  title: string;
  message: string;
  durationMs?: number;
  undoAction?: () => void;
  createdAt: number;
}

type ToastListener = (toasts: ToastItem[]) => void;

class ToastManager {
  private toasts: ToastItem[] = [];
  private listeners: Set<ToastListener> = new Set();

  public subscribe(listener: ToastListener): () => void {
    this.listeners.add(listener);
    listener(this.toasts);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notify(): void {
    this.listeners.forEach((listener) => listener([...this.toasts]));
  }

  public show(toast: Omit<ToastItem, 'id' | 'createdAt'>): string {
    const id = `toast_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const newToast: ToastItem = {
      ...toast,
      id,
      createdAt: Date.now(),
      durationMs: toast.durationMs ?? (toast.type === 'undo' ? 5000 : 4000),
    };

    this.toasts = [...this.toasts, newToast];
    this.notify();

    if (newToast.durationMs && newToast.durationMs > 0) {
      setTimeout(() => {
        this.dismiss(id);
      }, newToast.durationMs);
    }

    return id;
  }

  public dismiss(id: string): void {
    this.toasts = this.toasts.filter((t) => t.id !== id);
    this.notify();
  }

  public success(title: string, message: string): void {
    this.show({ type: 'success', title, message });
  }

  public error(title: string, message: string): void {
    this.show({ type: 'error', title, message });
  }

  public info(title: string, message: string): void {
    this.show({ type: 'info', title, message });
  }

  public undo(title: string, message: string, onUndo: () => void): void {
    this.show({ type: 'undo', title, message, undoAction: onUndo, durationMs: 5000 });
  }
}

export const toastService = new ToastManager();
