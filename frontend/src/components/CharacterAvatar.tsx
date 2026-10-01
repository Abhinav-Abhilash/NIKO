import React, { useState } from 'react';
import {
  AssistantSemanticState,
  CharacterPosture,
  CharacterEmotion,
  CharacterCoordinates,
  CharacterGaze,
  DEFAULT_CHARACTER_PALETTE,
} from '../types/character';
import { tokens } from '../tokens';

export interface CharacterAvatarProps {
  semanticState: AssistantSemanticState;
  posture: CharacterPosture;
  emotion: CharacterEmotion;
  position: CharacterCoordinates;
  gaze: CharacterGaze;
  isDragging: boolean;
  isBlinking: boolean;
  mouthOpen: number; // 0 to 1
  isListening: boolean;
  isSpeaking: boolean;
  activeSpeechSnippet?: string;
  onPointerDown: (e: React.PointerEvent) => void;
  onPointerMove: (e: React.PointerEvent) => void;
  onPointerUp: (e: React.PointerEvent) => void;
  onToggleVoice: () => void;
  onOpenCardHUD: () => void;
}

export const CharacterAvatar: React.FC<CharacterAvatarProps> = ({
  semanticState,
  posture,
  emotion,
  position,
  gaze,
  isDragging,
  isBlinking,
  mouthOpen,
  isListening,
  isSpeaking,
  activeSpeechSnippet,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  onToggleVoice,
  onOpenCardHUD,
}) => {
  const [showControls, setShowControls] = useState(false);
  const palette = DEFAULT_CHARACTER_PALETTE;

  // Derive status glow color
  const getGlowColor = () => {
    switch (semanticState) {
      case 'ASSISTANT_LISTENING':
        return '#38BDF8';
      case 'ASSISTANT_THINKING':
      case 'ASSISTANT_PROCESSING':
        return tokens.colors.coreThinking;
      case 'ASSISTANT_WORKING':
        return tokens.colors.coreActing;
      case 'ASSISTANT_NEEDS_PERMISSION':
        return tokens.colors.coreConfirm;
      case 'ASSISTANT_SUCCESS':
        return tokens.colors.success;
      case 'ASSISTANT_ERROR':
        return tokens.colors.error;
      default:
        return 'rgba(226, 109, 39, 0.4)';
    }
  };

  const glowColor = getGlowColor();

  // Eye gaze displacement
  const pupilOffsetX = gaze.lookX * 3.5;
  const pupilOffsetY = gaze.lookY * 2.5;

  // Head tilt based on emotion
  let headRotation = 0;
  if (emotion === 'CURIOUS' || emotion === 'CONFUSED') headRotation = -6;
  if (emotion === 'SLEEPY' || posture === 'SLEEPING') headRotation = 8;
  if (isDragging) headRotation = 4;

  // Posture vertical offset & scale
  let bodyYOffset = 0;
  let isSitting = posture === 'SITTING';
  let isSleeping = posture === 'SLEEPING';
  let isJumping = posture === 'JUMPING';

  if (isSitting) bodyYOffset = 14;
  if (isSleeping) bodyYOffset = 22;
  if (isJumping) bodyYOffset = -12;

  return (
    <div
      id="niko-embodied-character"
      data-testid="niko-embodied-character"
      style={{
        position: 'fixed',
        left: `${position.x}px`,
        top: `${position.y}px`,
        width: '130px',
        height: '160px',
        zIndex: 99999,
        cursor: isDragging ? 'grabbing' : 'grab',
        userSelect: 'none',
        touchAction: 'none',
        filter: isDragging ? 'drop-shadow(0 16px 24px rgba(0,0,0,0.6))' : 'drop-shadow(0 8px 16px rgba(0,0,0,0.4))',
        transition: isDragging ? 'none' : 'transform 0.15s ease-out, filter 0.2s ease',
        transform: isJumping ? 'scale(1.08)' : 'scale(1)',
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onMouseEnter={() => setShowControls(true)}
      onMouseLeave={() => setShowControls(false)}
      title="NIKO Companion Pet (Click to open Assistant HUD, Drag to move)"
    >
      {/* Speech / Thought Bubble (When speaking or has active snippet) */}
      {(activeSpeechSnippet || isSpeaking || semanticState === 'ASSISTANT_NEEDS_PERMISSION') && (
        <div
          style={{
            position: 'absolute',
            bottom: '155px',
            left: '50%',
            transform: 'translateX(-50%)',
            minWidth: '140px',
            maxWidth: '220px',
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            border: `1.5px solid ${glowColor}`,
            borderRadius: '14px',
            padding: '8px 12px',
            color: '#F8FAFC',
            fontSize: '11px',
            lineHeight: '1.35',
            boxShadow: `0 8px 24px rgba(0, 0, 0, 0.5), 0 0 12px ${glowColor}44`,
            pointerEvents: 'none',
            animation: 'fadeInUp 0.2s ease-out',
            zIndex: 100000,
          }}
        >
          {semanticState === 'ASSISTANT_NEEDS_PERMISSION' ? (
            <span style={{ color: '#FBBF24', fontWeight: 600 }}>⚠️ I need your confirmation!</span>
          ) : activeSpeechSnippet ? (
            <span>{activeSpeechSnippet.slice(0, 80)}{activeSpeechSnippet.length > 80 ? '...' : ''}</span>
          ) : isSpeaking ? (
            <span style={{ color: '#38BDF8', fontStyle: 'italic' }}>Speaking...</span>
          ) : null}

          {/* Bubble Arrow */}
          <div
            style={{
              position: 'absolute',
              bottom: '-6px',
              left: '50%',
              transform: 'translateX(-50%) rotate(45deg)',
              width: '10px',
              height: '10px',
              backgroundColor: 'rgba(15, 23, 42, 0.95)',
              borderRight: `1.5px solid ${glowColor}`,
              borderBottom: `1.5px solid ${glowColor}`,
            }}
          />
        </div>
      )}

      {/* Thinking / Confused Bubble */}
      {(semanticState === 'ASSISTANT_THINKING' || emotion === 'CONFUSED') && (
        <div
          style={{
            position: 'absolute',
            top: '-18px',
            right: '12px',
            width: '26px',
            height: '26px',
            borderRadius: '50%',
            backgroundColor: 'rgba(30, 41, 59, 0.95)',
            border: `1.5px solid ${tokens.colors.coreThinking}`,
            color: tokens.colors.coreThinking,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 'bold',
            fontSize: '14px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
            animation: 'bounce 1.5s infinite',
          }}
        >
          ?
        </div>
      )}

      {/* Floating Zzz (Sleeping) */}
      {isSleeping && (
        <div
          style={{
            position: 'absolute',
            top: '-20px',
            right: '10px',
            color: '#93C5FD',
            fontFamily: tokens.typography.fontMono,
            fontWeight: 'bold',
            fontSize: '13px',
            animation: 'floatZzz 2s infinite ease-in-out',
            pointerEvents: 'none',
          }}
        >
          Zzz...
        </div>
      )}

      {/* Success Confetti Sparkles */}
      {emotion === 'EXCITED' && (
        <div
          style={{
            position: 'absolute',
            top: '-10px',
            left: '5px',
            right: '5px',
            height: '30px',
            pointerEvents: 'none',
            display: 'flex',
            justifyContent: 'space-around',
          }}
        >
          <span style={{ color: '#FACC15', fontSize: '14px', animation: 'ping 1s infinite' }}>✨</span>
          <span style={{ color: '#38BDF8', fontSize: '12px', animation: 'ping 1.2s infinite' }}>⭐</span>
          <span style={{ color: '#F472B6', fontSize: '14px', animation: 'ping 0.8s infinite' }}>✨</span>
        </div>
      )}

      {/* SVG Chibi Embodied Character Engine */}
      <svg
        viewBox="0 0 130 160"
        style={{
          width: '100%',
          height: '100%',
          overflow: 'visible',
        }}
      >
        <defs>
          {/* Hair Gradient */}
          <linearGradient id="hairGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#FB923C" />
            <stop offset="60%" stopColor={palette.hairColor} />
            <stop offset="100%" stopColor={palette.hairShadow} />
          </linearGradient>

          {/* Blazer Gradient */}
          <linearGradient id="blazerGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#831843" />
            <stop offset="60%" stopColor={palette.blazerColor} />
            <stop offset="100%" stopColor="#4C0519" />
          </linearGradient>

          {/* Eye Gradient */}
          <linearGradient id="eyeGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#B45309" />
            <stop offset="40%" stopColor={palette.eyeColor} />
            <stop offset="100%" stopColor="#FDE68A" />
          </linearGradient>

          {/* Subtle Aura Filter */}
          <filter id="auraGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="0" stdDeviation="4" floodColor={glowColor} floodOpacity="0.6" />
          </filter>
        </defs>

        {/* Ambient Halo behind character */}
        <ellipse
          cx="65"
          cy="145"
          rx="38"
          ry="7"
          fill="rgba(0, 0, 0, 0.35)"
        />

        {/* 1. BACK HAIR (Long Flowing Auburn Locks) */}
        <g transform={`translate(0, ${bodyYOffset})`}>
          <path
            d="M 32 45 C 18 65, 20 110, 30 135 C 38 120, 42 80, 45 60 Z"
            fill="url(#hairGrad)"
          />
          <path
            d="M 98 45 C 112 65, 110 110, 100 135 C 92 120, 88 80, 85 60 Z"
            fill="url(#hairGrad)"
          />
          {/* Back hair bulk */}
          <path
            d="M 36 50 C 30 90, 45 140, 65 142 C 85 140, 100 90, 94 50 Z"
            fill={palette.hairShadow}
          />
        </g>

        {/* 2. LEGS & SHOES / SITTING POSE */}
        <g transform={`translate(0, ${bodyYOffset})`}>
          {isSleeping ? (
            // Cozy sleeping pose with soft pillow
            <g>
              <rect x="25" y="130" width="80" height="22" rx="10" fill="#E2E8F0" opacity="0.9" />
              <ellipse cx="65" cy="136" rx="30" ry="10" fill="#CBD5E1" />
            </g>
          ) : isSitting ? (
            // Sitting legs
            <g>
              {/* Crossed / bent cute chibi legs */}
              <ellipse cx="50" cy="142" rx="14" ry="7" fill="#0F172A" />
              <ellipse cx="80" cy="142" rx="14" ry="7" fill="#0F172A" />
              <ellipse cx="42" cy="143" rx="7" ry="5" fill="#1E293B" />
              <ellipse cx="88" cy="143" rx="7" ry="5" fill="#1E293B" />
            </g>
          ) : (
            // Standing legs
            <g>
              {/* Left leg (Dark sock + shoe) */}
              <rect x="46" y="122" width="10" height="24" rx="4" fill="#0F172A" />
              <ellipse cx="51" cy="146" rx="7" ry="5" fill="#1E293B" />
              <ellipse cx="50" cy="144" rx="4" ry="2" fill="#475569" />

              {/* Right leg */}
              <rect x="74" y="122" width="10" height="24" rx="4" fill="#0F172A" />
              <ellipse cx="79" cy="146" rx="7" ry="5" fill="#1E293B" />
              <ellipse cx="78" cy="144" rx="4" ry="2" fill="#475569" />
            </g>
          )}

          {/* 3. DARK PLEATED SKIRT */}
          <path
            d="M 40 102 L 90 102 L 98 124 L 32 124 Z"
            fill={palette.skirtColor}
          />
          {/* Skirt pleat lines */}
          <line x1="48" y1="104" x2="44" y2="124" stroke="#0F172A" strokeWidth="1.5" />
          <line x1="58" y1="104" x2="56" y2="124" stroke="#0F172A" strokeWidth="1.5" />
          <line x1="72" y1="104" x2="74" y2="124" stroke="#0F172A" strokeWidth="1.5" />
          <line x1="82" y1="104" x2="86" y2="124" stroke="#0F172A" strokeWidth="1.5" />

          {/* 4. BURGUNDY / MAROON SCHOOL UNIFORM BLAZER */}
          <path
            d="M 38 74 L 92 74 L 95 104 L 35 104 Z"
            fill="url(#blazerGrad)"
          />
          {/* Gold Blazer Trim (Lapel & hem) */}
          <path
            d="M 38 74 L 54 94 L 54 104 L 35 104 Z"
            fill="none"
            stroke={palette.blazerTrim}
            strokeWidth="1.5"
          />
          <path
            d="M 92 74 L 76 94 L 76 104 L 95 104 Z"
            fill="none"
            stroke={palette.blazerTrim}
            strokeWidth="1.5"
          />
          <line x1="35" y1="103" x2="95" y2="103" stroke={palette.blazerTrim} strokeWidth="1.5" />

          {/* White Shirt Collar & V-Neck */}
          <polygon points="54,74 65,92 76,74" fill={palette.shirtColor} />

          {/* Yellow School Tie with knot */}
          <polygon points="63,78 67,78 68,83 62,83" fill="#EAB308" />
          <polygon points="62,83 68,83 70,97 65,100 60,97" fill={palette.tieColor} stroke="#CA8A04" strokeWidth="0.5" />

          {/* 5. ARMS & HANDS / MINI LAPTOP ACTIVITY */}
          {semanticState === 'ASSISTANT_WORKING' ? (
            // Working pose: Mini glowing cyber laptop in front
            <g>
              {/* Sleeves angled forward */}
              <path d="M 36 78 L 48 95 L 42 98 L 32 82 Z" fill="url(#blazerGrad)" />
              <path d="M 94 78 L 82 95 L 88 98 L 98 82 Z" fill="url(#blazerGrad)" />
              {/* Hands */}
              <circle cx="48" cy="98" r="4.5" fill={palette.skinColor} />
              <circle cx="82" cy="98" r="4.5" fill={palette.skinColor} />

              {/* Glowing Mini Laptop */}
              <rect x="42" y="94" width="46" height="26" rx="3" fill="#0F172A" stroke="#38BDF8" strokeWidth="1.5" />
              <rect x="45" y="97" width="40" height="15" rx="1" fill="#0284C7" opacity="0.8" />
              <line x1="47" y1="101" x2="70" y2="101" stroke="#BAE6FD" strokeWidth="1.5" strokeDasharray="3 2" />
              <line x1="47" y1="106" x2="65" y2="106" stroke="#BAE6FD" strokeWidth="1.5" strokeDasharray="2 2" />
              <rect x="40" y="120" width="50" height="4" rx="2" fill="#334155" />
            </g>
          ) : isJumping || emotion === 'EXCITED' ? (
            // Cheering arms up!
            <g>
              <path d="M 37 78 L 24 60 L 30 56 L 43 74 Z" fill="url(#blazerGrad)" />
              <path d="M 93 78 L 106 60 L 100 56 L 87 74 Z" fill="url(#blazerGrad)" />
              <circle cx="26" cy="56" r="4.5" fill={palette.skinColor} />
              <circle cx="104" cy="56" r="4.5" fill={palette.skinColor} />
            </g>
          ) : (
            // Natural resting arms
            <g>
              <path d="M 37 76 L 30 96 L 36 98 L 43 80 Z" fill="url(#blazerGrad)" />
              <circle cx="33" cy="99" r="4.5" fill={palette.skinColor} />
              <path d="M 93 76 L 100 96 L 94 98 L 87 80 Z" fill="url(#blazerGrad)" />
              <circle cx="97" cy="99" r="4.5" fill={palette.skinColor} />
            </g>
          )}
        </g>

        {/* 6. HEAD & FACE GROUP (Supports Tilt & Blinking) */}
        <g
          transform={`translate(65, ${52 + bodyYOffset}) rotate(${headRotation}) translate(-65, -52)`}
        >
          {/* Head Base */}
          <ellipse
            cx="65"
            cy="52"
            rx="33"
            ry="28"
            fill={palette.skinColor}
          />

          {/* Rosy Cheeks */}
          <ellipse cx="44" cy="59" rx="5" ry="3" fill={palette.blushColor} opacity="0.6" />
          <ellipse cx="86" cy="59" rx="5" ry="3" fill={palette.blushColor} opacity="0.6" />

          {/* EYES */}
          {isBlinking || isSleeping ? (
            // Closed / Blinking curved lines
            <g stroke="#78350F" strokeWidth="2.5" strokeLinecap="round" fill="none">
              <path d="M 44 52 Q 51 57 58 52" />
              <path d="M 72 52 Q 79 57 86 52" />
            </g>
          ) : (
            // Expressive Golden / Amber Chibi Eyes
            <g>
              {/* Left Eye */}
              <ellipse cx="51" cy="50" rx="9" ry="11" fill="url(#eyeGrad)" stroke="#78350F" strokeWidth="1.5" />
              {/* Left Pupil + Gaze */}
              <ellipse cx={51 + pupilOffsetX} cy={50 + pupilOffsetY} rx="5" ry="7" fill="#78350F" />
              {/* Highlights */}
              <circle cx={48 + pupilOffsetX * 0.5} cy={46 + pupilOffsetY * 0.5} r="3" fill={palette.eyeHighlight} />
              <circle cx={53 + pupilOffsetX * 0.5} cy={53 + pupilOffsetY * 0.5} r="1.5" fill={palette.eyeHighlight} />

              {/* Right Eye */}
              <ellipse cx="79" cy="50" rx="9" ry="11" fill="url(#eyeGrad)" stroke="#78350F" strokeWidth="1.5" />
              {/* Right Pupil + Gaze */}
              <ellipse cx={79 + pupilOffsetX} cy={50 + pupilOffsetY} rx="5" ry="7" fill="#78350F" />
              {/* Highlights */}
              <circle cx={76 + pupilOffsetX * 0.5} cy={46 + pupilOffsetY * 0.5} r="3" fill={palette.eyeHighlight} />
              <circle cx={81 + pupilOffsetX * 0.5} cy={53 + pupilOffsetY * 0.5} r="1.5" fill={palette.eyeHighlight} />

              {/* Eyelashes / Upper Lid */}
              <path d="M 41 43 Q 51 38 61 44" stroke="#78350F" strokeWidth="2" strokeLinecap="round" fill="none" />
              <path d="M 69 44 Q 79 38 89 43" stroke="#78350F" strokeWidth="2" strokeLinecap="round" fill="none" />
            </g>
          )}

          {/* Eyebrows */}
          <g stroke="#B84F14" strokeWidth="1.8" strokeLinecap="round" fill="none">
            {emotion === 'CONFUSED' || emotion === 'CURIOUS' ? (
              <>
                <path d="M 43 37 Q 50 33 58 37" />
                <path d="M 72 35 Q 80 40 87 38" />
              </>
            ) : emotion === 'SAD' ? (
              <>
                <path d="M 43 36 Q 51 40 58 38" />
                <path d="M 72 38 Q 79 40 87 36" />
              </>
            ) : (
              <>
                <path d="M 43 36 Q 51 32 58 36" />
                <path d="M 72 36 Q 79 32 87 36" />
              </>
            )}
          </g>

          {/* Cute Nose Dot */}
          <circle cx="65" cy="56" r="1" fill="#D97706" opacity="0.7" />

          {/* MOUTH (Animated Lipsync & Expressions) */}
          {mouthOpen > 0.1 ? (
            // Open talking mouth
            <ellipse
              cx="65"
              cy={64}
              rx={3 + mouthOpen * 4}
              ry={2 + mouthOpen * 5}
              fill="#BE185D"
              stroke="#831843"
              strokeWidth="1"
            />
          ) : emotion === 'HAPPY' || emotion === 'EXCITED' ? (
            // Wide happy smile
            <path
              d="M 59 62 Q 65 68 71 62"
              fill="none"
              stroke="#9D174D"
              strokeWidth="2"
              strokeLinecap="round"
            />
          ) : emotion === 'SAD' ? (
            // Little pout
            <path
              d="M 60 65 Q 65 61 70 65"
              fill="none"
              stroke="#9D174D"
              strokeWidth="2"
              strokeLinecap="round"
            />
          ) : (
            // Cute neutral smile
            <path
              d="M 61 63 Q 65 66 69 63"
              fill="none"
              stroke="#9D174D"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
          )}

          {/* 7. FRONT HAIR & MESSY BUN (Auburn Hairstyle) */}
          {/* Side Bangs */}
          <path
            d="M 33 46 C 30 65, 34 85, 39 92 C 41 82, 38 60, 42 46 Z"
            fill="url(#hairGrad)"
          />
          <path
            d="M 97 46 C 100 65, 96 85, 91 92 C 89 82, 92 60, 88 46 Z"
            fill="url(#hairGrad)"
          />

          {/* Forehead Bangs */}
          <path
            d="M 32 40 C 40 26, 60 26, 68 36 C 74 26, 90 26, 98 40 C 92 36, 85 36, 80 43 C 75 35, 68 35, 64 45 C 58 35, 48 35, 42 45 C 38 38, 35 38, 32 40 Z"
            fill="url(#hairGrad)"
          />

          {/* Messy High Bun on Top */}
          <g>
            <circle cx="65" cy="18" r="16" fill="url(#hairGrad)" />
            <circle cx="74" cy="14" r="10" fill="url(#hairGrad)" />
            <circle cx="56" cy="15" r="9" fill="url(#hairGrad)" />
            {/* Bun Hair Tie */}
            <ellipse cx="65" cy="27" rx="12" ry="4" fill="#991B1B" />
            {/* Playful stray wisp */}
            <path
              d="M 68 8 C 76 0, 85 4, 82 12"
              fill="none"
              stroke={palette.hairColor}
              strokeWidth="2.5"
              strokeLinecap="round"
            />
          </g>
        </g>
      </svg>

      {/* Floating Hover Controls & State Badge */}
      <div
        style={{
          position: 'absolute',
          bottom: '-22px',
          left: '50%',
          transform: 'translateX(-50%)',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          opacity: showControls || isSpeaking || isListening ? 1 : 0.85,
          transition: 'opacity 0.2s ease',
        }}
      >
        {/* Status Pill Badge */}
        <div
          style={{
            background: 'rgba(15, 23, 42, 0.92)',
            border: `1px solid ${glowColor}`,
            borderRadius: tokens.radii.full,
            padding: '2px 8px',
            fontSize: '9px',
            fontFamily: tokens.typography.fontMono,
            color: glowColor,
            letterSpacing: '0.04em',
            whiteSpace: 'nowrap',
            boxShadow: '0 2px 8px rgba(0,0,0,0.5)',
          }}
        >
          {semanticState.replace('ASSISTANT_', '')}
        </div>

        {/* Voice Toggle Button */}
        <button
          type="button"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => {
            e.stopPropagation();
            onToggleVoice();
          }}
          style={{
            width: '24px',
            height: '24px',
            borderRadius: '50%',
            backgroundColor: isListening ? '#38BDF8' : 'rgba(30, 41, 59, 0.95)',
            border: `1px solid ${isListening ? '#0284C7' : 'rgba(255, 255, 255, 0.2)'}`,
            color: isListening ? '#0F172A' : '#94A3B8',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            padding: 0,
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

        {/* Expand to Assistant HUD Card */}
        <button
          type="button"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => {
            e.stopPropagation();
            onOpenCardHUD();
          }}
          style={{
            width: '24px',
            height: '24px',
            borderRadius: '50%',
            backgroundColor: 'rgba(30, 41, 59, 0.95)',
            border: '1px solid rgba(255, 255, 255, 0.2)',
            color: '#E2E8F0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            padding: 0,
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.4)',
          }}
          title="Open Assistant HUD Card"
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="15 3 21 3 21 9" />
            <polyline points="9 21 3 21 3 15" />
            <line x1="21" y1="3" x2="14" y2="10" />
            <line x1="3" y1="21" x2="10" y2="14" />
          </svg>
        </button>
      </div>
    </div>
  );
};
