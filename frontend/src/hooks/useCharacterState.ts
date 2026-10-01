import { useState, useEffect, useRef, useCallback } from 'react';
import {
  AssistantSemanticState,
  CharacterPosture,
  CharacterEmotion,
  EnvironmentState,
  CharacterCoordinates,
  CharacterGaze,
} from '../types/character';
import { OrbState } from './useOrbState';

export interface UseCharacterStateParams {
  orbState: OrbState;
  isListening: boolean;
  isSpeaking: boolean;
  isStreaming: boolean;
  hasPendingApproval: boolean;
  activeToolCallsCount: number;
  lastToolStatus?: 'success' | 'error' | null;
  audioLevel?: number;
  initialX?: number;
  initialY?: number;
}

export interface UseCharacterStateReturn {
  semanticState: AssistantSemanticState;
  posture: CharacterPosture;
  emotion: CharacterEmotion;
  environmentState: EnvironmentState;
  position: CharacterCoordinates;
  setPosition: (pos: CharacterCoordinates) => void;
  gaze: CharacterGaze;
  isDragging: boolean;
  isBlinking: boolean;
  mouthOpen: number; // 0 to 1
  startDrag: (e: React.PointerEvent) => void;
  onDrag: (e: React.PointerEvent) => void;
  endDrag: (e: React.PointerEvent, onClickFallback?: () => void) => void;
  triggerReaction: (emotion: CharacterEmotion, durationMs?: number) => void;
  wakeUp: () => void;
}

export function useCharacterState({
  orbState,
  isListening,
  isSpeaking,
  isStreaming,
  hasPendingApproval,
  activeToolCallsCount,
  lastToolStatus,
  audioLevel = 0,
  initialX,
  initialY,
}: UseCharacterStateParams): UseCharacterStateReturn {
  // Position
  const [position, setPosition] = useState<CharacterCoordinates>(() => {
    try {
      const saved = localStorage.getItem('niko_character_pos');
      if (saved) return JSON.parse(saved);
    } catch {
      // ignore
    }
    const defX = initialX ?? (typeof window !== 'undefined' ? window.innerWidth - 160 : 800);
    const defY = initialY ?? (typeof window !== 'undefined' ? window.innerHeight - 220 : 600);
    return { x: Math.max(20, defX), y: Math.max(20, defY) };
  });

  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef<{ startX: number; startY: number; posX: number; posY: number }>({
    startX: 0,
    startY: 0,
    posX: 0,
    posY: 0,
  });
  const hasMovedRef = useRef(false);

  // Inactivity & override states
  const [inactivityState, setInactivityState] = useState<'ACTIVE' | 'BORED' | 'SLEEPY' | 'SLEEPING'>('ACTIVE');
  const [overrideEmotion, setOverrideEmotion] = useState<{ emotion: CharacterEmotion; expiresAt: number } | null>(null);
  const [isBlinking, setIsBlinking] = useState(false);
  const [gaze, setGaze] = useState<CharacterGaze>({ lookX: 0, lookY: 0 });
  const [isLanding, setIsLanding] = useState(false);

  const lastActivityRef = useRef<number>(Date.now());

  // Derive semantic AI state from inputs
  let semanticState: AssistantSemanticState = 'ASSISTANT_IDLE';
  if (hasPendingApproval) {
    semanticState = 'ASSISTANT_NEEDS_PERMISSION';
  } else if (activeToolCallsCount > 0) {
    semanticState = 'ASSISTANT_WORKING';
  } else if (isListening) {
    semanticState = 'ASSISTANT_LISTENING';
  } else if (isSpeaking) {
    semanticState = 'ASSISTANT_SPEAKING';
  } else if (isStreaming || orbState === 'thinking') {
    semanticState = 'ASSISTANT_THINKING';
  } else if (orbState === 'acting') {
    semanticState = 'ASSISTANT_PROCESSING';
  } else if (lastToolStatus === 'success') {
    semanticState = 'ASSISTANT_SUCCESS';
  } else if (lastToolStatus === 'error') {
    semanticState = 'ASSISTANT_ERROR';
  }

  // Activity tracking: any AI state change or voice/stream resets inactivity
  useEffect(() => {
    if (semanticState !== 'ASSISTANT_IDLE') {
      lastActivityRef.current = Date.now();
      setInactivityState('ACTIVE');
    }
  }, [semanticState]);

  // Periodic inactivity timer
  useEffect(() => {
    const interval = setInterval(() => {
      if (semanticState !== 'ASSISTANT_IDLE' || isDragging) return;
      const idleTime = Date.now() - lastActivityRef.current;
      if (idleTime > 60000) {
        setInactivityState('SLEEPING');
      } else if (idleTime > 30000) {
        setInactivityState('SLEEPY');
      } else if (idleTime > 15000) {
        setInactivityState('BORED');
      } else {
        setInactivityState('ACTIVE');
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [semanticState, isDragging]);

  // Natural Blinking Cycle
  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout>;
    const runBlink = () => {
      setIsBlinking(true);
      timeoutId = setTimeout(() => {
        setIsBlinking(false);
        const nextDelay = 2500 + Math.random() * 4000;
        timeoutId = setTimeout(runBlink, nextDelay);
      }, 140);
    };
    timeoutId = setTimeout(runBlink, 3000);
    return () => clearTimeout(timeoutId);
  }, []);

  // Cursor Tracking for gaze (subtle attention)
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      lastActivityRef.current = Date.now();
      if (inactivityState === 'SLEEPING') return;

      const charCenterX = position.x + 60;
      const charCenterY = position.y + 70;
      const dx = e.clientX - charCenterX;
      const dy = e.clientY - charCenterY;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist < 450) {
        // Normalize gaze between -1 and 1
        const lookX = Math.max(-1, Math.min(1, dx / 200));
        const lookY = Math.max(-1, Math.min(1, dy / 200));
        setGaze({ lookX, lookY });
      } else {
        setGaze({ lookX: 0, lookY: 0 });
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, [position, inactivityState]);

  // Derive Character Posture & Emotion
  let posture: CharacterPosture = 'STANDING';
  let emotion: CharacterEmotion = 'NEUTRAL';
  let environmentState: EnvironmentState = 'DESKTOP';

  if (isDragging) {
    posture = 'DRAGGED';
    emotion = 'SURPRISED';
    environmentState = 'CURSOR_INTERACTION';
  } else if (isLanding) {
    posture = 'JUMPING';
    emotion = 'HAPPY';
  } else {
    switch (semanticState) {
      case 'ASSISTANT_LISTENING':
        posture = 'STANDING';
        emotion = 'CURIOUS';
        environmentState = 'CURSOR_NEAR';
        break;
      case 'ASSISTANT_THINKING':
      case 'ASSISTANT_PROCESSING':
        posture = 'STANDING';
        emotion = 'CONFUSED';
        break;
      case 'ASSISTANT_SPEAKING':
        posture = 'STANDING';
        emotion = 'HAPPY';
        break;
      case 'ASSISTANT_WORKING':
        posture = 'SITTING';
        emotion = 'NEUTRAL';
        break;
      case 'ASSISTANT_NEEDS_PERMISSION':
        posture = 'STANDING';
        emotion = 'SURPRISED';
        break;
      case 'ASSISTANT_SUCCESS':
        posture = 'JUMPING';
        emotion = 'EXCITED';
        break;
      case 'ASSISTANT_ERROR':
        posture = 'STANDING';
        emotion = 'SAD';
        break;
      case 'ASSISTANT_IDLE':
      default:
        if (inactivityState === 'SLEEPING') {
          posture = 'SLEEPING';
          emotion = 'SLEEPY';
        } else if (inactivityState === 'SLEEPY') {
          posture = 'SITTING';
          emotion = 'SLEEPY';
        } else if (inactivityState === 'BORED') {
          posture = 'SITTING';
          emotion = 'BORED';
        } else {
          posture = 'STANDING';
          emotion = 'NEUTRAL';
        }
        break;
    }
  }

  // Apply emotion override if active
  if (overrideEmotion && Date.now() < overrideEmotion.expiresAt) {
    emotion = overrideEmotion.emotion;
  }

  // Mouth lipsync aperture driven by speaking & audioLevel
  let mouthOpen = 0;
  if (isSpeaking) {
    mouthOpen = Math.min(1, Math.max(0.2, audioLevel * 1.8));
  } else if (emotion === 'EXCITED' || emotion === 'SURPRISED') {
    mouthOpen = 0.4;
  }

  // Drag handlers
  const startDrag = useCallback((e: React.PointerEvent) => {
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
  }, [position]);

  const onDrag = useCallback((e: React.PointerEvent) => {
    if (!isDragging) return;
    const dx = e.clientX - dragStartRef.current.startX;
    const dy = e.clientY - dragStartRef.current.startY;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
      hasMovedRef.current = true;
    }
    const newX = Math.max(10, Math.min(window.innerWidth - 130, dragStartRef.current.posX + dx));
    const newY = Math.max(10, Math.min(window.innerHeight - 170, dragStartRef.current.posY + dy));
    setPosition({ x: newX, y: newY });
  }, [isDragging]);

  const endDrag = useCallback((e: React.PointerEvent, onClickFallback?: () => void) => {
    setIsDragging(false);
    if (typeof (e.target as HTMLElement).releasePointerCapture === 'function') {
      try {
        (e.target as HTMLElement).releasePointerCapture(e.pointerId);
      } catch {
        // ignore
      }
    }
    localStorage.setItem('niko_character_pos', JSON.stringify(position));

    if (!hasMovedRef.current) {
      if (onClickFallback) onClickFallback();
    } else {
      // Landing bounce animation
      setIsLanding(true);
      setTimeout(() => setIsLanding(false), 400);
    }
  }, [position]);

  const triggerReaction = useCallback((emo: CharacterEmotion, durationMs = 2500) => {
    setOverrideEmotion({ emotion: emo, expiresAt: Date.now() + durationMs });
  }, []);

  const wakeUp = useCallback(() => {
    lastActivityRef.current = Date.now();
    setInactivityState('ACTIVE');
    setOverrideEmotion({ emotion: 'SURPRISED', expiresAt: Date.now() + 1500 });
  }, []);

  return {
    semanticState,
    posture,
    emotion,
    environmentState,
    position,
    setPosition,
    gaze,
    isDragging,
    isBlinking,
    mouthOpen,
    startDrag,
    onDrag,
    endDrag,
    triggerReaction,
    wakeUp,
  };
}
