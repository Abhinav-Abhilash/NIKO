import React, { useState, useEffect, useRef, useCallback } from 'react';
import { SpritePlayer } from './SpritePlayer';
import { PetSettingsModal } from './PetSettingsModal';
import { loadPetSettings, type PetSettings } from '../services/petSettings';
import { useApprovals } from '../hooks/useApprovals';
import { useChatStream } from '../hooks/useChatStream';
import { useProviderStatus } from '../hooks/useProviderStatus';
import { useOrbState } from '../hooks/useOrbState';
import { useSpritePetBehavior } from '../hooks/useSpritePetBehavior';
import { soundService } from '../services/soundService';

export interface DesktopPetProps {
  className?: string;
  style?: React.CSSProperties;
}

export const DesktopPet: React.FC<DesktopPetProps> = ({ className = '', style = {} }) => {
  const [settings, setSettings] = useState<PetSettings>(() => loadPetSettings());
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [manualStateOverride, setManualStateOverride] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isInputOpen, setIsInputOpen] = useState(false);
  const [inputText, setInputText] = useState('');
  const inlineInputRef = useRef<HTMLInputElement | null>(null);

  // 1. Backend Hooks Integration
  const approvals = useApprovals();
  const chat = useChatStream();
  const provider = useProviderStatus();
  const orb = useOrbState({
    hasPendingApproval: approvals.hasPendingApproval,
    isStreaming: chat.isStreaming,
    activeToolCallsCount: chat.activeToolCalls.length,
  });

  // 2. Behavioral State Mapping & Local Inactivity / Reactions
  const behavior = useSpritePetBehavior({
    hasPendingApproval: approvals.hasPendingApproval,
    error: chat.error,
    isCoolingDown: provider.isCoolingDown,
    activeToolCallsCount: chat.activeToolCalls.length,
    orbState: orb.orbState,
    isStreaming: chat.isStreaming,
    isSpeaking: false,
    inactivityTimeoutMs: settings.inactivityTimeoutMs,
    manualStateOverride,
    onWakeUp: () => {
      // Optional sound on wake
      if (settings.soundEnabled) {
        soundService.playSound('wake');
      }
    },
  });

  // Auto-focus approval card or play sound on arrival
  const approvalCardRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (approvals.hasPendingApproval && approvals.pendingApproval) {
      if (settings.soundEnabled) {
        soundService.playSound('approval');
      }
      const timer = setTimeout(() => {
        approvalCardRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [approvals.hasPendingApproval, approvals.pendingApproval, settings.soundEnabled]);

  // Dragging support via Tauri startDragging
  const handlePointerDown = async (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return; // Left click only for dragging
    setIsDragging(true);

    try {
      const { getCurrentWindow } = await import('@tauri-apps/api/window');
      const win = getCurrentWindow();
      await win.startDragging();
    } catch {
      // Non-Tauri fallback
    }
  };

  const handlePointerUp = () => {
    setIsDragging(false);
  };

  useEffect(() => {
    const onGlobalMouseUp = () => setIsDragging(false);
    window.addEventListener('mouseup', onGlobalMouseUp);
    return () => window.removeEventListener('mouseup', onGlobalMouseUp);
  }, []);

  // Click on Pet -> Play Reaction (with cooldown) or toggle inline input
  const handlePetClick = (e: React.MouseEvent<HTMLDivElement>) => {
    e.stopPropagation();
    const reaction = behavior.handleClick();

    if (reaction && settings.soundEnabled) {
      soundService.playSound('click');
    }

    // Double click or click when awake toggles chat input
    if (e.detail === 2) {
      setIsInputOpen((prev) => !prev);
    }
  };

  // Right-click opens Pet Settings Menu
  const handleContextMenu = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsSettingsOpen(true);
  };

  // Reset window position to bottom-right above taskbar
  const handleResetPosition = useCallback(async () => {
    try {
      const { getCurrentWindow, currentMonitor } = await import('@tauri-apps/api/window');
      const win = getCurrentWindow();
      const monitor = await currentMonitor();
      if (monitor) {
        const factor = monitor.scaleFactor || 1;
        const screenW = monitor.size.width;
        const screenH = monitor.size.height;
        const winW = 220 * factor;
        const winH = 260 * factor;
        const marginX = 32 * factor;
        const marginY = 72 * factor;
        const posX = Math.round(screenW - winW - marginX);
        const posY = Math.round(screenH - winH - marginY);

        const { PhysicalPosition } = await import('@tauri-apps/api/dpi');
        await win.setPosition(new PhysicalPosition(posX, posY));
      }
    } catch (err) {
      console.warn('[DesktopPet] Unable to reset Tauri window position:', err);
    }
  }, []);

  const handleSendInline = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    chat.sendMessage(inputText.trim());
    setInputText('');
    setIsInputOpen(false);
  };

  return (
    <div
      id="niko-desktop-pet-root"
      data-testid="niko-desktop-pet-root"
      data-tauri-drag-region
      className={`niko-desktop-pet-wrapper ${className}`}
      onContextMenu={handleContextMenu}
      style={{
        width: '100vw',
        height: '100vh',
        margin: 0,
        padding: 0,
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
        background: 'transparent',
        userSelect: 'none',
        WebkitUserSelect: 'none',
        overflow: 'hidden',
        pointerEvents: 'auto',
        ...style,
      }}
    >
      {/* Sprite Character Player */}
      <div
        data-tauri-drag-region
        style={{
          position: 'relative',
          cursor: isDragging ? 'grabbing' : 'grab',
          filter: isDragging
            ? 'drop-shadow(0 16px 24px rgba(0, 0, 0, 0.6)) scale(1.02)'
            : 'drop-shadow(0 8px 16px rgba(0, 0, 0, 0.38))',
          transition: 'filter 0.2s ease, transform 0.2s ease',
        }}
        title="NIKO Desktop Pet (Drag to move, Right-Click for Settings, Double-Click to Chat)"
      >
        <SpritePlayer
          data-testid="desktop-pet-sprite-player"
          state={behavior.activeState}
          direction={behavior.direction}
          sizeScale={settings.sizeScale}
          onClick={handlePetClick}
          onPointerDown={handlePointerDown}
          onPointerUp={handlePointerUp}
        />
      </div>

      {/* Quick Approval Overlay Card */}
      {approvals.hasPendingApproval && approvals.pendingApproval && (
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
              if (settings.soundEnabled) soundService.playSound('click');
              approvals.approve('once');
            } else if (e.key === 'Escape') {
              e.preventDefault();
              if (settings.soundEnabled) soundService.playSound('click');
              approvals.deny('denied_by_user');
            }
          }}
          style={{
            position: 'fixed',
            bottom: '12px',
            left: '12px',
            right: '12px',
            backgroundColor: 'rgba(15, 23, 42, 0.96)',
            backdropFilter: 'blur(20px)',
            WebkitBackdropFilter: 'blur(20px)',
            border: '1.5px solid #F59E0B',
            borderRadius: '14px',
            padding: '12px',
            boxShadow: '0 16px 36px rgba(0, 0, 0, 0.75), 0 0 20px rgba(245, 158, 11, 0.3)',
            zIndex: 100002,
            color: '#F8FAFC',
            fontFamily: 'Inter, system-ui, sans-serif',
            outline: 'none',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontWeight: 700, fontSize: '11px', color: '#FCD34D', textTransform: 'uppercase' }}>
              ⚠️ Permission Required
            </span>
            <span
              style={{
                fontFamily: 'monospace',
                fontWeight: 700,
                fontSize: '11px',
                color: '#FBBF24',
                backgroundColor: 'rgba(245, 158, 11, 0.2)',
                padding: '2px 6px',
                borderRadius: '6px',
              }}
            >
              {approvals.remainingSeconds}s
            </span>
          </div>

          <div style={{ fontSize: '12px', marginBottom: '10px', color: '#E2E8F0', fontWeight: 600 }}>
            Can I execute {approvals.pendingApproval.skillName}?
          </div>

          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
            <button
              type="button"
              data-testid="pet-deny-btn"
              onClick={() => {
                if (settings.soundEnabled) soundService.playSound('click');
                approvals.deny('denied_by_user');
              }}
              style={{
                padding: '4px 10px',
                fontSize: '11px',
                fontWeight: 600,
                backgroundColor: 'rgba(239, 68, 68, 0.2)',
                color: '#F87171',
                border: '1px solid rgba(239, 68, 68, 0.4)',
                borderRadius: '6px',
                cursor: 'pointer',
              }}
            >
              No (Esc)
            </button>
            <button
              type="button"
              data-testid="pet-approve-btn"
              onClick={() => {
                if (settings.soundEnabled) soundService.playSound('click');
                approvals.approve('once');
              }}
              style={{
                padding: '4px 12px',
                fontSize: '11px',
                fontWeight: 700,
                backgroundColor: '#D97706',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
              }}
            >
              Yes (Enter)
            </button>
          </div>
        </div>
      )}

      {/* Inline Click-to-Type Chat Input */}
      {isInputOpen && (
        <form
          data-testid="pet-inline-chat-form"
          onSubmit={handleSendInline}
          style={{
            position: 'fixed',
            bottom: '10px',
            left: '10px',
            right: '10px',
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            border: '1.5px solid rgba(56, 189, 248, 0.5)',
            borderRadius: '12px',
            padding: '6px 10px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            zIndex: 100001,
          }}
        >
          <input
            ref={inlineInputRef}
            data-testid="pet-inline-chat-input"
            type="text"
            value={inputText}
            autoFocus
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                e.preventDefault();
                setIsInputOpen(false);
              }
            }}
            placeholder="Ask NIKO..."
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: '#F8FAFC',
              fontSize: '11px',
              fontFamily: 'Inter, system-ui, sans-serif',
            }}
          />
          <button
            type="submit"
            disabled={!inputText.trim()}
            style={{
              padding: '3px 8px',
              backgroundColor: inputText.trim() ? '#38BDF8' : 'rgba(255, 255, 255, 0.1)',
              color: inputText.trim() ? '#0F172A' : '#64748B',
              border: 'none',
              borderRadius: '6px',
              fontSize: '10px',
              fontWeight: 700,
              cursor: inputText.trim() ? 'pointer' : 'default',
            }}
          >
            Send
          </button>
        </form>
      )}

      {/* Settings Modal */}
      <PetSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        onUpdateSettings={setSettings}
        onResetPosition={handleResetPosition}
        onTriggerSleepNow={() => behavior.triggerSleepNow()}
        manualStateOverride={manualStateOverride}
        onSetManualState={setManualStateOverride}
      />
    </div>
  );
};

export default DesktopPet;
