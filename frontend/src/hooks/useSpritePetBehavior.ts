import { useState, useEffect, useRef, useCallback } from 'react';
import type { OrbState } from './useOrbState';

export interface UseSpritePetBehaviorOptions {
  hasPendingApproval?: boolean;
  error?: string | null;
  isCoolingDown?: boolean;
  activeToolCallsCount?: number;
  orbState?: OrbState;
  isStreaming?: boolean;
  isSpeaking?: boolean;
  lastToolStatus?: 'success' | 'error' | null;
  inactivityTimeoutMs?: number; // default 5 min (300,000 ms)
  clickReactionCooldownMs?: number; // default 1,800 ms
  manualStateOverride?: string | null;
  onWakeUp?: () => void;
}

export type ClickReactionType = 'happy' | 'startled' | 'annoyed';

export interface UseSpritePetBehaviorReturn {
  activeState: string;
  direction: 'left' | 'right';
  setDirection: (dir: 'left' | 'right') => void;
  isAsleep: boolean;
  isSitting: boolean;
  isReacting: boolean;
  inactivityElapsedMs: number;
  handleClick: () => ClickReactionType | null;
  wakeUp: () => void;
  triggerSleepNow: () => void;
  triggerReactionManual: (reaction: ClickReactionType) => void;
}

export function useSpritePetBehavior({
  hasPendingApproval = false,
  error = null,
  isCoolingDown = false,
  activeToolCallsCount = 0,
  orbState = 'idle',
  isStreaming = false,
  isSpeaking = false,
  lastToolStatus = null,
  inactivityTimeoutMs = 5 * 60 * 1000, // 5 minutes default
  clickReactionCooldownMs = 1800,
  manualStateOverride = null,
  onWakeUp,
}: UseSpritePetBehaviorOptions = {}): UseSpritePetBehaviorReturn {
  const [direction, setDirection] = useState<'left' | 'right'>('left');
  const [activeReaction, setActiveReaction] = useState<ClickReactionType | null>(null);
  const [lastActivityTime, setLastActivityTime] = useState<number>(() => Date.now());
  const [inactivityElapsedMs, setInactivityElapsedMs] = useState<number>(0);
  const [isForceSleeping, setIsForceSleeping] = useState<boolean>(false);

  const lastClickTimeRef = useRef<number>(0);
  const reactionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onWakeUpRef = useRef(onWakeUp);
  onWakeUpRef.current = onWakeUp;

  // Wake up pet and reset inactivity timer
  const wakeUp = useCallback(() => {
    setLastActivityTime(Date.now());
    setInactivityElapsedMs(0);
    setIsForceSleeping(false);
    if (onWakeUpRef.current) {
      onWakeUpRef.current();
    }
  }, []);

  // Developer / test shortcut to trigger sleep immediately
  const triggerSleepNow = useCallback(() => {
    setIsForceSleeping(true);
    setInactivityElapsedMs(inactivityTimeoutMs + 5000);
  }, [inactivityTimeoutMs]);

  // Wake on any backend activity
  const isBackendActive =
    hasPendingApproval ||
    Boolean(error) ||
    isCoolingDown ||
    activeToolCallsCount > 0 ||
    isStreaming ||
    isSpeaking ||
    orbState !== 'idle';

  useEffect(() => {
    if (isBackendActive) {
      wakeUp();
    }
  }, [isBackendActive, wakeUp]);

  // Inactivity Tick Timer
  useEffect(() => {
    // If set to 0 or negative, disable sleep
    if (inactivityTimeoutMs <= 0) return;

    const interval = setInterval(() => {
      const now = Date.now();
      const elapsed = isForceSleeping ? inactivityTimeoutMs + 5000 : now - lastActivityTime;
      setInactivityElapsedMs(elapsed);
    }, 1000);

    return () => clearInterval(interval);
  }, [lastActivityTime, inactivityTimeoutMs, isForceSleeping]);

  // Click reaction logic with spam protection cooldown
  const triggerReaction = useCallback(
    (chosen: ClickReactionType) => {
      wakeUp();
      setActiveReaction(chosen);

      if (reactionTimerRef.current) {
        clearTimeout(reactionTimerRef.current);
      }

      // Reaction duration: 1.5s
      reactionTimerRef.current = setTimeout(() => {
        setActiveReaction(null);
        reactionTimerRef.current = null;
      }, 1500);
    },
    [wakeUp]
  );

  const handleClick = useCallback((): ClickReactionType | null => {
    const now = Date.now();
    // Enforce reaction cooldown
    if (now - lastClickTimeRef.current < clickReactionCooldownMs) {
      // Cooldown active: ignore spam clicks
      wakeUp();
      return null;
    }

    lastClickTimeRef.current = now;

    // Pick random reaction: happy, startled, annoyed
    const reactions: ClickReactionType[] = ['happy', 'startled', 'annoyed'];
    const chosen = reactions[Math.floor(Math.random() * reactions.length)];
    triggerReaction(chosen);
    return chosen;
  }, [clickReactionCooldownMs, triggerReaction, wakeUp]);

  const triggerReactionManual = useCallback(
    (reaction: ClickReactionType) => {
      triggerReaction(reaction);
    },
    [triggerReaction]
  );

  // Inactivity State resolution
  const isInactive = inactivityTimeoutMs > 0 && inactivityElapsedMs >= inactivityTimeoutMs;
  // If inactive for < 4 seconds past threshold: sit, then deep sleep
  const isSitting = isInactive && inactivityElapsedMs < inactivityTimeoutMs + 4000;
  const isAsleep = isInactive && inactivityElapsedMs >= inactivityTimeoutMs + 4000;

  // Resolve Active State according to Strict Priority:
  // 0. Manual Dev Override
  // 1. waiting_approval (curious/pointing/notification-reaction, never angry)
  // 2. error (sad, quiet dejected, never angry)
  // 3. quota cooldown (sleepy downtime)
  // 4. acting (laptop typing, writing)
  // 5. thinking (thought cloud, pondering)
  // 6. speaking (talking articulation)
  // 7. success (celebration, dancing)
  // 8. click reaction (happy / surprised / mouse_interaction)
  // 9. local idle behavior (sitting / sleeping / idle)
  let activeState = 'idle';

  if (manualStateOverride) {
    activeState = manualStateOverride;
  } else if (hasPendingApproval || orbState === 'confirm') {
    activeState = 'waiting_approval';
  } else if (Boolean(error) || lastToolStatus === 'error') {
    activeState = 'error';
  } else if (isCoolingDown) {
    activeState = 'cooldown';
  } else if (activeToolCallsCount > 0 || orbState === 'acting') {
    activeState = 'acting';
  } else if (isStreaming || orbState === 'thinking') {
    activeState = 'thinking';
  } else if (isSpeaking) {
    activeState = 'speaking';
  } else if (lastToolStatus === 'success') {
    activeState = 'success';
  } else if (activeReaction !== null) {
    switch (activeReaction) {
      case 'happy':
        activeState = 'happy';
        break;
      case 'startled':
        activeState = 'surprised';
        break;
      case 'annoyed':
        // Map annoyed to mouse_interaction frame 3 ('annoyed_click') or bored
        activeState = 'mouse_interaction';
        break;
    }
  } else if (isAsleep) {
    activeState = 'sleeping';
  } else if (isSitting) {
    activeState = 'sitting';
  } else {
    activeState = 'idle';
  }

  return {
    activeState,
    direction,
    setDirection,
    isAsleep,
    isSitting,
    isReacting: activeReaction !== null,
    inactivityElapsedMs,
    handleClick,
    wakeUp,
    triggerSleepNow,
    triggerReactionManual,
  };
}

export default useSpritePetBehavior;
