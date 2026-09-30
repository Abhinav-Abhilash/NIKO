/**
 * NIKO Theme Design Tokens
 * 
 * Central registry for all visual variables (colors, typography, radii, shadows, glow).
 * Flow design imports will populate and reference these values.
 */

export const tokens = {
  colors: {
    // Core backgrounds
    background: 'transparent',
    surface: 'rgba(15, 23, 42, 0.85)',
    surfaceElevated: 'rgba(30, 41, 59, 0.90)',
    surfaceMuted: 'rgba(51, 65, 85, 0.50)',
    
    // Borders
    border: 'rgba(148, 163, 184, 0.15)',
    borderFocus: 'rgba(56, 189, 248, 0.50)',
    borderError: 'rgba(239, 68, 68, 0.50)',

    // Typography
    textPrimary: '#F8FAFC',
    textSecondary: '#94A3B8',
    textMuted: '#64748B',
    textAccent: '#38BDF8',

    // Accents & State
    accent: '#38BDF8',
    accentHover: '#0EA5E9',
    success: '#10B981',
    warning: '#F59E0B',
    error: '#EF4444',

    // Reactor Core Glow
    coreIdle: '#38BDF8',
    coreThinking: '#818CF8',
    coreActing: '#34D399',
    coreConfirm: '#F59E0B',
  },

  typography: {
    fontSans: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    fontMono: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    sizeXs: '0.75rem',
    sizeSm: '0.875rem',
    sizeBase: '1rem',
    sizeLg: '1.125rem',
    sizeXl: '1.25rem',
  },

  radii: {
    sm: '0.375rem',
    md: '0.5rem',
    lg: '0.75rem',
    xl: '1rem',
    full: '9999px',
  },

  shadows: {
    overlay: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5)',
    coreGlow: '0 0 25px rgba(56, 189, 248, 0.45)',
  },
} as const;

export type ThemeTokens = typeof tokens;
