import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { AssistantCardOverlay } from '../components/AssistantCardOverlay';

// Mock hooks
vi.mock('../hooks', () => ({
  useOverlay: () => ({
    isVisible: true,
    mode: 'compact',
    show: vi.fn(),
    hide: vi.fn(),
    setMode: vi.fn(),
  }),
  useChatStream: () => ({
    messages: [{ id: '1', role: 'assistant', content: 'Ready to assist with your Windows tasks.' }],
    isStreaming: false,
    streamingContent: '',
    sendMessage: vi.fn(),
    activeToolCalls: [],
  }),
  useVoiceEngine: () => ({
    isListening: false,
    isSpeaking: false,
    isBargeInActive: false,
    audioLevel: 0,
    toggleListening: vi.fn(),
  }),
  useApprovals: () => ({
    hasPendingApproval: false,
    pendingApprovals: [],
    approve: vi.fn(),
    reject: vi.fn(),
  }),
  useOrbState: () => ({
    orbState: 'idle',
  }),
}));

describe('AssistantCardOverlay Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders Google Assistant style bottom HUD card with suggestion chips', () => {
    render(<AssistantCardOverlay />);

    expect(screen.getByText('NIKO AI')).toBeInTheDocument();
    expect(screen.getByText('Ready to assist with your Windows tasks.')).toBeInTheDocument();
    expect(screen.getByText('📋 Summarize clipboard')).toBeInTheDocument();
    expect(screen.getByText("🖥️ What's on screen?")).toBeInTheDocument();
  });

  it('allows typing into the input field and submitting a message', () => {
    render(<AssistantCardOverlay />);

    const input = screen.getByPlaceholderText('Ask NIKO anything or speak...');
    fireEvent.change(input, { target: { value: 'Inspect active windows' } });

    expect(input).toHaveValue('Inspect active windows');

    const submitBtn = screen.getByTitle('Send message');
    fireEvent.click(submitBtn);
  });
});
