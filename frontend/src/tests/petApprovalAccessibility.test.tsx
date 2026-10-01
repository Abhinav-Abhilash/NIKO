import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { PetCompanion } from '../components/PetCompanion';
import { useCharacterState } from '../hooks/useCharacterState';
import { renderHook } from '@testing-library/react';

describe('Pet Companion & Approval Accessibility', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useRealTimers();
  });

  it('enforces click-through root wrapper with clickable pet area', () => {
    render(
      <PetCompanion
        orbState="idle"
        isListening={false}
        isSpeaking={false}
        audioLevel={0}
        onExpand={vi.fn()}
        onToggleVoice={vi.fn()}
      />
    );

    const rootWrapper = screen.getByTestId('niko-pet-companion-wrapper');
    expect(rootWrapper.style.pointerEvents).toBe('none');

    const characterAvatar = screen.getByTestId('niko-embodied-character');
    expect(characterAvatar.style.pointerEvents).toBe('auto');
  });

  it('renders reachable, focused approval prompt with 30s countdown and Enter/Esc handlers', () => {
    const onApprove = vi.fn();
    const onDeny = vi.fn();

    const mockPendingApproval = {
      approvalId: 'appr_test_123',
      skillName: 'file_delete_skill',
      arguments: { path: '/storage/sample.txt' },
      provenance: 'direct_command',
      requestedAt: Date.now(),
      expiresAt: Date.now() + 30000,
      remainingSeconds: 30,
    };

    render(
      <PetCompanion
        orbState="confirm"
        isListening={false}
        isSpeaking={false}
        audioLevel={0}
        hasPendingApproval={true}
        pendingApproval={mockPendingApproval}
        remainingSeconds={30}
        onApprove={onApprove}
        onDeny={onDeny}
        onExpand={vi.fn()}
        onToggleVoice={vi.fn()}
      />
    );

    // Prompt is visible and clickable
    const prompt = screen.getByTestId('pet-approval-prompt');
    expect(prompt).toBeDefined();
    expect(prompt.style.pointerEvents).toBe('auto');

    // Countdown is visible
    const countdown = screen.getByTestId('pet-approval-countdown');
    expect(countdown.textContent).toBe('30s');

    // Skill name is displayed
    expect(screen.getByText('file_delete_skill')).toBeDefined();

    // Keyboard controls: Enter to approve
    fireEvent.keyDown(prompt, { key: 'Enter', code: 'Enter' });
    expect(onApprove).toHaveBeenCalledWith('once');

    // Keyboard controls: Escape to deny
    fireEvent.keyDown(prompt, { key: 'Escape', code: 'Escape' });
    expect(onDeny).toHaveBeenCalledWith('denied_by_user');

    // Clicking buttons directly works
    const approveBtn = screen.getByTestId('pet-approve-btn');
    fireEvent.click(approveBtn);
    expect(onApprove).toHaveBeenCalledTimes(2);

    const denyBtn = screen.getByTestId('pet-deny-btn');
    fireEvent.click(denyBtn);
    expect(onDeny).toHaveBeenCalledTimes(2);
  });
});

describe('useCharacterState - Real States Telemetry (Zero Fake Timers)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('strictly derives idle state with no spontaneous fake-timer state drift', () => {
    const { result } = renderHook(() =>
      useCharacterState({
        orbState: 'idle',
        isListening: false,
        isSpeaking: false,
        isStreaming: false,
        hasPendingApproval: false,
        activeToolCallsCount: 0,
      })
    );

    expect(result.current.semanticState).toBe('ASSISTANT_IDLE');
    expect(result.current.posture).toBe('STANDING');
    expect(result.current.emotion).toBe('NEUTRAL');
  });

  it('reflects thinking state when LLM is streaming or orbState is thinking', () => {
    const { result } = renderHook(() =>
      useCharacterState({
        orbState: 'thinking',
        isListening: false,
        isSpeaking: false,
        isStreaming: true,
        hasPendingApproval: false,
        activeToolCallsCount: 0,
      })
    );

    expect(result.current.semanticState).toBe('ASSISTANT_THINKING');
    expect(result.current.posture).toBe('STANDING');
    expect(result.current.emotion).toBe('CONFUSED');
  });

  it('reflects acting state when tool calls are running', () => {
    const { result } = renderHook(() =>
      useCharacterState({
        orbState: 'acting',
        isListening: false,
        isSpeaking: false,
        isStreaming: false,
        hasPendingApproval: false,
        activeToolCallsCount: 2,
      })
    );

    expect(result.current.semanticState).toBe('ASSISTANT_WORKING');
    expect(result.current.posture).toBe('SITTING');
    expect(result.current.emotion).toBe('NEUTRAL');
  });

  it('reflects waiting for approval state when approval is requested', () => {
    const { result } = renderHook(() =>
      useCharacterState({
        orbState: 'confirm',
        isListening: false,
        isSpeaking: false,
        isStreaming: false,
        hasPendingApproval: true,
        activeToolCallsCount: 0,
      })
    );

    expect(result.current.semanticState).toBe('ASSISTANT_NEEDS_PERMISSION');
    expect(result.current.posture).toBe('STANDING');
    expect(result.current.emotion).toBe('SURPRISED');
  });

  it('reflects error state when tool execution fails or error is reported', () => {
    const { result } = renderHook(() =>
      useCharacterState({
        orbState: 'idle',
        isListening: false,
        isSpeaking: false,
        isStreaming: false,
        hasPendingApproval: false,
        activeToolCallsCount: 0,
        error: 'Network connection lost',
      })
    );

    expect(result.current.semanticState).toBe('ASSISTANT_ERROR');
    expect(result.current.posture).toBe('STANDING');
    expect(result.current.emotion).toBe('SAD');
  });

  it('reflects providers cooling down state when LLM quotas are exhausted', () => {
    const { result } = renderHook(() =>
      useCharacterState({
        orbState: 'idle',
        isListening: false,
        isSpeaking: false,
        isStreaming: false,
        hasPendingApproval: false,
        activeToolCallsCount: 0,
        isCoolingDown: true,
        cooldownMessage: 'All providers cooling down for role',
      })
    );

    expect(result.current.semanticState).toBe('ASSISTANT_COOLING_DOWN');
    expect(result.current.posture).toBe('SITTING');
    expect(result.current.emotion).toBe('SLEEPY');
  });

  it('reflects speaking state when voice output is active', () => {
    const { result } = renderHook(() =>
      useCharacterState({
        orbState: 'idle',
        isListening: false,
        isSpeaking: true,
        isStreaming: false,
        hasPendingApproval: false,
        activeToolCallsCount: 0,
        audioLevel: 0.75,
      })
    );

    expect(result.current.semanticState).toBe('ASSISTANT_SPEAKING');
    expect(result.current.posture).toBe('STANDING');
    expect(result.current.emotion).toBe('HAPPY');
    expect(result.current.mouthOpen).toBeGreaterThan(0.2);
  });
});
