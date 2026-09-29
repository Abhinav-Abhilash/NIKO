import React from 'react';
import type { SystemMetrics } from '../types';

interface HeaderProps {
  metrics: SystemMetrics;
  activeModelName: string;
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
  onOpenCommandPalette: () => void;
  onOpenShortcutsHelp: () => void;
  onOpenSettings: () => void;
  onOpenLogin: () => void;
  currentUser?: { username: string; role: string } | null;
}

export const Header: React.FC<HeaderProps> = ({
  metrics,
  activeModelName,
  theme,
  onToggleTheme,
  onOpenCommandPalette,
  onOpenShortcutsHelp,
  onOpenSettings,
  onOpenLogin,
  currentUser,
}) => {
  return (
    <header className="fixed top-0 left-16 right-0 h-12 bg-surface-container-lowest/95 backdrop-blur border-b border-surface-variant/40 z-40 px-gutter flex items-center justify-between select-none">
      {/* Real-Time Telemetry Tickers */}
      <div className="flex items-center gap-space-md overflow-x-auto no-scrollbar">
        {/* Core Status */}
        <div className="flex items-center gap-space-xs text-mono-sm font-mono text-on-surface-variant">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              metrics.coreOnline ? 'bg-secondary animate-pulse' : 'bg-error'
            }`}
          />
          <span className="text-on-surface font-semibold">CORE:</span>
          <span className={metrics.coreOnline ? 'text-secondary' : 'text-error'}>
            {metrics.coreOnline ? 'ONLINE' : 'OFFLINE'}
          </span>
        </div>

        <div className="h-3 w-[1px] bg-surface-variant/60" />

        {/* CPU */}
        <div className="flex items-center gap-space-xs text-mono-sm font-mono text-on-surface-variant">
          <span>CPU:</span>
          <span className="text-on-surface">{metrics.cpuPercent.toFixed(0)}%</span>
        </div>

        <div className="h-3 w-[1px] bg-surface-variant/60" />

        {/* RAM */}
        <div className="flex items-center gap-space-xs text-mono-sm font-mono text-on-surface-variant">
          <span>RAM:</span>
          <span className="text-on-surface">
            {metrics.ramUsageGb.toFixed(1)} / {metrics.ramTotalGb.toFixed(0)} GB
          </span>
        </div>

        <div className="h-3 w-[1px] bg-surface-variant/60" />

        {/* PING */}
        <div className="flex items-center gap-space-xs text-mono-sm font-mono text-on-surface-variant">
          <span>PING:</span>
          <span className="text-primary-container font-semibold">{metrics.pingMs}ms</span>
        </div>
      </div>

      {/* Right Controls & Profile */}
      <div className="flex items-center gap-space-sm">
        {/* Active Model Switcher Pill */}
        <button
          onClick={onOpenSettings}
          className="flex items-center gap-space-xs px-space-sm py-1 bg-surface-container-low border border-surface-variant/60 hover:border-outline text-mono-sm font-mono rounded transition-colors"
          title="Configure Model Roles & Fallbacks"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-primary-container" />
          <span className="text-on-surface-variant">MODEL:</span>
          <span className="text-on-surface font-medium truncate max-w-[140px]">
            {activeModelName}
          </span>
          <span className="material-symbols-outlined text-[14px] text-on-surface-variant">
            expand_more
          </span>
        </button>

        {/* ⌘K Command Palette Button */}
        <button
          onClick={onOpenCommandPalette}
          className="flex items-center gap-space-xs px-space-sm py-1 bg-surface-container-low border border-surface-variant/60 hover:border-outline text-on-surface-variant hover:text-on-surface transition-colors rounded text-mono-sm font-mono"
          type="button"
          title="Command Palette (⌘K)"
        >
          <span>Search & Exec</span>
          <kbd className="px-1 py-0.5 bg-surface-container-high border border-surface-variant rounded text-[10px] text-on-surface-variant font-mono">
            ⌘K
          </kbd>
        </button>

        {/* Shortcuts Help Button (?) */}
        <button
          onClick={onOpenShortcutsHelp}
          className="w-8 h-8 rounded-lg bg-surface-container-low border border-surface-variant/60 hover:border-outline flex items-center justify-center text-on-surface-variant hover:text-on-surface transition-colors"
          title="Keyboard Shortcuts Reference (?)"
        >
          <span className="material-symbols-outlined text-sm">help_outline</span>
        </button>

        {/* Theme Toggle Button */}
        <button
          onClick={onToggleTheme}
          className="w-8 h-8 rounded-lg bg-surface-container-low border border-surface-variant/60 hover:border-outline flex items-center justify-center text-primary-container hover:text-primary transition-colors"
          title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Theme`}
        >
          <span className="material-symbols-outlined text-sm">
            {theme === 'dark' ? 'light_mode' : 'dark_mode'}
          </span>
        </button>

        <div className="h-4 w-[1px] bg-surface-variant/60" />

        {/* Operator Profile Icon */}
        <button
          onClick={onOpenLogin}
          className="w-8 h-8 rounded-full bg-primary flex items-center justify-center hover:ring-2 hover:ring-primary-container transition-all"
          title={currentUser ? `Operator: ${currentUser.username} (${currentUser.role})` : 'Click to Login'}
        >
          <span className="material-symbols-outlined text-on-primary text-[18px]">
            {currentUser ? 'verified_user' : 'person'}
          </span>
        </button>
      </div>
    </header>
  );
};
