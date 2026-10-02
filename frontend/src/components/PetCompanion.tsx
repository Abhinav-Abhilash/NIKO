import React, { useRef, useEffect } from 'react';
import type { OrbState } from '../hooks/useOrbState';
import { CharacterAvatar } from './CharacterAvatar';
import { useCharacterState } from '../hooks/useCharacterState';
import { useApprovals, type PendingApproval, type ApprovalPersistence } from '../hooks/useApprovals';
import { soundService } from '../services/soundService';

export interface PetCompanionProps {
  orbState: OrbState;
  isListening: boolean;
  isSpeaking: boolean;
  isStreaming?: boolean;
  isBargeInActive?: boolean;
  audioLevel: number;
  activeSpeechSnippet?: string;
  hasPendingApproval?: boolean;
  pendingApproval?: PendingApproval | null;
  remainingSeconds?: number;
  onApprove?: (persistence?: ApprovalPersistence) => Promise<void> | void;
  onDeny?: (reason?: string) => Promise<void> | void;
  isCoolingDown?: boolean;
  cooldownMessage?: string | null;
  error?: string | null;
  activeToolCallsCount?: number;
  petName?: string;
  onSendMessage?: (content: string) => void;
  onExpand: () => void;
  onToggleVoice: () => void;
  onBargeIn?: () => void;
}

export const PetCompanion: React.FC<PetCompanionProps> = ({
  orbState,
  isListening,
  isSpeaking,
  isStreaming = false,
  audioLevel,
  activeSpeechSnippet,
  hasPendingApproval: propHasPendingApproval,
  pendingApproval: propPendingApproval,
  remainingSeconds: propRemainingSeconds,
  onApprove: propOnApprove,
  onDeny: propOnDeny,
  isCoolingDown = false,
  cooldownMessage,
  error = null,
  activeToolCallsCount = 0,
  petName = 'NIKO',
  onSendMessage,
  onExpand,
  onToggleVoice,
}) => {
  const [isInputOpen, setIsInputOpen] = React.useState(false);
  const [inputText, setInputText] = React.useState('');
  const inlineInputRef = useRef<HTMLInputElement | null>(null);

  // Graceful fallback to shared useApprovals if props are not explicitly supplied
  const fallbackApprovals = useApprovals();
  const hasPendingApproval =
    propHasPendingApproval !== undefined
      ? propHasPendingApproval
      : fallbackApprovals.hasPendingApproval;
  const pendingApproval =
    propPendingApproval !== undefined
      ? propPendingApproval
      : fallbackApprovals.pendingApproval;
  const remainingSeconds =
    propRemainingSeconds !== undefined
      ? propRemainingSeconds
      : fallbackApprovals.remainingSeconds;
  const handleApprove = propOnApprove || fallbackApprovals.approve;
  const handleDeny = propOnDeny || fallbackApprovals.deny;

  const charState = useCharacterState({
    orbState,
    isListening,
    isSpeaking,
    isStreaming,
    hasPendingApproval,
    activeToolCallsCount,
    isCoolingDown,
    cooldownMessage,
    error,
    audioLevel,
  });

  const approvalCardRef = useRef<HTMLDivElement | null>(null);

  // Auto-focus the approval prompt and play approval cue whenever an approval request arrives (ducked if mic/TTS active)
  useEffect(() => {
    if (hasPendingApproval && pendingApproval) {
      soundService.playSound('approval', { isListening, isSpeaking });
      const timer = setTimeout(() => {
        approvalCardRef.current?.focus();
      }, 20);
      return () => clearTimeout(timer);
    }
  }, [hasPendingApproval, pendingApproval, isListening, isSpeaking]);

  useEffect(() => {
    if (isInputOpen) {
      const timer = setTimeout(() => {
        inlineInputRef.current?.focus();
      }, 20);
      return () => clearTimeout(timer);
    }
  }, [isInputOpen]);

  const handlePetClick = () => {
    soundService.playSound('click', { isListening, isSpeaking });
    setIsInputOpen((prev) => !prev);
    onExpand();
  };

  const handleSendInline = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    if (onSendMessage) {
      onSendMessage(inputText.trim());
    }
    setInputText('');
  };

  const handleApproveWithSound = (persistence: ApprovalPersistence = 'once') => {
    soundService.playSound('click', { isListening, isSpeaking });
    handleApprove(persistence);
  };

  const handleDenyWithSound = (reason = 'denied_by_user') => {
    soundService.playSound('click', { isListening, isSpeaking });
    handleDeny(reason);
  };

  // Human-friendly description for approval prompt
  const formatApprovalQuestion = () => {
    if (!pendingApproval) return 'Can I perform this action?';
    const skill = pendingApproval.skillName;
    const args = pendingApproval.arguments || {};
    if (skill === 'open_app' && args.app_name) {
      return `Can I open ${args.app_name}?`;
    }
    if (skill === 'web_search' && args.query) {
      return `Can I search the web for "${args.query}"?`;
    }
    if (skill === 'read_file' && args.file_path) {
      return `Can I read file ${args.file_path}?`;
    }
    if (skill === 'write_file' && args.file_path) {
      return `Can I write to file ${args.file_path}?`;
    }
    return `Can I execute ${skill}?`;
  };

  const inputLeft =
    charState.position.x + 140 > (typeof window !== 'undefined' ? window.innerWidth - 260 : 800)
      ? Math.max(16, charState.position.x - 260)
      : charState.position.x + 140;

  return (
    <div
      id="niko-pet-companion-wrapper"
      data-testid="niko-pet-companion-wrapper"
      style={{
        position: 'fixed',
        inset: 0,
        pointerEvents: 'none',
        zIndex: 99998,
      }}
    >
      {/* Embodied Chibi Character Renderer (clickable & draggable) */}
      <CharacterAvatar
        semanticState={charState.semanticState}
        posture={charState.posture}
        emotion={charState.emotion}
        position={charState.position}
        gaze={charState.gaze}
        isDragging={charState.isDragging}
        isBlinking={charState.isBlinking}
        mouthOpen={charState.mouthOpen}
        isListening={isListening}
        isSpeaking={isSpeaking}
        activeSpeechSnippet={activeSpeechSnippet}
        onPointerDown={charState.startDrag}
        onPointerMove={charState.onDrag}
        onPointerUp={(e) => charState.endDrag(e, handlePetClick)}
        onToggleVoice={onToggleVoice}
        onOpenCardHUD={handlePetClick}
      />

      {/* Click-to-Type Inline Text Input beside Pet Avatar */}
      {isInputOpen && (
        <form
          data-testid="pet-inline-input-wrapper"
          onSubmit={handleSendInline}
          style={{
            position: 'fixed',
            left: `${inputLeft}px`,
            top: `${charState.position.y + 50}px`,
            width: '240px',
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1.5px solid rgba(56, 189, 248, 0.4)',
            borderRadius: '16px',
            padding: '8px 10px',
            boxShadow: '0 12px 32px rgba(0, 0, 0, 0.6), 0 0 16px rgba(56, 189, 248, 0.2)',
            pointerEvents: 'auto',
            zIndex: 100001,
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <input
            ref={inlineInputRef}
            data-testid="pet-inline-input"
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                e.preventDefault();
                setIsInputOpen(false);
              }
            }}
            placeholder={`Ask ${petName}...`}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: '#F8FAFC',
              fontSize: '12px',
              fontFamily: 'Inter, system-ui, sans-serif',
            }}
          />
          <button
            type="submit"
            data-testid="pet-send-btn"
            disabled={!inputText.trim()}
            style={{
              padding: '4px 10px',
              backgroundColor: inputText.trim() ? '#38BDF8' : 'rgba(255, 255, 255, 0.1)',
              color: inputText.trim() ? '#0F172A' : '#64748B',
              border: 'none',
              borderRadius: '10px',
              fontSize: '11px',
              fontWeight: 700,
              cursor: inputText.trim() ? 'pointer' : 'default',
            }}
          >
            Send
          </button>
        </form>
      )}

      {/* Unreachable-Proof Approval Card Prompt Through the Pet */}
      {hasPendingApproval && pendingApproval && (
        <div
          id="niko-pet-approval-card"
          data-testid="pet-approval-prompt"
          role="dialog"
          aria-modal="true"
          aria-label="Permission Confirmation Required"
          tabIndex={0}
          ref={approvalCardRef}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              handleApproveWithSound('once');
            } else if (e.key === 'Escape') {
              e.preventDefault();
              e.stopPropagation();
              handleDenyWithSound('denied_by_user');
            }
          }}
          style={{
            position: 'fixed',
            left: `${Math.max(16, Math.min((typeof window !== 'undefined' ? window.innerWidth : 800) - 340, charState.position.x - 90))}px`,
            top: `${Math.max(16, charState.position.y - 190)}px`,
            width: '320px',
            backgroundColor: 'rgba(15, 23, 42, 0.96)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1.5px solid #F59E0B',
            borderRadius: '16px',
            padding: '16px',
            boxShadow: '0 20px 40px rgba(0, 0, 0, 0.7), 0 0 24px rgba(245, 158, 11, 0.35)',
            pointerEvents: 'auto',
            zIndex: 100002,
            color: '#F8FAFC',
            fontFamily: 'Inter, system-ui, sans-serif',
            outline: 'none',
          }}
        >
          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '18px' }}>⚠️</span>
              <span style={{ fontWeight: 700, fontSize: '12px', letterSpacing: '0.05em', color: '#FCD34D', textTransform: 'uppercase' }}>
                Permission Required
              </span>
            </div>
            <span
              data-testid="pet-approval-countdown"
              style={{
                fontFamily: 'monospace',
                fontWeight: 700,
                fontSize: '11px',
                backgroundColor: 'rgba(245, 158, 11, 0.2)',
                color: '#FBBF24',
                padding: '2px 8px',
                borderRadius: '8px',
                border: '1px solid rgba(245, 158, 11, 0.4)',
              }}
            >
              {remainingSeconds}s
            </span>
          </div>

          {/* Friendly Question through Pet Persona */}
          <div style={{ fontSize: '13px', marginBottom: '8px', color: '#E2E8F0', fontWeight: 600 }}>
            {formatApprovalQuestion()}
          </div>

          {/* Arguments details */}
          {pendingApproval.arguments && Object.keys(pendingApproval.arguments).length > 0 && (
            <div
              style={{
                backgroundColor: 'rgba(2, 6, 23, 0.75)',
                borderRadius: '8px',
                padding: '8px 10px',
                fontSize: '11px',
                fontFamily: 'monospace',
                color: '#94A3B8',
                marginBottom: '12px',
                maxHeight: '60px',
                overflowY: 'auto',
                border: '1px solid rgba(255, 255, 255, 0.08)',
              }}
            >
              <pre style={{ margin: 0 }}>{JSON.stringify(pendingApproval.arguments, null, 2)}</pre>
            </div>
          )}

          {/* Actions: Yes / No buttons */}
          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '6px' }}>
            <button
              type="button"
              data-testid="pet-deny-btn"
              onClick={() => handleDenyWithSound('denied_by_user')}
              style={{
                padding: '6px 14px',
                fontSize: '12px',
                fontWeight: 600,
                backgroundColor: 'rgba(239, 68, 68, 0.15)',
                color: '#F87171',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: '8px',
                cursor: 'pointer',
              }}
            >
              No (Esc)
            </button>
            <button
              type="button"
              data-testid="pet-approve-btn"
              onClick={() => handleApproveWithSound('once')}
              style={{
                padding: '6px 16px',
                fontSize: '12px',
                fontWeight: 700,
                backgroundColor: '#D97706',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                boxShadow: '0 0 12px rgba(217, 119, 6, 0.5)',
              }}
            >
              Yes (Enter)
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
