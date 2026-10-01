import { describe, it, expect, beforeEach, vi } from 'vitest';
import { SoundService, type SoundEvent } from '../services/soundService';

describe('SoundService - Settings, Ducking & Audio Unlock', () => {
  let service: SoundService;

  beforeEach(() => {
    localStorage.clear();
    service = new SoundService();
  });

  it('loads default sound settings', () => {
    const settings = service.getSettings();
    expect(settings.mute).toBe(false);
    expect(settings.volume).toBe(0.7);
    expect(settings.quietHours.enabled).toBe(false);
    expect(settings.eventToggles.approval).toBe(true);
    expect(settings.eventToggles.message).toBe(true);
  });

  it('toggles master mute and persists to storage', () => {
    service.setMute(true);
    expect(service.getSettings().mute).toBe(true);

    const stored = JSON.parse(localStorage.getItem('niko_sound_settings') || '{}');
    expect(stored.mute).toBe(true);

    service.setMute(false);
    expect(service.getSettings().mute).toBe(false);
  });

  it('clamps volume between 0.0 and 1.0', () => {
    service.setVolume(1.5);
    expect(service.getSettings().volume).toBe(1.0);

    service.setVolume(-0.2);
    expect(service.getSettings().volume).toBe(0.0);

    service.setVolume(0.45);
    expect(service.getSettings().volume).toBe(0.45);
  });

  it('manages per-event sound toggles independently', () => {
    service.setEventToggle('tool', false);
    expect(service.getSettings().eventToggles.tool).toBe(false);
    expect(service.getSettings().eventToggles.approval).toBe(true);

    service.setEventToggle('approval', false);
    expect(service.getSettings().eventToggles.approval).toBe(false);

    service.setEventToggle('tool', true);
    expect(service.getSettings().eventToggles.tool).toBe(true);
  });

  describe('Ducking Logic (Self-Hearing Prevention)', () => {
    it('ducks and mutes sound when microphone is open', () => {
      // Microphone is active
      expect(service.isDucked({ isListening: true, isSpeaking: false })).toBe(true);
      expect(service.isDucked({ isListening: true })).toBe(true);
    });

    it('ducks and mutes sound when NIKO is actively speaking TTS', () => {
      // NIKO TTS output is active
      expect(service.isDucked({ isListening: false, isSpeaking: true })).toBe(true);
      expect(service.isDucked({ isSpeaking: true })).toBe(true);
    });

    it('does not duck when both mic and TTS are idle', () => {
      expect(service.isDucked({ isListening: false, isSpeaking: false })).toBe(false);
      expect(service.isDucked(undefined)).toBe(false);
    });

    it('blocks playSound when ducked', async () => {
      const played = await service.playSound('message', { isListening: true });
      expect(played).toBe(false);

      const playedWhileSpeaking = await service.playSound('tool', { isSpeaking: true });
      expect(playedWhileSpeaking).toBe(false);
    });
  });

  describe('Quiet Hours Logic', () => {
    it('evaluates daytime quiet hours accurately', () => {
      service.setQuietHours({ enabled: true, start: '13:00', end: '15:00' });

      const inside = new Date(2026, 9, 2, 14, 30);
      const outside = new Date(2026, 9, 2, 16, 0);

      expect(service.isQuietHoursActive(inside)).toBe(true);
      expect(service.isQuietHoursActive(outside)).toBe(false);
    });

    it('evaluates overnight quiet hours accurately (22:00 to 08:00)', () => {
      service.setQuietHours({ enabled: true, start: '22:00', end: '08:00' });

      const night = new Date(2026, 9, 2, 23, 15);
      const earlyMorning = new Date(2026, 9, 2, 4, 30);
      const afternoon = new Date(2026, 9, 2, 14, 0);

      expect(service.isQuietHoursActive(night)).toBe(true);
      expect(service.isQuietHoursActive(earlyMorning)).toBe(true);
      expect(service.isQuietHoursActive(afternoon)).toBe(false);
    });

    it('ignores quiet hours calculation when disabled', () => {
      service.setQuietHours({ enabled: false, start: '22:00', end: '08:00' });
      const night = new Date(2026, 9, 2, 23, 15);
      expect(service.isQuietHoursActive(night)).toBe(false);
    });
  });

  describe('Audio Unlock on First User Gesture', () => {
    it('manages audio unlock state', () => {
      expect(service.isAudioUnlocked()).toBe(false);
      const unlocked = service.unlockAudio();
      expect(unlocked).toBe(true);
      expect(service.isAudioUnlocked()).toBe(true);
    });
  });
});
