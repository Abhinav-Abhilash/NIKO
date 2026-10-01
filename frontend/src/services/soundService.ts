/**
 * NIKO Sound System Service
 * 
 * Handles audio playback for companion events, human-in-the-loop alerts,
 * microphone/TTS ducking to prevent feedback loops, quiet hours gating,
 * and the browser audio-unlock-on-first-interaction lifecycle.
 */

export type SoundEvent =
  | 'message'
  | 'tool'
  | 'approval'
  | 'error'
  | 'click'
  | 'wake';

export interface QuietHoursConfig {
  enabled: boolean;
  start: string; // "HH:MM" e.g. "22:00"
  end: string;   // "HH:MM" e.g. "08:00"
}

export interface SoundSettings {
  mute: boolean;
  volume: number; // 0.0 to 1.0
  quietHours: QuietHoursConfig;
  eventToggles: Record<SoundEvent, boolean>;
}

export interface SoundPlaybackContext {
  isListening?: boolean;
  isSpeaking?: boolean;
}

export const DEFAULT_SOUND_SETTINGS: SoundSettings = {
  mute: false,
  volume: 0.7,
  quietHours: {
    enabled: false,
    start: '22:00',
    end: '08:00',
  },
  eventToggles: {
    approval: true,
    message: true,
    tool: true,
    error: true,
    click: true,
    wake: true,
  },
};

const SOUND_FILE_MAP: Record<SoundEvent, string> = {
  approval: '/sounds/approval.wav',
  message: '/sounds/message.wav',
  tool: '/sounds/tool.wav',
  error: '/sounds/error.wav',
  click: '/sounds/click.wav',
  wake: '/sounds/wake.wav',
};

export class SoundService {
  private settings: SoundSettings;
  private isUnlocked = false;
  private audioCtx: AudioContext | null = null;
  private audioCache = new Map<SoundEvent, HTMLAudioElement>();

  constructor() {
    this.settings = this.loadSettings();
    this.setupUnlockListeners();
  }

  public getSettings(): SoundSettings {
    return { ...this.settings };
  }

  public updateSettings(partial: Partial<SoundSettings>): SoundSettings {
    this.settings = {
      ...this.settings,
      ...partial,
      volume: partial.volume !== undefined ? Math.max(0, Math.min(1, partial.volume)) : this.settings.volume,
      eventToggles: {
        ...this.settings.eventToggles,
        ...(partial.eventToggles || {}),
      },
      quietHours: {
        ...this.settings.quietHours,
        ...(partial.quietHours || {}),
      },
    };
    this.saveSettings();
    return this.getSettings();
  }

  public setMute(mute: boolean): void {
    this.updateSettings({ mute });
  }

  public setVolume(volume: number): void {
    this.updateSettings({ volume });
  }

  public setEventToggle(event: SoundEvent, enabled: boolean): void {
    this.updateSettings({
      eventToggles: {
        ...this.settings.eventToggles,
        [event]: enabled,
      },
    });
  }

  public setQuietHours(quietHours: Partial<QuietHoursConfig>): void {
    this.updateSettings({
      quietHours: {
        ...this.settings.quietHours,
        ...quietHours,
      },
    });
  }

  /**
   * Evaluates whether a given timestamp falls within quiet hours.
   */
  public isQuietHoursActive(date: Date = new Date()): boolean {
    if (!this.settings.quietHours.enabled) return false;

    const { start, end } = this.settings.quietHours;
    const [startH, startM] = start.split(':').map(Number);
    const [endH, endM] = end.split(':').map(Number);

    const curH = date.getHours();
    const curM = date.getMinutes();
    const curTotal = curH * 60 + curM;
    const startTotal = startH * 60 + startM;
    const endTotal = endH * 60 + endM;

    if (startTotal <= endTotal) {
      // Standard daytime quiet hours (e.g. 13:00 to 15:00)
      return curTotal >= startTotal && curTotal < endTotal;
    } else {
      // Overnight quiet hours (e.g. 22:00 to 08:00)
      return curTotal >= startTotal || curTotal < endTotal;
    }
  }

  /**
   * Determines whether sound should be ducked (muted) because the microphone is
   * open or NIKO is actively speaking, preventing acoustic feedback.
   */
  public isDucked(context?: SoundPlaybackContext): boolean {
    if (!context) return false;
    return Boolean(context.isListening || context.isSpeaking);
  }

  /**
   * Primary entry point for playing a local sound cue.
   * Returns true if sound played, false if blocked (muted, quiet hours, ducked, disabled).
   */
  public async playSound(event: SoundEvent, context?: SoundPlaybackContext): Promise<boolean> {
    // 1. Master mute check
    if (this.settings.mute) return false;

    // 2. Volume zero check
    if (this.settings.volume <= 0) return false;

    // 3. Per-event toggle check
    if (!this.settings.eventToggles[event]) return false;

    // 4. Quiet hours check
    if (this.isQuietHoursActive()) return false;

    // 5. Mic / TTS Ducking check (prevent hearing itself)
    if (this.isDucked(context)) return false;

    // 6. Ensure AudioContext is unlocked
    this.unlockAudio();

    try {
      const audio = this.getAudioElement(event);
      audio.volume = this.settings.volume;
      audio.currentTime = 0;
      await audio.play();
      return true;
    } catch {
      // Gracefully degrade in test environments or if user hasn't interacted yet
      return false;
    }
  }

  /**
   * Resumes the AudioContext and unlocks browser autoplay on first user interaction.
   */
  public unlockAudio(): boolean {
    if (this.isUnlocked) return true;

    try {
      if (typeof window !== 'undefined') {
        const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        if (AudioCtx && !this.audioCtx) {
          this.audioCtx = new AudioCtx();
        }
        if (this.audioCtx && this.audioCtx.state === 'suspended') {
          this.audioCtx.resume();
        }
        this.isUnlocked = true;
      }
    } catch {
      // Ignore in environments without Web Audio API
    }
    return this.isUnlocked;
  }

  public isAudioUnlocked(): boolean {
    return this.isUnlocked;
  }

  private getAudioElement(event: SoundEvent): HTMLAudioElement {
    let audio = this.audioCache.get(event);
    if (!audio) {
      audio = new Audio(SOUND_FILE_MAP[event]);
      this.audioCache.set(event, audio);
    }
    return audio;
  }

  private setupUnlockListeners(): void {
    if (typeof window === 'undefined') return;

    const handleUnlock = () => {
      this.unlockAudio();
      window.removeEventListener('pointerdown', handleUnlock);
      window.removeEventListener('keydown', handleUnlock);
      window.removeEventListener('click', handleUnlock);
    };

    window.addEventListener('pointerdown', handleUnlock, { once: true, passive: true });
    window.addEventListener('keydown', handleUnlock, { once: true, passive: true });
    window.addEventListener('click', handleUnlock, { once: true, passive: true });
  }

  private loadSettings(): SoundSettings {
    if (typeof window === 'undefined') return { ...DEFAULT_SOUND_SETTINGS };
    try {
      const stored = localStorage.getItem('niko_sound_settings');
      if (stored) {
        const parsed = JSON.parse(stored);
        return {
          ...DEFAULT_SOUND_SETTINGS,
          ...parsed,
          eventToggles: {
            ...DEFAULT_SOUND_SETTINGS.eventToggles,
            ...(parsed.eventToggles || {}),
          },
          quietHours: {
            ...DEFAULT_SOUND_SETTINGS.quietHours,
            ...(parsed.quietHours || {}),
          },
        };
      }
    } catch {
      // ignore
    }
    return { ...DEFAULT_SOUND_SETTINGS };
  }

  private saveSettings(): void {
    if (typeof window === 'undefined') return;
    try {
      localStorage.setItem('niko_sound_settings', JSON.stringify(this.settings));
    } catch {
      // ignore
    }
  }
}

export const soundService = new SoundService();
