export type OrbStateType = 'idle' | 'thinking' | 'acting' | 'confirm';

export interface UseOrbStateOptions {
  hasPendingApproval?: boolean;
  isStreaming?: boolean;
  activeToolCallsCount?: number;
}

export interface UseOrbStateReturn {
  orbState: OrbStateType;
  isIdle: boolean;
  isThinking: boolean;
  isActing: boolean;
  isConfirm: boolean;
}

export function useOrbState(options: UseOrbStateOptions): UseOrbStateReturn {
  const { hasPendingApproval = false, isStreaming = false, activeToolCallsCount = 0 } = options;

  let orbState: OrbStateType = 'idle';

  if (hasPendingApproval) {
    orbState = 'confirm';
  } else if (activeToolCallsCount > 0) {
    orbState = 'acting';
  } else if (isStreaming) {
    orbState = 'thinking';
  } else {
    orbState = 'idle';
  }

  return {
    orbState,
    isIdle: orbState === 'idle',
    isThinking: orbState === 'thinking',
    isActing: orbState === 'acting',
    isConfirm: orbState === 'confirm',
  };
}
