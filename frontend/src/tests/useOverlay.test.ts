import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useOverlay } from '../hooks/useOverlay';

describe('useOverlay hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('initializes with default visibility and mode', () => {
    const { result } = renderHook(() => useOverlay(true, 'compact'));
    expect(result.current.isVisible).toBe(true);
    expect(result.current.mode).toBe('compact');
    expect(result.current.autoHideOnBlur).toBe(false);
  });

  it('toggles visibility and changes mode', () => {
    const { result } = renderHook(() => useOverlay(true, 'compact'));

    act(() => {
      result.current.hide();
    });
    expect(result.current.isVisible).toBe(false);

    act(() => {
      result.current.show('expanded');
    });
    expect(result.current.isVisible).toBe(true);
    expect(result.current.mode).toBe('expanded');

    act(() => {
      result.current.toggle();
    });
    expect(result.current.isVisible).toBe(false);
  });

  it('hides on global Escape key press', () => {
    const { result } = renderHook(() => useOverlay(true, 'compact'));
    expect(result.current.isVisible).toBe(true);

    act(() => {
      const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true });
      window.dispatchEvent(event);
    });

    expect(result.current.isVisible).toBe(false);
  });

  it('hides on blur only when autoHideOnBlur is enabled', () => {
    const { result } = renderHook(() => useOverlay(true, 'compact'));

    // Blur when disabled
    act(() => {
      window.dispatchEvent(new Event('blur'));
    });
    expect(result.current.isVisible).toBe(true);

    // Enable autoHideOnBlur
    act(() => {
      result.current.setAutoHideOnBlur(true);
    });
    expect(result.current.autoHideOnBlur).toBe(true);

    // Blur when enabled
    act(() => {
      window.dispatchEvent(new Event('blur'));
    });
    expect(result.current.isVisible).toBe(false);
  });

  it('supports pet mode toggling', () => {
    const { result } = renderHook(() => useOverlay(true, 'compact'));
    expect(result.current.mode).toBe('compact');

    act(() => {
      result.current.togglePet();
    });
    expect(result.current.mode).toBe('pet');

    act(() => {
      result.current.togglePet();
    });
    expect(result.current.mode).toBe('compact');
  });
});
