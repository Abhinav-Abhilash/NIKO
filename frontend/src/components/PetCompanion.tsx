import React, { useState, useEffect, useRef, useCallback } from 'react';
import { OrbState } from '../hooks/useOrbState';
import { tokens } from '../tokens';

export interface PetCompanionProps {
  orbState: OrbState;
  isListening: boolean;
  isSpeaking: boolean;
  isBargeInActive: boolean;
  audioLevel: number;
  onExpand: () => void;
  onToggleVoice: () => void;
  onBargeIn?: () => void;
}

export const PetCompanion: React.FC<PetCompanionProps> = ({
  orbState,
  isListening,
  isSpeaking,
  isBargeInActive,
  audioLevel,
  onExpand,
  onToggleVoice,
  onBargeIn,
}) => {
  // Load initial position from localStorage or default to bottom-right
  const [position, setPosition] = useState<{ x: number; y: number }>(() => {
    try {
      const saved = localStorage.getItem('niko_pet_pos');
      if (saved) return JSON.parse(saved);
    } catch {
      // fallback
    }
    return { x: window.innerWidth - 120, y: window.innerHeight - 120 };
  });

  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef<{ startX: number; startY: number; posX: number; posY: number }>({
    startX: 0,
    startY: 0,
    posX: 0,
    posY: 0,
  });
  const hasMovedRef = useRef(false);

  // Determine glow color
  const getCoreColor = () => {
    if (isBargeInActive) return '#ef4444';
    switch (orbState) {
      case 'thinking':
        return tokens.colors.coreThinking;
      case 'acting':
        return tokens.colors.coreActing;
      case 'confirm':
        return tokens.colors.coreConfirm;
      case 'idle':
      default:
        return isListening ? '#38bdf8' : tokens.colors.coreIdle;
    }
  };

  const coreColor = getCoreColor();

  const handlePointerDown = (e: React.PointerEvent) => {
    setIsDragging(true);
    hasMovedRef.current = false;
    dragStartRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      posX: position.x,
      posY: position.y,
    };
    if (typeof (e.target as HTMLElement).setPointerCapture === 'function') {
      try {
        (e.target as HTMLElement).setPointerCapture(e.pointerId);
      } catch {
        // ignore
      }
    }
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!isDragging) return;
    const dx = e.clientX - dragStartRef.current.startX;
    const dy = e.clientY - dragStartRef.current.startY;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
      hasMovedRef.current = true;
    }
    const newX = Math.max(10, Math.min(window.innerWidth - 90, dragStartRef.current.posX + dx));
    const newY = Math.max(10, Math.min(window.innerHeight - 90, dragStartRef.current.posY + dy));
    setPosition({ x: newX, y: newY });
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    setIsDragging(false);
    if (typeof (e.target as HTMLElement).releasePointerCapture === 'function') {
      try {
        (e.target as HTMLElement).releasePointerCapture(e.pointerId);
      } catch {
        // ignore
      }
    }
    localStorage.setItem('niko_pet_pos', JSON.stringify(position));

    // If it was a click without dragging, expand to compact HUD
    if (!hasMovedRef.current) {
      onExpand();
    }
  };

  // Adjust position on window resize
  useEffect(() => {
    const handleResize = () => {
      setPosition((curr) => ({
        x: Math.min(curr.x, window.innerWidth - 90),
        y: Math.min(curr.y, window.innerHeight - 90),
      }));
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const scalePulse = 1 + Math.min(audioLevel * 0.4, 0.35);

  return (
    <div
      id="niko-pet-companion"
      style={{
        position: 'fixed',
        left: `${position.x}px`,
        top: `${position.y}px`,
        width: '80px',
        height: '80px',
        zIndex: 99999,
        cursor: isDragging ? 'grabbing' : 'grab',
        userSelect: 'none',
        touchAction: 'none',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      title="NIKO Companion Pet (Click to open HUD, Drag to reposition)"
    >
      {/* Outer Glow Halo */}
      <div
        style={{
          position: 'absolute',
          width: '72px',
          height: '72px',
          borderRadius: '50%',
          backgroundColor: `${coreColor}22`,
          boxShadow: `0 0 24px ${coreColor}66`,
          transform: `scale(${scalePulse})`,
          transition: 'transform 0.1s ease-out, background-color 0.25s ease',
          pointerEvents: 'none',
        }}
      />

      {/* Main Glassmorphic Orb Body */}
      <div
        style={{
          width: '64px',
          height: '64px',
          borderRadius: '50%',
          background: 'rgba(15, 23, 42, 0.85)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          border: `1.5px solid ${coreColor}88`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.6)',
        }}
      >
        {/* Animated Cybernetic Reticle SVG */}
        <svg
          style={{
            position: 'absolute',
            width: '52px',
            height: '52px',
            animation: orbState === 'thinking' || isSpeaking ? 'spin 3s linear infinite' : 'none',
          }}
          viewBox="0 0 52 52"
        >
          <circle
            cx="26"
            cy="26"
            r="22"
            fill="none"
            stroke={coreColor}
            strokeWidth="1.5"
            strokeDasharray={isListening ? '4 2 1 2' : '6 4'}
            opacity="0.75"
          />
          <circle
            cx="26"
            cy="26"
            r="16"
            fill="none"
            stroke={coreColor}
            strokeWidth="1"
            strokeDasharray="2 3"
            opacity="0.45"
          />
        </svg>

        {/* Central Reactor Core Sphere */}
        <div
          style={{
            width: '18px',
            height: '18px',
            borderRadius: '50%',
            backgroundColor: coreColor,
            boxShadow: `0 0 16px ${coreColor}, 0 0 4px #ffffff`,
            transform: `scale(${isSpeaking ? 1.2 : 1})`,
            transition: 'transform 0.15s ease',
          }}
        />

        {/* Quick Voice Mic Action Badge */}
        <button
          type="button"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => {
            e.stopPropagation();
            onToggleVoice();
          }}
          style={{
            position: 'absolute',
            bottom: '-4px',
            right: '-4px',
            width: '24px',
            height: '24px',
            borderRadius: '50%',
            backgroundColor: isListening ? '#38bdf8' : 'rgba(30, 41, 59, 0.95)',
            border: `1px solid ${isListening ? '#0284c7' : 'rgba(255, 255, 255, 0.2)'}`,
            color: isListening ? '#0f172a' : '#94a3b8',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            padding: 0,
            fontSize: '11px',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.4)',
          }}
          title={isListening ? 'Mute Voice Mic' : 'Activate Voice Mic'}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="22" />
          </svg>
        </button>
      </div>

      {/* State label badge */}
      <div
        style={{
          position: 'absolute',
          bottom: '-16px',
          background: 'rgba(15, 23, 42, 0.9)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: tokens.radii.full,
          padding: '1px 6px',
          fontSize: '9px',
          fontFamily: tokens.typography.fontMono,
          color: coreColor,
          letterSpacing: '0.04em',
          pointerEvents: 'none',
          whiteSpace: 'nowrap',
        }}
      >
        {isBargeInActive ? 'BARGE-IN' : isSpeaking ? 'SPEAKING' : orbState.toUpperCase()}
      </div>
    </div>
  );
};
