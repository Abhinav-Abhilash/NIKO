import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { PetCompanion } from '../components/PetCompanion';
import { CharacterAvatar } from '../components/CharacterAvatar';
import { useCharacterState } from '../hooks/useCharacterState';
import { renderHook } from '@testing-library/react';

describe('Character & Voice Engine Integration', () => {
  it('synchronizes speaking state, emotion, and speech bubble when voice speaks', () => {
    const { rerender } = render(
      <PetCompanion
        orbState="idle"
        isListening={false}
        isSpeaking={false}
        isBargeInActive={false}
        audioLevel={0}
        onExpand={vi.fn()}
        onToggleVoice={vi.fn()}
      />
    );

    // Initial Idle State: no speech bubble, mouth closed
    expect(screen.queryByText(/speaking/i)).toBeNull();
    expect(screen.queryByText(/hello master/i)).toBeNull();

    // Voice Engine starts speaking with sentence snippet
    rerender(
      <PetCompanion
        orbState="idle"
        isListening={false}
        isSpeaking={true}
        isBargeInActive={false}
        audioLevel={0.4}
        activeSpeechSnippet="Hello Master! Niko is online and ready to help!"
        onExpand={vi.fn()}
        onToggleVoice={vi.fn()}
      />
    );

    // Speech bubble appears with live spoken text
    expect(screen.getByText(/Hello Master! Niko is online and ready to help!/i)).toBeInTheDocument();
  });

  it('dynamically modulates mouth aperture based on audio amplitude level', () => {
    // 1. Silent / Not Speaking
    const { result, rerender } = renderHook(
      (props) =>
        useCharacterState({
          orbState: 'idle',
          isListening: false,
          isSpeaking: props.isSpeaking,
          isStreaming: false,
          hasPendingApproval: false,
          activeToolCallsCount: 0,
          audioLevel: props.audioLevel,
        }),
      { initialProps: { isSpeaking: false, audioLevel: 0 } }
    );

    expect(result.current.mouthOpen).toBe(0);
    expect(result.current.semanticState).toBe('ASSISTANT_IDLE');

    // 2. Speaking with low audio energy
    rerender({ isSpeaking: true, audioLevel: 0.15 });
    expect(result.current.semanticState).toBe('ASSISTANT_SPEAKING');
    expect(result.current.emotion).toBe('HAPPY');
    const lowAperture = result.current.mouthOpen;
    expect(lowAperture).toBeGreaterThan(0.2);

    // 3. Speaking with peak audio energy (accentuated syllables)
    rerender({ isSpeaking: true, audioLevel: 0.55 });
    const peakAperture = result.current.mouthOpen;
    expect(peakAperture).toBeGreaterThan(lowAperture);
    expect(peakAperture).toBeLessThanOrEqual(1.0);

    // 4. Instant Barge-In Cutoff / Silence: mouth snaps shut immediately
    rerender({ isSpeaking: false, audioLevel: 0 });
    expect(result.current.mouthOpen).toBe(0);
    expect(result.current.semanticState).toBe('ASSISTANT_IDLE');
  });

  it('renders SVG animated open mouth geometry when mouthOpen is active', () => {
    const { container, rerender } = render(
      <CharacterAvatar
        semanticState="ASSISTANT_IDLE"
        posture="STANDING"
        emotion="NEUTRAL"
        position={{ x: 100, y: 100 }}
        gaze={{ lookX: 0, lookY: 0 }}
        isDragging={false}
        isBlinking={false}
        mouthOpen={0}
        isListening={false}
        isSpeaking={false}
        onPointerDown={vi.fn()}
        onPointerMove={vi.fn()}
        onPointerUp={vi.fn()}
        onToggleVoice={vi.fn()}
        onOpenCardHUD={vi.fn()}
      />
    );

    // Closed mouth uses path stroke (smile arc)
    const mouthPaths = container.querySelectorAll('path[stroke="#9D174D"]');
    expect(mouthPaths.length).toBeGreaterThan(0);

    // Mouth opens during voice playback
    rerender(
      <CharacterAvatar
        semanticState="ASSISTANT_SPEAKING"
        posture="STANDING"
        emotion="HAPPY"
        position={{ x: 100, y: 100 }}
        gaze={{ lookX: 0, lookY: 0 }}
        isDragging={false}
        isBlinking={false}
        mouthOpen={0.75}
        isListening={false}
        isSpeaking={true}
        onPointerDown={vi.fn()}
        onPointerMove={vi.fn()}
        onPointerUp={vi.fn()}
        onToggleVoice={vi.fn()}
        onOpenCardHUD={vi.fn()}
      />
    );

    // Open mouth renders animated ellipse filled with #BE185D
    const openMouthEllipse = container.querySelector('ellipse[fill="#BE185D"]');
    expect(openMouthEllipse).not.toBeNull();
    expect(Number(openMouthEllipse?.getAttribute('rx'))).toBeGreaterThan(3);
    expect(Number(openMouthEllipse?.getAttribute('ry'))).toBeGreaterThan(2);
  });
});
