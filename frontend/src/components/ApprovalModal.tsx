import React, { useEffect, useState } from 'react';
import type { ApprovalRequestItem } from '../types';

interface ApprovalModalProps {
  request: ApprovalRequestItem | null;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onClose: () => void;
}

export const ApprovalModal: React.FC<ApprovalModalProps> = ({
  request,
  onApprove,
  onReject,
  onClose,
}) => {
  const [secondsLeft, setSecondsLeft] = useState<number>(request?.timeoutSeconds || 30);

  useEffect(() => {
    if (!request) return;
    setSecondsLeft(request.timeoutSeconds || 30);

    const timer = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          onReject(request.id);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [request, onReject]);

  if (!request) return null;

  const riskColor =
    request.riskLevel === 'critical'
      ? 'text-error border-error/50 bg-error/10'
      : request.riskLevel === 'high'
      ? 'text-primary-container border-primary-container/50 bg-primary-container/10'
      : 'text-secondary border-secondary/50 bg-secondary/10';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl bg-surface-container-low border border-primary-container/40 rounded-xl shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 bg-surface-container border-b border-surface-variant/40">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-primary-container text-2xl animate-pulse">
              gavel
            </span>
            <div>
              <h3 className="font-mono text-lg font-bold text-on-surface">
                PERMISSION CONFIRMATION REQUIRED
              </h3>
              <p className="font-mono text-xs text-on-surface-variant">
                Autonomous agent requested execution of restricted skill
              </p>
            </div>
          </div>
          <span className={`px-2.5 py-1 rounded text-xs font-mono font-bold border uppercase ${riskColor}`}>
            {request.riskLevel} RISK
          </span>
        </div>

        {/* Modal Body */}
        <div className="p-6 flex flex-col gap-4">
          {/* Target Skill Info */}
          <div className="flex items-center justify-between p-3 bg-surface-container-high rounded border border-surface-variant/40 font-mono text-sm">
            <div className="flex items-center gap-2">
              <span className="text-on-surface-variant">SKILL:</span>
              <span className="text-primary font-bold">{request.toolName}</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-on-surface-variant">
              <span>AUTO-CANCEL IN:</span>
              <span className="text-primary-container font-bold">{secondsLeft}s</span>
            </div>
          </div>

          {/* Parameters Payload */}
          <div className="flex flex-col gap-1.5">
            <label className="font-mono text-xs text-on-surface-variant uppercase tracking-wider font-semibold">
              Execution Payload & Parameters
            </label>
            <div className="bg-surface-container-lowest p-4 rounded border border-surface-variant/60 font-mono text-xs text-on-surface overflow-x-auto max-h-60">
              <pre>{JSON.stringify(request.arguments, null, 2)}</pre>
            </div>
          </div>

          {/* Warning Message */}
          <div className="p-3 bg-primary-container/10 border border-primary-container/30 rounded flex items-start gap-2.5 text-xs text-primary">
            <span className="material-symbols-outlined text-base flex-shrink-0 mt-0.5">
              warning
            </span>
            <span>
              Executing this skill will invoke a local system or file-system operation.
              Review arguments carefully before approving.
            </span>
          </div>
        </div>

        {/* Modal Actions */}
        <div className="flex items-center justify-between px-6 py-4 bg-surface-container border-t border-surface-variant/40">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-surface-container-high hover:bg-surface-variant text-on-surface-variant hover:text-on-surface text-sm font-mono rounded transition-colors"
          >
            Dismiss
          </button>
          <div className="flex items-center gap-3">
            <button
              onClick={() => onReject(request.id)}
              className="px-5 py-2 bg-error-container/20 hover:bg-error-container/40 text-error border border-error/40 text-sm font-mono font-semibold rounded transition-all"
            >
              Deny Execution
            </button>
            <button
              onClick={() => onApprove(request.id)}
              className="px-6 py-2 bg-primary-container hover:bg-primary-fixed text-on-primary-container font-mono font-bold text-sm rounded shadow-[0_0_15px_rgba(255,176,32,0.4)] transition-all hover:scale-105"
            >
              Approve & Execute
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
