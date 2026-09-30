import { useState, useEffect, useCallback } from 'react';
import { wsClient } from '../services/websocket';

export interface ProviderCooldownInfo {
  isCoolingDown: boolean;
  coolingRole: string | null;
  shortestResetSeconds: number | null;
  cooldownMessage: string | null;
}

export interface UseProviderStatusReturn extends ProviderCooldownInfo {
  clearCooldown: () => void;
}

export function useProviderStatus(): UseProviderStatusReturn {
  const [cooldown, setCooldown] = useState<ProviderCooldownInfo>({
    isCoolingDown: false,
    coolingRole: null,
    shortestResetSeconds: null,
    cooldownMessage: null,
  });

  const clearCooldown = useCallback(() => {
    setCooldown({
      isCoolingDown: false,
      coolingRole: null,
      shortestResetSeconds: null,
      cooldownMessage: null,
    });
  }, []);

  useEffect(() => {
    const unsubCooldown = wsClient.on('chat:cooldown_banner', (data: {
      role?: string;
      shortest_reset_seconds?: number;
      message?: string;
    }) => {
      setCooldown({
        isCoolingDown: true,
        coolingRole: data.role || null,
        shortestResetSeconds: data.shortest_reset_seconds ?? null,
        cooldownMessage: data.message || 'All providers cooling down for role',
      });
    });

    return () => {
      unsubCooldown();
    };
  }, []);

  return {
    ...cooldown,
    clearCooldown,
  };
}
