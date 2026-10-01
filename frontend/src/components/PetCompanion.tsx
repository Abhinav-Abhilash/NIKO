import React, { useState, useEffect, useRef } from 'react';
import { OrbState } from '../hooks/useOrbState';
import { tokens } from '../tokens';
import { CharacterAvatar } from './CharacterAvatar';
import { useCharacterState } from '../hooks/useCharacterState';

export interface PetCompanionProps {
  orbState: OrbState;
  isListening: boolean;
  isSpeaking: boolean;
  isBargeInActive: boolean;
  audioLevel: number;
  activeSpeechSnippet?: string;
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
  activeSpeechSnippet,
  onExpand,
  onToggleVoice,
  onBargeIn,
}) => {
  const [renderMode, setRenderMode] = useState<'character' | 'orb'>('character');

  const charState = useCharacterState({
    orbState,
    isListening,
    isSpeaking,
    isStreaming: false,
    hasPendingApproval: orbState === 'confirm',
    activeToolCallsCount: orbState === 'acting' ? 1 : 0,
    audioLevel,
  });

  // Fallback / alternate orb mode
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

  return (
    <div id="niko-pet-companion-wrapper">
      {/* Embodied Chibi Character Renderer */}
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
        onPointerUp={(e) => charState.endDrag(e, onExpand)}
        onToggleVoice={onToggleVoice}
        onOpenCardHUD={onExpand}
      />
    </div>
  );
};
