import React, { useState } from 'react';
import {
  useOverlay,
  useChatStream,
  useApprovals,
  useOrbState,
  useProviderStatus,
  useVoiceEngine,
} from '../hooks';
import { tokens } from '../tokens';
import { PetCompanion } from './PetCompanion';

/**
 * Cyberpunk / Windows 11 Acrylic HUD Overlay.
 * Implements high-agency terminal aesthetics with glassmorphic depth,
 * dynamic reactor core state visualization, and least-latency interaction.
 */
export const PlaceholderOverlay: React.FC = () => {
  const overlay = useOverlay(true, 'compact');
  const chat = useChatStream();
  const voice = useVoiceEngine({
    onSpeechRecognized: (transcript) => {
      chat.sendMessage(transcript);
    },
  });
  const approvals = useApprovals({
    onApprovalArrive: () => {
      overlay.show('approval');
    },
  });
  const orb = useOrbState({
    hasPendingApproval: approvals.hasPendingApproval,
    isStreaming: chat.isStreaming,
    activeToolCallsCount: chat.activeToolCalls.length,
  });
  const providers = useProviderStatus();

  const [inputVal, setInputVal] = useState('');

  if (!overlay.isVisible) {
    return (
      <div id="niko-overlay-hidden" style={{ display: 'none' }}>
        {/* Render paused while hidden */}
      </div>
    );
  }

  if (overlay.mode === 'pet') {
    return (
      <PetCompanion
        orbState={orb.orbState}
        isListening={voice.isListening}
        isSpeaking={voice.isSpeaking}
        isBargeInActive={voice.isBargeInActive}
        audioLevel={voice.audioLevel}
        activeSpeechSnippet={voice.currentSentence || undefined}
        onExpand={() => overlay.setMode('compact')}
        onToggleVoice={voice.toggleListening}
        onBargeIn={voice.triggerBargeIn}
      />
    );
  }

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim()) return;
    chat.sendMessage(inputVal);
    setInputVal('');
  };

  // Determine core glow color based on orbState
  const getCoreColor = () => {
    switch (orb.orbState) {
      case 'thinking':
        return tokens.colors.coreThinking;
      case 'acting':
        return tokens.colors.coreActing;
      case 'confirm':
        return tokens.colors.coreConfirm;
      case 'idle':
      default:
        return tokens.colors.coreIdle;
    }
  };


  const coreColor = getCoreColor();

  return (
    <div
      id="niko-overlay-container"
      style={{
        width: 'calc(100% - 32px)',
        maxWidth: overlay.mode === 'expanded' ? '820px' : '560px',
        margin: '24px auto',
        backgroundColor: 'rgba(11, 14, 18, 0.88)',
        backdropFilter: 'blur(24px) saturate(180%)',
        WebkitBackdropFilter: 'blur(24px) saturate(180%)',
        color: tokens.colors.textPrimary,
        border: '1px solid rgba(255, 255, 255, 0.12)',
        borderRadius: tokens.radii.lg,
        boxShadow: '0 24px 48px -12px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(255, 255, 255, 0.06)',
        fontFamily: tokens.typography.fontSans,
        padding: '16px 20px',
        position: 'relative',
        transition: 'max-width 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
        overflow: 'hidden',
      }}
    >
      {/* Top subtle hairline glow */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: '10%',
          right: '10%',
          height: '1px',
          background: `linear-gradient(90deg, transparent, ${coreColor}88, transparent)`,
        }}
      />

      {/* Header Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '14px',
          paddingBottom: '10px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        }}
      >
        {/* Reactor Core Icon + Status Label */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              position: 'relative',
              width: '24px',
              height: '24px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {/* Spinning Concentric Reticle */}
            <svg
              style={{
                width: '24px',
                height: '24px',
                animation: chat.isStreaming ? 'spin 3s linear infinite' : 'none',
              }}
              viewBox="0 0 32 32"
            >
              <circle
                cx="16"
                cy="16"
                r="13"
                fill="none"
                stroke={coreColor}
                strokeWidth="1.5"
                strokeDasharray="4 4"
                opacity="0.6"
              />
            </svg>
            {/* Glowing Core Dot */}
            <div
              style={{
                position: 'absolute',
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: coreColor,
                boxShadow: `0 0 10px ${coreColor}`,
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span
              style={{
                fontFamily: tokens.typography.fontMono,
                fontSize: tokens.typography.sizeXs,
                letterSpacing: '0.08em',
                fontWeight: 600,
                color: tokens.colors.textSecondary,
              }}
            >
              NIKO (State: <strong style={{ color: coreColor }}>{orb.orbState}</strong>)
            </span>
          </div>
        </div>

        {/* Window & View Control Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Full-Duplex Voice Toggle */}
          <button
            type="button"
            onClick={voice.toggleListening}
            style={{
              background: voice.isListening ? 'rgba(56, 189, 248, 0.15)' : 'rgba(255, 255, 255, 0.06)',
              color: voice.isListening ? '#38bdf8' : tokens.colors.textSecondary,
              border: `1px solid ${voice.isListening ? '#0284c7' : 'rgba(255, 255, 255, 0.1)'}`,
              borderRadius: tokens.radii.sm,
              padding: '4px 10px',
              fontSize: '11px',
              fontFamily: tokens.typography.fontMono,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              transition: 'all 0.15s ease',
            }}
            title={voice.isListening ? 'Mute Full-Duplex Voice' : 'Enable Full-Duplex Voice (VAD & Barge-In)'}
          >
            <span
              style={{
                display: 'inline-block',
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: voice.isListening ? '#38bdf8' : 'rgba(255,255,255,0.4)',
                boxShadow: voice.isListening ? '0 0 6px #38bdf8' : 'none',
              }}
            />
            {voice.isListening ? 'Voice ON' : 'Voice'}
          </button>

          {/* Floating Pet Mode Toggle */}
          <button
            type="button"
            onClick={() => overlay.setMode('pet')}
            style={{
              background: 'rgba(168, 85, 247, 0.12)',
              color: '#c084fc',
              border: '1px solid rgba(168, 85, 247, 0.3)',
              borderRadius: tokens.radii.sm,
              padding: '4px 10px',
              fontSize: '11px',
              fontFamily: tokens.typography.fontMono,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
            title="Switch to Floating Desktop Pet Companion Mode"
          >
            Pet HUD
          </button>

          <button
            type="button"
            onClick={() => overlay.setMode(overlay.mode === 'compact' ? 'expanded' : 'compact')}
            style={{
              background: 'rgba(255, 255, 255, 0.06)',
              color: tokens.colors.textSecondary,
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: tokens.radii.sm,
              padding: '4px 10px',
              fontSize: '11px',
              fontFamily: tokens.typography.fontMono,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            {overlay.mode === 'compact' ? 'Expand' : 'Compact'}
          </button>
          <button
            type="button"
            onClick={overlay.hide}
            style={{
              background: 'rgba(239, 68, 68, 0.08)',
              color: '#f87171',
              border: '1px solid rgba(239, 68, 68, 0.25)',
              borderRadius: tokens.radii.sm,
              padding: '4px 10px',
              fontSize: '11px',
              fontFamily: tokens.typography.fontMono,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            Hide (Esc)
          </button>
        </div>
      </div>

      {/* Provider Cooldown Banner */}
      {providers.isCoolingDown && (
        <div
          style={{
            background: 'rgba(245, 158, 11, 0.12)',
            border: '1px solid rgba(245, 158, 11, 0.35)',
            color: '#fbbf24',
            padding: '8px 12px',
            marginBottom: '12px',
            borderRadius: tokens.radii.sm,
            fontSize: tokens.typography.sizeSm,
            fontFamily: tokens.typography.fontMono,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#f59e0b' }} />
          <span>
            <strong>COOLDOWN:</strong> {providers.cooldownMessage} (reset in {providers.shortestResetSeconds}s)
          </span>
        </div>
      )}

      {/* Active Approval Modal / Dialog */}
      {approvals.hasPendingApproval && approvals.pendingApproval && (
        <div
          id="niko-approval-card"
          style={{
            border: '1px solid rgba(245, 158, 11, 0.65)',
            backgroundColor: 'rgba(30, 20, 10, 0.92)',
            borderRadius: tokens.radii.md,
            padding: '14px 16px',
            marginBottom: '14px',
            boxShadow: '0 8px 24px rgba(245, 158, 11, 0.15)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <h4
              style={{
                margin: 0,
                color: '#fbbf24',
                fontSize: tokens.typography.sizeSm,
                fontFamily: tokens.typography.fontMono,
                letterSpacing: '0.04em',
                fontWeight: 700,
              }}
            >
              CONFIRMATION REQUIRED ({approvals.remainingSeconds}s)
            </h4>
            <span
              style={{
                fontSize: '10px',
                fontFamily: tokens.typography.fontMono,
                background: 'rgba(245, 158, 11, 0.2)',
                color: '#fbbf24',
                padding: '2px 6px',
                borderRadius: tokens.radii.sm,
              }}
            >
              ACTION_CONFIRM
            </span>
          </div>

          <p style={{ margin: '4px 0', fontSize: tokens.typography.sizeSm }}>
            Skill: <strong style={{ color: '#fef08a' }}>{approvals.pendingApproval.skillName}</strong>
          </p>
          <p style={{ margin: '4px 0', fontSize: '12px' }}>
            Arguments:{' '}
            <code
              style={{
                fontFamily: tokens.typography.fontMono,
                background: 'rgba(0, 0, 0, 0.4)',
                padding: '2px 6px',
                borderRadius: '3px',
                color: '#e2e8f0',
              }}
            >
              {JSON.stringify(approvals.pendingApproval.arguments)}
            </code>
          </p>
          <p style={{ margin: '4px 0', fontSize: '11px', color: '#94a3b8' }}>
            Provenance: {approvals.pendingApproval.provenance}
          </p>

          <div style={{ marginTop: '12px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              id="approve-once-btn"
              type="button"
              onClick={() => approvals.approve('once')}
              style={{
                background: '#f59e0b',
                color: '#000000',
                border: 'none',
                borderRadius: tokens.radii.sm,
                padding: '6px 12px',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'opacity 0.15s ease',
              }}
            >
              Approve (Enter)
            </button>
            <button
              id="approve-session-btn"
              type="button"
              onClick={() => approvals.approve('session')}
              style={{
                background: 'rgba(245, 158, 11, 0.15)',
                color: '#fbbf24',
                border: '1px solid rgba(245, 158, 11, 0.35)',
                borderRadius: tokens.radii.sm,
                padding: '6px 12px',
                fontSize: '12px',
                cursor: 'pointer',
              }}
            >
              Allow for this session
            </button>
            <button
              id="approve-always-btn"
              type="button"
              onClick={() => approvals.approve('always')}
              style={{
                background: 'rgba(255, 255, 255, 0.08)',
                color: tokens.colors.textPrimary,
                border: '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: tokens.radii.sm,
                padding: '6px 12px',
                fontSize: '12px',
                cursor: 'pointer',
              }}
            >
              Always allow this action
            </button>
            <button
              id="deny-btn"
              type="button"
              onClick={() => approvals.deny('denied_by_user')}
              style={{
                background: 'rgba(239, 68, 68, 0.15)',
                color: '#f87171',
                border: '1px solid rgba(239, 68, 68, 0.35)',
                borderRadius: tokens.radii.sm,
                padding: '6px 12px',
                fontSize: '12px',
                cursor: 'pointer',
              }}
            >
              Deny (Esc)
            </button>
          </div>
        </div>
      )}

      {/* Message Stream */}
      <div
        id="niko-message-list"
        style={{
          maxHeight: overlay.mode === 'expanded' ? '420px' : '220px',
          overflowY: 'auto',
          marginBottom: '14px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          paddingBottom: '12px',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
        }}
      >
        {chat.messages.length === 0 ? (
          <div
            style={{
              color: tokens.colors.textMuted,
              fontStyle: 'italic',
              fontSize: tokens.typography.sizeSm,
              padding: '12px 0',
              textAlign: 'center',
            }}
          >
            NIKO ready. Ask a question or command an OS action below.
          </div>
        ) : (
          chat.messages.map((m) => (
            <div
              key={m.id}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                background: m.role === 'user' ? 'rgba(56, 189, 248, 0.05)' : 'rgba(255, 255, 255, 0.02)',
                border: m.role === 'user' ? '1px solid rgba(56, 189, 248, 0.15)' : '1px solid rgba(255, 255, 255, 0.05)',
                borderRadius: tokens.radii.md,
                padding: '8px 12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span
                  style={{
                    fontFamily: tokens.typography.fontMono,
                    fontSize: '10px',
                    fontWeight: 700,
                    letterSpacing: '0.05em',
                    color: m.role === 'user' ? tokens.colors.accent : tokens.colors.coreThinking,
                  }}
                >
                  {m.role === 'user' ? 'OPERATOR' : 'NIKO'}
                </span>
              </div>
              <span style={{ fontSize: tokens.typography.sizeSm, lineHeight: '1.45', whiteSpace: 'pre-wrap' }}>
                {m.content}
              </span>

              {m.toolCalls && m.toolCalls.length > 0 && (
                <div style={{ marginTop: '4px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {m.toolCalls.map((tc) => (
                    <div
                      key={tc.id}
                      style={{
                        fontFamily: tokens.typography.fontMono,
                        fontSize: '11px',
                        background: 'rgba(34, 197, 94, 0.08)',
                        border: '1px solid rgba(34, 197, 94, 0.25)',
                        color: '#4ade80',
                        borderRadius: tokens.radii.sm,
                        padding: '4px 8px',
                      }}
                    >
                      [Tool: {tc.name} ({tc.status})]
                      {tc.result !== undefined && <span> -&gt; {JSON.stringify(tc.result)}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Input Bar */}
      <form onSubmit={handleSend} style={{ display: 'flex', gap: '8px', position: 'relative' }}>
        <input
          id="niko-chat-input"
          ref={overlay.inputRef}
          type="text"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          placeholder="Ask NIKO (e.g. what time is it and how's my CPU)..."
          style={{
            flex: 1,
            padding: '10px 14px',
            backgroundColor: 'rgba(0, 0, 0, 0.45)',
            color: tokens.colors.textPrimary,
            border: '1px solid rgba(255, 255, 255, 0.15)',
            borderRadius: tokens.radii.sm,
            fontFamily: tokens.typography.fontMono,
            fontSize: tokens.typography.sizeSm,
            outline: 'none',
            boxShadow: 'inset 0 1px 2px rgba(0, 0, 0, 0.5)',
            transition: 'border-color 0.15s ease',
          }}
          disabled={chat.isStreaming}
        />
        {chat.isStreaming ? (
          <button
            type="button"
            onClick={chat.cancelStream}
            style={{
              padding: '0 16px',
              backgroundColor: 'rgba(239, 68, 68, 0.2)',
              color: '#f87171',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              borderRadius: tokens.radii.sm,
              fontSize: tokens.typography.sizeSm,
              fontFamily: tokens.typography.fontMono,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
        ) : (
          <button
            type="submit"
            id="niko-submit-btn"
            style={{
              padding: '0 18px',
              backgroundColor: tokens.colors.accent,
              color: '#0b0e12',
              border: 'none',
              borderRadius: tokens.radii.sm,
              fontSize: tokens.typography.sizeSm,
              fontFamily: tokens.typography.fontMono,
              fontWeight: 700,
              cursor: 'pointer',
              transition: 'opacity 0.15s ease',
            }}
          >
            Send
          </button>
        )}
      </form>

      {/* Footer Settings & Meta */}
      <div
        style={{
          marginTop: '10px',
          fontSize: '11px',
          color: tokens.colors.textMuted,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={overlay.autoHideOnBlur}
            onChange={(e) => overlay.setAutoHideOnBlur(e.target.checked)}
            style={{ accentColor: tokens.colors.accent }}
          />{' '}
          Auto-hide on blur
        </label>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontFamily: tokens.typography.fontMono }}>Hotkey: Ctrl+Space</span>
          {chat.messages.length > 0 && (
            <button
              type="button"
              onClick={chat.clearMessages}
              style={{
                fontSize: '10px',
                fontFamily: tokens.typography.fontMono,
                color: tokens.colors.textMuted,
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                textDecoration: 'underline',
              }}
            >
              Clear History
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default PlaceholderOverlay;
