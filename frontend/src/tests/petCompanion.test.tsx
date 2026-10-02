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

  it('supports click-to-type flow: opens inline input beside pet and submits message', () => {
    const onSendMessage = vi.fn();
    const onExpand = vi.fn();

    render(
      <PetCompanion
        orbState="idle"
        isListening={false}
        isSpeaking={false}
        audioLevel={0}
        petName="NIKO"
        onSendMessage={onSendMessage}
        onExpand={onExpand}
        onToggleVoice={vi.fn()}
      />
    );

    const companion = screen.getByTestId('niko-embodied-character');
    // Click companion to open inline text input
    fireEvent.pointerDown(companion, { clientX: 50, clientY: 50 });
    fireEvent.pointerUp(companion, { clientX: 50, clientY: 50 });

    const input = screen.getByTestId('pet-inline-input');
    expect(input).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Ask NIKO...')).toBeInTheDocument();

    // Type prompt and send
    fireEvent.change(input, { target: { value: 'Open calculator and calculate 42 * 42' } });
    const sendBtn = screen.getByTestId('pet-send-btn');
    fireEvent.click(sendBtn);

    expect(onSendMessage).toHaveBeenCalledWith('Open calculator and calculate 42 * 42');
  });

  it('renders answers directly in pet speech bubble during streaming and voice playback', () => {
    render(
      <PetCompanion
        orbState="thinking"
        isListening={false}
        isSpeaking={true}
        isStreaming={true}
        audioLevel={0.6}
        activeSpeechSnippet="The answer is 1,764."
        onExpand={vi.fn()}
        onToggleVoice={vi.fn()}
      />
    );

    expect(screen.getByText('The answer is 1,764.')).toBeInTheDocument();
  });

  it('asks approval through pet persona with 30s countdown and Yes/No actions', () => {
    const onApprove = vi.fn();
    const onDeny = vi.fn();

    render(
      <PetCompanion
        orbState="confirm"
        isListening={false}
        isSpeaking={false}
        audioLevel={0}
        hasPendingApproval={true}
        pendingApproval={{
          approvalId: 'appr_notepad_1',
          skillName: 'open_app',
          arguments: { app_name: 'Notepad' },
          provenance: 'direct_command',
          requestedAt: Date.now(),
          expiresAt: Date.now() + 30000,
          remainingSeconds: 30,
        }}
        remainingSeconds={30}
        onApprove={onApprove}
        onDeny={onDeny}
        onExpand={vi.fn()}
        onToggleVoice={vi.fn()}
      />
    );

    // Prompt asks through friendly pet question
    expect(screen.getByText('Can I open Notepad?')).toBeInTheDocument();
    expect(screen.getByTestId('pet-approval-countdown').textContent).toBe('30s');

    // Yes / No buttons
    const approveBtn = screen.getByTestId('pet-approve-btn');
    expect(approveBtn.textContent).toContain('Yes');
    fireEvent.click(approveBtn);
    expect(onApprove).toHaveBeenCalledWith('once');

    const denyBtn = screen.getByTestId('pet-deny-btn');
    expect(denyBtn.textContent).toContain('No');
    fireEvent.click(denyBtn);
    expect(onDeny).toHaveBeenCalledWith('denied_by_user');
  });
});
