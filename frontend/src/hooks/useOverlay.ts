import { useState, useEffect, useCallback, useRef } from 'react';

export type OverlayMode = 'compact' | 'expanded' | 'approval';

export interface OverlayState {
  isVisible: boolean;
  mode: OverlayMode;
  autoHideOnBlur: boolean;
  activeMonitor: string | null;
}

export interface OverlayActions {
  show: (mode?: OverlayMode) => void;
  hide: () => void;
  toggle: () => void;
  setMode: (mode: OverlayMode) => void;
  setAutoHideOnBlur: (enabled: boolean) => void;
  setActiveMonitor: (monitor: string | null) => void;
  focusInput: () => void;
  inputRef: React.RefObject<HTMLInputElement | null>;
}

export type UseOverlayReturn = OverlayState & OverlayActions;

// Native Tauri Window Bridge helper (gracefully degrades in web/test environment)
async function tauriSetVisibility(visible: boolean) {
  try {
    const tauri = (window as unknown as { __TAURI__?: { window?: { getCurrentWindow: () => { show: () => Promise<void>; hide: () => Promise<void>; setFocus: () => Promise<void> } } } }).__TAURI__;
    if (tauri?.window) {
      const currentWin = tauri.window.getCurrentWindow();
      if (visible) {
        await currentWin.show();
        await currentWin.setFocus();
      } else {
        await currentWin.hide();
      }
    }
  } catch {
    // Graceful fallback for non-Tauri browser dev/test
  }
}

export function useOverlay(initialVisible = true, initialMode: OverlayMode = 'compact'): UseOverlayReturn {
  const [isVisible, setIsVisible] = useState<boolean>(initialVisible);
  const [mode, setModeState] = useState<OverlayMode>(initialMode);
  const [autoHideOnBlur, setAutoHideOnBlur] = useState<boolean>(false);
  const [activeMonitor, setActiveMonitor] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const focusInput = useCallback(() => {
    // Defer to next microtask so elements can mount/unhide
    setTimeout(() => {
      inputRef.current?.focus();
    }, 10);
  }, []);

  const show = useCallback((targetMode?: OverlayMode) => {
    setIsVisible(true);
    if (targetMode) {
      setModeState(targetMode);
    }
    tauriSetVisibility(true);
    focusInput();
  }, [focusInput]);

  const hide = useCallback(() => {
    setIsVisible(false);
    tauriSetVisibility(false);
  }, []);

  const toggle = useCallback(() => {
    if (isVisible) {
      hide();
    } else {
      show();
    }
  }, [isVisible, hide, show]);

  const setMode = useCallback((newMode: OverlayMode) => {
    setModeState(newMode);
  }, []);

  // Global Escape key listener (when no modal has called preventDefault)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isVisible && !e.defaultPrevented) {
        hide();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isVisible, hide]);

  // Window Blur listener (Auto-hide on blur if enabled)
  useEffect(() => {
    const handleBlur = () => {
      if (autoHideOnBlur && isVisible) {
        hide();
      }
    };

    window.addEventListener('blur', handleBlur);
    return () => window.removeEventListener('blur', handleBlur);
  }, [autoHideOnBlur, isVisible, hide]);

  return {
    isVisible,
    mode,
    autoHideOnBlur,
    activeMonitor,
    show,
    hide,
    toggle,
    setMode,
    setAutoHideOnBlur,
    setActiveMonitor,
    focusInput,
    inputRef,
  };
}
