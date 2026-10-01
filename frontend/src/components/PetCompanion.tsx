import React from 'react';
import type { OrbState } from '../hooks/useOrbState';
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
  audioLevel,
  activeSpeechSnippet,
  onExpand,
  onToggleVoice,
}) => {
  const charState = useCharacterState({
    orbState,
    isListening,
    isSpeaking,
    isStreaming: false,
    hasPendingApproval: orbState === 'confirm',
    activeToolCallsCount: orbState === 'acting' ? 1 : 0,
    audioLevel,
  });

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
