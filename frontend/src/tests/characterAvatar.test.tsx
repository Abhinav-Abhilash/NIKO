import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { CharacterAvatar } from '../components/CharacterAvatar';

describe('CharacterAvatar Component', () => {
  const defaultProps = {
    semanticState: 'ASSISTANT_IDLE' as const,
    posture: 'STANDING' as const,
    emotion: 'NEUTRAL' as const,
    position: { x: 100, y: 100 },
    gaze: { lookX: 0, lookY: 0 },
    isDragging: false,
    isBlinking: false,
    mouthOpen: 0,
    isListening: false,
    isSpeaking: false,
    onPointerDown: vi.fn(),
    onPointerMove: vi.fn(),
    onPointerUp: vi.fn(),
    onToggleVoice: vi.fn(),
    onOpenCardHUD: vi.fn(),
  };

  it('renders embodied chibi character with proper container and status pill', () => {
    render(<CharacterAvatar {...defaultProps} />);

    const charEl = screen.getByTestId('niko-embodied-character');
    expect(charEl).toBeInTheDocument();
    expect(screen.getByText('IDLE')).toBeInTheDocument();
  });

  it('renders speech bubble when activeSpeechSnippet is provided', () => {
    render(<CharacterAvatar {...defaultProps} activeSpeechSnippet="Hello! I am NIKO." isSpeaking={true} />);

    expect(screen.getByText('Hello! I am NIKO.')).toBeInTheDocument();
  });

  it('triggers onToggleVoice when mic button is clicked', () => {
    const onToggleVoice = vi.fn();
    render(<CharacterAvatar {...defaultProps} onToggleVoice={onToggleVoice} />);

    const micBtn = screen.getByTitle('Activate Voice Mic');
    fireEvent.click(micBtn);

    expect(onToggleVoice).toHaveBeenCalledTimes(1);
  });

  it('triggers onOpenCardHUD when expand button is clicked', () => {
    const onOpenCardHUD = vi.fn();
    render(<CharacterAvatar {...defaultProps} onOpenCardHUD={onOpenCardHUD} />);

    const expandBtn = screen.getByTitle('Open Assistant HUD Card');
    fireEvent.click(expandBtn);

    expect(onOpenCardHUD).toHaveBeenCalledTimes(1);
  });
});
