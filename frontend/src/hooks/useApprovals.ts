import { useState, useEffect, useCallback, useRef } from 'react';
import { wsClient } from '../services/websocket';
import { ApiService } from '../services/api';

export type ApprovalPersistence = 'once' | 'session' | 'always';

export interface PendingApproval {
  approvalId: string;
  skillName: string;
  arguments: Record<string, unknown>;
  reason?: string;
  provenance: string;
  requestedAt: number;
  expiresAt: number;
  remainingSeconds: number;
}

export interface ApprovalsState {
  pendingApproval: PendingApproval | null;
  hasPendingApproval: boolean;
  remainingSeconds: number;
}

export interface ApprovalsActions {
  approve: (persistence?: ApprovalPersistence) => Promise<void>;
  deny: (reason?: string) => Promise<void>;
}

export type UseApprovalsReturn = ApprovalsState & ApprovalsActions;

interface UseApprovalsOptions {
  onApprovalArrive?: (approval: PendingApproval) => void;
  defaultCountdownSeconds?: number;
}

export function useApprovals(options?: UseApprovalsOptions): UseApprovalsReturn {
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState<number>(options?.defaultCountdownSeconds || 30);

  const pendingRef = useRef<PendingApproval | null>(null);
  pendingRef.current = pendingApproval;

  const onArriveRef = useRef(options?.onApprovalArrive);
  onArriveRef.current = options?.onApprovalArrive;

  const deny = useCallback(async (_reason = 'denied_by_user') => {
    const cur = pendingRef.current;
    if (!cur) return;

    try {
      await ApiService.respondToApproval(cur.approvalId, 'deny');
    } catch (err) {
      console.warn('Failed to send denial to backend:', err);
    } finally {
      setPendingApproval(null);
      setRemainingSeconds(options?.defaultCountdownSeconds || 30);
    }
  }, [options?.defaultCountdownSeconds]);

  const approve = useCallback(async (persistence: ApprovalPersistence = 'once') => {
    const cur = pendingRef.current;
    if (!cur) return;

    if (persistence === 'session') {
      try {
        const sessionAllowed = JSON.parse(sessionStorage.getItem('niko_session_allowed_skills') || '[]');
        sessionAllowed.push(cur.skillName);
        sessionStorage.setItem('niko_session_allowed_skills', JSON.stringify(sessionAllowed));
      } catch {
        // storage disabled or unavailable
      }
    } else if (persistence === 'always') {
      try {
        const alwaysAllowed = JSON.parse(localStorage.getItem('niko_always_allowed_skills') || '[]');
        alwaysAllowed.push({ skill: cur.skillName, args: cur.arguments });
        localStorage.setItem('niko_always_allowed_skills', JSON.stringify(alwaysAllowed));
      } catch {
        // storage disabled or unavailable
      }
    }

    try {
      await ApiService.respondToApproval(cur.approvalId, 'approve');
    } catch (err) {
      console.warn('Failed to send approval to backend:', err);
    } finally {
      setPendingApproval(null);
      setRemainingSeconds(options?.defaultCountdownSeconds || 30);
    }
  }, [options?.defaultCountdownSeconds]);

  // Handle incoming approval requests from WebSocket
  useEffect(() => {
    const handleIncoming = (data: Record<string, unknown>) => {
      const approvalObj = (data.approval as Record<string, unknown>) || data;
      const approvalId = String(approvalObj.approval_id || approvalObj.id || '');
      if (!approvalId) return;

      const countdown = Number(approvalObj.timeout_seconds || options?.defaultCountdownSeconds || 30);
      const newApproval: PendingApproval = {
        approvalId,
        skillName: String(approvalObj.skill_name || approvalObj.name || 'unspecified_skill'),
        arguments: (approvalObj.arguments as Record<string, unknown>) || {},
        reason: approvalObj.reason ? String(approvalObj.reason) : undefined,
        provenance: String(approvalObj.provenance || 'direct'),
        requestedAt: Date.now(),
        expiresAt: Date.now() + countdown * 1000,
        remainingSeconds: countdown,
      };

      setPendingApproval(newApproval);
      setRemainingSeconds(countdown);

      if (onArriveRef.current) {
        onArriveRef.current(newApproval);
      }
    };

    const unsubReq = wsClient.on('approval:request', handleIncoming);
    const unsubChatApproval = wsClient.on('chat:approval_required', handleIncoming);

    return () => {
      unsubReq();
      unsubChatApproval();
    };
  }, [options?.defaultCountdownSeconds]);

  // 30-Second Countdown timer
  useEffect(() => {
    if (!pendingApproval) return;

    const timer = setInterval(() => {
      setRemainingSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          deny('timeout');
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [pendingApproval, deny]);

  // Keyboard navigation: Enter to approve, Escape to deny
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!pendingRef.current) return;

      if (e.key === 'Enter') {
        e.preventDefault();
        approve('once');
      } else if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        deny('cancelled_by_user');
      }
    };

    window.addEventListener('keydown', handleKeyDown, true);
    return () => window.removeEventListener('keydown', handleKeyDown, true);
  }, [approve, deny]);

  return {
    pendingApproval,
    hasPendingApproval: pendingApproval !== null,
    remainingSeconds,
    approve,
    deny,
  };
}
