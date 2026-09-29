import React, { useEffect, useState } from 'react';
import { toastService } from '../services/toast';
import type { ToastItem } from '../services/toast';

export const ToastContainer: React.FC = () => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  useEffect(() => {
    return toastService.subscribe((list) => {
      setToasts(list);
    });
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none">
      {toasts.map((toast) => {
        const isUndo = toast.type === 'undo';
        const isError = toast.type === 'error';
        const isSuccess = toast.type === 'success';

        return (
          <div
            key={toast.id}
            className={`pointer-events-auto p-3.5 rounded-xl border shadow-xl flex flex-col gap-1.5 font-mono text-xs animate-in slide-in-from-bottom-2 fade-in duration-200 ${
              isError
                ? 'bg-error-container/90 text-on-error-container border-error/50'
                : isUndo
                ? 'bg-primary-container/95 text-on-primary-container border-primary-fixed shadow-[0_0_15px_rgba(255,176,32,0.4)]'
                : isSuccess
                ? 'bg-secondary-container/90 text-on-secondary-container border-secondary/50'
                : 'bg-surface-container-high/95 text-on-surface border-surface-variant'
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 font-bold truncate">
                <span className="material-symbols-outlined text-base">
                  {isError ? 'error' : isUndo ? 'history' : isSuccess ? 'check_circle' : 'info'}
                </span>
                <span className="truncate">{toast.title}</span>
              </div>
              <button
                type="button"
                onClick={() => toastService.dismiss(toast.id)}
                className="opacity-70 hover:opacity-100"
              >
                <span className="material-symbols-outlined text-sm">close</span>
              </button>
            </div>

            <p className="text-[11px] leading-relaxed opacity-90">{toast.message}</p>

            {isUndo && toast.undoAction && (
              <div className="flex items-center justify-between pt-1 mt-1 border-t border-on-primary-container/20">
                <span className="text-[10px] uppercase font-bold">5s Undo Window Active</span>
                <button
                  type="button"
                  onClick={() => {
                    if (toast.undoAction) toast.undoAction();
                    toastService.dismiss(toast.id);
                  }}
                  className="px-2.5 py-1 bg-surface-container-lowest text-primary font-bold rounded shadow hover:bg-surface-container transition-colors"
                >
                  Undo Action
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
