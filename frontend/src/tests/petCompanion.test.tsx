import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PetCompanion } from '../components/PetCompanion';

describe('PetCompanion Component', () => {
  it('renders pet companion in idle state and triggers onExpand on click', () => {
    const onExpand = vi.fn();
    const onToggleVoice = vi.fn();

    render(
      <PetCompanion
        orbState="idle"
        isListening={false}
        isSpeaking={false}
        isBargeInActive={false}
        audioLevel={0}
        onExpand={onExpand}
        onToggleVoice={onToggleVoice}
      />
    );

    const companion = screen.getByTitle(/NIKO Companion Pet/i);
    expect(companion).toBeDefined();
    expect(screen.getByText('IDLE')).toBeDefined();

    // Click companion orb without moving
    fireEvent.pointerDown(companion, { clientX: 100, clientY: 100 });
    fireEvent.pointerUp(companion, { clientX: 100, clientY: 100 });

    expect(onExpand).toHaveBeenCalled();
  });

  it('triggers voice toggle when clicking voice mic button', () => {
    const onExpand = vi.fn();
    const onToggleVoice = vi.fn();

    render(
      <PetCompanion
        orbState="acting"
        isListening={false}
        isSpeaking={false}
        isBargeInActive={false}
        audioLevel={0.5}
        onExpand={onExpand}
        onToggleVoice={onToggleVoice}
      />
    );

    const micBtn = screen.getByTitle('Activate Voice Mic');
    fireEvent.click(micBtn);

    expect(onToggleVoice).toHaveBeenCalled();
    expect(onExpand).not.toHaveBeenCalled();
  });
});
