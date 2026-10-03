export interface PetSettings {
  sizeScale: number; // 0.5 to 1.5
  soundEnabled: boolean;
  inactivityTimeoutMs: number; // in milliseconds (e.g. 300,000 for 5 min)
  startPosition: 'bottom-right' | 'center' | 'custom';
}

export const DEFAULT_PET_SETTINGS: PetSettings = {
  sizeScale: 1.0,
  soundEnabled: true,
  inactivityTimeoutMs: 5 * 60 * 1000, // 5 min
  startPosition: 'bottom-right',
};

const STORAGE_KEY = 'niko_pet_settings';

export function loadPetSettings(): PetSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      return { ...DEFAULT_PET_SETTINGS, ...JSON.parse(raw) };
    }
  } catch {
    // fallback
  }
  return DEFAULT_PET_SETTINGS;
}

export function savePetSettings(settings: PetSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // ignore
  }
}
