import { useState, useCallback, useEffect } from 'react';
import {
  soundService,
  type SoundSettings,
  type SoundEvent,
  type SoundPlaybackContext,
} from '../services/soundService';

export interface UseSoundReturn {
  settings: SoundSettings;
  updateSettings: (partial: Partial<SoundSettings>) => void;
  setMute: (mute: boolean) => void;
  setVolume: (volume: number) => void;
  setEventToggle: (event: SoundEvent, enabled: boolean) => void;
  setQuietHours: (enabled: boolean, start?: string, end?: string) => void;
  playSound: (event: SoundEvent, context?: SoundPlaybackContext) => Promise<boolean>;
  isQuietHoursActive: boolean;
  isUnlocked: boolean;
  unlockAudio: () => void;
}

export function useSound(): UseSoundReturn {
  const [settings, setSettingsState] = useState<SoundSettings>(() => soundService.getSettings());
  const [isUnlocked, setIsUnlocked] = useState<boolean>(() => soundService.isAudioUnlocked());

  const updateSettings = useCallback((partial: Partial<SoundSettings>) => {
    const updated = soundService.updateSettings(partial);
    setSettingsState(updated);
  }, []);

  const setMute = useCallback((mute: boolean) => {
    soundService.setMute(mute);
    setSettingsState(soundService.getSettings());
  }, []);

  const setVolume = useCallback((volume: number) => {
    soundService.setVolume(volume);
    setSettingsState(soundService.getSettings());
  }, []);

  const setEventToggle = useCallback((event: SoundEvent, enabled: boolean) => {
    soundService.setEventToggle(event, enabled);
    setSettingsState(soundService.getSettings());
  }, []);

  const setQuietHours = useCallback((enabled: boolean, start?: string, end?: string) => {
    soundService.setQuietHours({
      enabled,
      ...(start ? { start } : {}),
      ...(end ? { end } : {}),
    });
    setSettingsState(soundService.getSettings());
  }, []);

  const playSound = useCallback((event: SoundEvent, context?: SoundPlaybackContext) => {
    return soundService.playSound(event, context);
  }, []);

  const unlockAudio = useCallback(() => {
    const res = soundService.unlockAudio();
    setIsUnlocked(res);
  }, []);

  useEffect(() => {
    const handleGesture = () => {
      setIsUnlocked(soundService.isAudioUnlocked());
    };
    window.addEventListener('pointerdown', handleGesture, { once: true });
    return () => window.removeEventListener('pointerdown', handleGesture);
  }, []);

  return {
    settings,
    updateSettings,
    setMute,
    setVolume,
    setEventToggle,
    setQuietHours,
    playSound,
    isQuietHoursActive: soundService.isQuietHoursActive(),
    isUnlocked,
    unlockAudio,
  };
}
