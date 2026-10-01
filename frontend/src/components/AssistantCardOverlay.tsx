import React, { useState, useRef, useEffect } from 'react';
import { useChatStream, useVoiceEngine, useApprovals, useOrbState, useOverlay } from '../hooks';
import { tokens } from '../tokens';
import { PetCompanion } from './PetCompanion';
import { useCharacterState } from '../hooks/useCharacterState';

export interface AssistantCardOverlayProps {
  onSwitchToCockpit?: () => void;
  onOpenSettings?: () => void;
}

const SUGGESTION_CHIPS = [
  { label: '📋 Summarize clipboard', prompt: 'Summarize the contents of my clipboard.' },
  { label: "🖥️ What's on screen?", prompt: 'List all open windows and what is on my screen.' },
  { label: '🔍 Search docs', prompt: 'Search my indexed documents for recent project notes.' },
  { label: '🧹 Clean temp files', prompt: 'Inspect and clean temporary cache files.' },
  { label: '⏱️ 25m focus timer', prompt: 'Schedule a reminder for 25 minutes from now: Focus session finished.' },
  { label: '💻 Inspect VS Code', prompt: 'Find the active Visual Studio Code window.' },
];

export const AssistantCardOverlay: React.FC<AssistantCardOverlayProps> = ({
  onSwitchToCockpit,
  onOpenSettings,
}) => {
  const overlay = useOverlay(true, 'compact');
  const chat = useChatStream();
  const voice = useVoiceEngine({
    onSpeechRecognized: (transcript) => {
      chat.sendMessage(transcript);
    },
  });
  const approvals = useApprovals({
    onApprovalArrive: () => {
      // Auto-bring overlay forward if pending
    },
  });
  const orb = useOrbState({
    hasPendingApproval: approvals.hasPendingApproval,
    isStreaming: chat.isStreaming,
    activeToolCallsCount: chat.activeToolCalls.length,
  });

  const [inputVal, setInputVal] = useState('');
  const inputRef = useRef<HTMLInputElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Character Embodiment state
  const charState = useCharacterState({
    orbState: orb.orbState,
    isListening: voice.isListening,
    isSpeaking: voice.isSpeaking,
    isStreaming: chat.isStreaming,
    hasPendingApproval: approvals.hasPendingApproval,
    activeToolCallsCount: chat.activeToolCalls.length,
    audioLevel: voice.audioLevel,
  });

  // Auto-scroll response stream
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [chat.streamingContent, chat.messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim()) return;
    chat.sendMessage(inputVal);
    setInputVal('');
  };

  const handleChipClick = (prompt: string) => {
    chat.sendMessage(prompt);
  };

  // If user switched to pure floating embodied character mode
  if (overlay.mode === 'pet') {
    return (
      <PetCompanion
        orbState={orb.orbState}
        isListening={voice.isListening}
        isSpeaking={voice.isSpeaking}
        isStreaming={chat.isStreaming}
        audioLevel={voice.audioLevel}
        activeSpeechSnippet={chat.streamingContent || chat.messages[chat.messages.length - 1]?.content}
        hasPendingApproval={approvals.hasPendingApproval}
        pendingApproval={approvals.pendingApproval}
        remainingSeconds={approvals.remainingSeconds}
        onApprove={approvals.approve}
        onDeny={approvals.deny}
        activeToolCallsCount={chat.activeToolCalls.length}
        error={chat.error}
        onExpand={() => overlay.setMode('compact')}
        onToggleVoice={voice.toggleListening}
      />
    );
  }

  const latestMessage = chat.messages[chat.messages.length - 1];

  return (
    <div
      id="niko-assistant-card-hud"
      style={{
        position: 'fixed',
        bottom: '24px',
        left: '50%',
        transform: 'translateX(-50%)',
        width: 'calc(100% - 48px)',
        maxWidth: '680px',
        backgroundColor: 'rgba(15, 23, 42, 0.92)',
        backdropFilter: 'blur(28px) saturate(180%)',
        WebkitBackdropFilter: 'blur(28px) saturate(180%)',
        border: '1.5px solid rgba(255, 255, 255, 0.14)',
        borderRadius: '28px',
        boxShadow: '0 24px 64px -8px rgba(0, 0, 0, 0.8), 0 0 32px rgba(56, 189, 248, 0.12)',
        color: tokens.colors.textPrimary,
        fontFamily: tokens.typography.fontSans,
        padding: '16px 20px',
        zIndex: 99998,
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        transition: 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
      }}
    >
      {/* Top Header & Miniature Embodied Companion Peek */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingBottom: '8px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        }}
      >
        {/* Left: NIKO Identity + Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Animated Mini Avatar Glow Indicator */}
          <div
            style={{
              width: '28px',
              height: '28px',
              borderRadius: '50%',
              backgroundColor: '#6B1724',
              border: `1.5px solid ${tokens.colors.accent}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#FDE68A',
              fontWeight: 'bold',
              fontSize: '12px',
              boxShadow: `0 0 10px ${tokens.colors.accent}66`,
            }}
          >
            N
          </div>
          <div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#F8FAFC', display: 'flex', alignItems: 'center', gap: '6px' }}>
              NIKO AI
              <span
                style={{
                  fontSize: '10px',
                  fontFamily: tokens.typography.fontMono,
                  color: tokens.colors.accent,
                  background: 'rgba(56, 189, 248, 0.12)',
                  padding: '1px 6px',
                  borderRadius: '10px',
                }}
              >
                {charState.semanticState.replace('ASSISTANT_', '')}
              </span>
            </div>
          </div>
        </div>

        {/* Right: Quick Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Switch to Floating Embodied Character Mode */}
          <button
            type="button"
            onClick={() => overlay.setMode('pet')}
            style={{
              background: 'rgba(255, 255, 255, 0.06)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: tokens.radii.full,
              padding: '4px 10px',
              fontSize: '11px',
              color: '#E2E8F0',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              transition: 'background 0.15s ease',
            }}
            title="Switch to Desktop Character Mode"
          >
            <span>🧍</span> Character Mode
          </button>

          {/* Expand to Cockpit */}
          {onSwitchToCockpit && (
            <button
              type="button"
              onClick={onSwitchToCockpit}
              style={{
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                borderRadius: '50%',
                width: '26px',
                height: '26px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#94A3B8',
                cursor: 'pointer',
              }}
              title="Expand Full Dashboard"
            >
              ⤢
            </button>
          )}

          {/* Settings */}
          {onOpenSettings && (
            <button
              type="button"
              onClick={onOpenSettings}
              style={{
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                borderRadius: '50%',
                width: '26px',
                height: '26px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#94A3B8',
                cursor: 'pointer',
              }}
              title="Open Settings"
            >
              ⚙
            </button>
          )}
        </div>
      </div>

      {/* HITL Pending Approval Dialog Banner (If Active) */}
      {approvals.hasPendingApproval && approvals.pendingApproval && (
        <div
          style={{
            backgroundColor: 'rgba(245, 158, 11, 0.15)',
            border: '1.5px solid #F59E0B',
            borderRadius: '16px',
            padding: '12px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#FBBF24' }}>
              ⚠️ Action Permission Required: {approvals.pendingApproval.skillName}
            </span>
          </div>
          <div style={{ fontSize: '11px', color: '#CBD5E1', fontFamily: tokens.typography.fontMono }}>
            {JSON.stringify(approvals.pendingApproval.arguments, null, 2)}
          </div>
          <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
            <button
              type="button"
              onClick={() => approvals.approve()}
              style={{
                backgroundColor: '#10B981',
                color: '#0F172A',
                border: 'none',
                borderRadius: '8px',
                padding: '6px 14px',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Approve & Execute
            </button>
            <button
              type="button"
              onClick={() => approvals.deny()}
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.2)',
                color: '#EF4444',
                border: '1px solid #EF4444',
                borderRadius: '8px',
                padding: '6px 14px',
                fontSize: '12px',
                cursor: 'pointer',
              }}
            >
              Deny
            </button>
          </div>
        </div>
      )}

      {/* Active Streaming / Response Area (if messages exist or streaming) */}
      {(chat.streamingContent || latestMessage) && (
        <div
          ref={scrollRef}
          style={{
            maxHeight: '180px',
            overflowY: 'auto',
            padding: '8px 12px',
            backgroundColor: 'rgba(0, 0, 0, 0.25)',
            borderRadius: '14px',
            fontSize: '13px',
            lineHeight: '1.45',
            color: '#F1F5F9',
          }}
        >
          {chat.isStreaming ? (
            <div>
              <div style={{ color: tokens.colors.accent, fontSize: '11px', marginBottom: '4px', fontWeight: 600 }}>
                Thinking & Answering...
              </div>
              <div>{chat.streamingContent}</div>
            </div>
          ) : (
            <div>{latestMessage?.content}</div>
          )}
        </div>
      )}

      {/* Active Tool Executions Badges */}
      {chat.activeToolCalls.length > 0 && (
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {chat.activeToolCalls.map((tc) => (
            <div
              key={tc.id}
              style={{
                background: 'rgba(52, 211, 153, 0.15)',
                border: '1px solid #34D399',
                borderRadius: '12px',
                padding: '3px 8px',
                fontSize: '11px',
                color: '#34D399',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <span>⚡</span> {tc.name}...
            </div>
          ))}
        </div>
      )}

      {/* Suggestion Chips Horizontal Bar */}
      <div
        style={{
          display: 'flex',
          gap: '8px',
          overflowX: 'auto',
          paddingBottom: '4px',
          scrollbarWidth: 'none',
        }}
      >
        {SUGGESTION_CHIPS.map((chip, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => handleChipClick(chip.prompt)}
            style={{
              background: 'rgba(30, 41, 59, 0.7)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: tokens.radii.full,
              padding: '6px 14px',
              fontSize: '12px',
              color: '#CBD5E1',
              whiteSpace: 'nowrap',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(56, 189, 248, 0.2)';
              e.currentTarget.style.borderColor = tokens.colors.accent;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(30, 41, 59, 0.7)';
              e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.12)';
            }}
          >
            {chip.label}
          </button>
        ))}
      </div>

      {/* Unified Input Pill & Voice Waveform */}
      <form
        onSubmit={handleSubmit}
        style={{
          display: 'flex',
          alignItems: 'center',
          backgroundColor: 'rgba(30, 41, 59, 0.85)',
          border: '1.5px solid rgba(255, 255, 255, 0.16)',
          borderRadius: tokens.radii.full,
          padding: '6px 8px 6px 16px',
          gap: '10px',
        }}
      >
        <input
          ref={inputRef}
          type="text"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          placeholder="Ask NIKO anything or speak..."
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: '#F8FAFC',
            fontSize: '13px',
          }}
        />

        {/* Voice Waveform Activity / Mic Button */}
        <button
          type="button"
          onClick={voice.toggleListening}
          style={{
            backgroundColor: voice.isListening ? '#38BDF8' : 'rgba(51, 65, 85, 0.8)',
            border: 'none',
            borderRadius: '50%',
            width: '34px',
            height: '34px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: voice.isListening ? '#0F172A' : '#E2E8F0',
            cursor: 'pointer',
            transition: 'transform 0.15s ease, background-color 0.2s ease',
            transform: voice.isListening ? `scale(${1 + Math.min(voice.audioLevel * 0.5, 0.3)})` : 'scale(1)',
          }}
          title={voice.isListening ? 'Mute Mic' : 'Activate Voice Mic'}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="22" />
          </svg>
        </button>

        {/* Send Button */}
        <button
          type="submit"
          disabled={!inputVal.trim()}
          style={{
            backgroundColor: inputVal.trim() ? tokens.colors.accent : 'transparent',
            border: 'none',
            borderRadius: '50%',
            width: '34px',
            height: '34px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: inputVal.trim() ? '#0F172A' : '#64748B',
            cursor: inputVal.trim() ? 'pointer' : 'default',
            transition: 'background-color 0.15s ease',
          }}
          title="Send message"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </form>
    </div>
  );
};
