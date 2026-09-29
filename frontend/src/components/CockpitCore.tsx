import React from 'react';

interface CockpitCoreProps {
  isStreaming: boolean;
  activeModelName: string;
  contextUsed: number;
  contextMax: number;
  elevatedMode: boolean;
  onToggleElevated: () => void;
  onOpenModelSelector: () => void;
}

export const CockpitCore: React.FC<CockpitCoreProps> = ({
  isStreaming,
  activeModelName,
  contextUsed,
  contextMax,
  elevatedMode,
  onToggleElevated,
  onOpenModelSelector,
}) => {
  return (
    <section className="w-full bg-surface-container-low px-gutter-md py-space-sm flex flex-wrap items-center justify-between gap-space-md border-b border-surface-variant/40 shadow-sm select-none">
      {/* Signature Autonomous Engine: The Core */}
      <div className="flex items-center gap-space-lg min-w-0">
        <div className="relative flex items-center justify-center w-14 h-14 flex-shrink-0">
          {/* SVG Concentric Animated Ring Array */}
          <svg className={`w-14 h-14 ${isStreaming ? 'animate-spin-slow' : ''}`} viewBox="0 0 100 100">
            <circle
              cx="50"
              cy="50"
              fill="none"
              opacity="0.35"
              r="44"
              stroke="#ffb020"
              strokeDasharray="12 18"
              strokeWidth="1.5"
            />
            <circle
              className={`${isStreaming ? 'animate-spin-reverse' : ''} origin-center`}
              cx="50"
              cy="50"
              fill="none"
              opacity="0.6"
              r="34"
              stroke="#ffb020"
              strokeDasharray="8 12"
              strokeWidth="1.2"
            />
            <circle
              className={`${isStreaming ? 'animate-spin-fast' : ''} origin-center`}
              cx="50"
              cy="50"
              fill="none"
              opacity="0.9"
              r="24"
              stroke="#ffddb1"
              strokeDasharray="4 6"
              strokeWidth="1"
            />
          </svg>

          {/* Amber Pulsing Nucleus */}
          <div
            className={`absolute w-3.5 h-3.5 rounded-full bg-primary-container shadow-[0_0_12px_rgba(255,176,32,0.85)] ${
              isStreaming ? 'animate-ping' : 'animate-pulse'
            }`}
          />

          {/* Compass Ticks */}
          <div className="absolute inset-0 flex items-center justify-between px-0.5 pointer-events-none">
            <span className="w-1 h-0.5 bg-primary-container/70" />
            <span className="w-1 h-0.5 bg-primary-container/70" />
          </div>
        </div>

        {/* Core Status & Process Vector */}
        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-space-xs">
            <span className="font-mono text-label-caps text-primary-container tracking-wider font-semibold">
              SYS_CORE // L4_DISPATCH
            </span>
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isStreaming ? 'bg-primary-container animate-ping' : 'bg-secondary'
              }`}
            />
          </div>
          <p className="font-mono text-mono-md text-primary tracking-wider font-semibold truncate">
            {isStreaming ? 'STREAMING // SYNTHESIZING INFERENCE' : 'IDLE // STANDBY READY'}
          </p>
          <span className="font-mono text-mono-sm text-on-surface-variant truncate">
            AGENT_LOOP: #10842 · CONTEXT WINDOW {contextUsed.toLocaleString()} / {(contextMax / 1000).toFixed(0)}k
          </span>
        </div>
      </div>

      {/* Telemetry & Hardware Switches */}
      <div className="flex items-center flex-wrap gap-space-sm">
        {/* Model Switcher Pill */}
        <button
          onClick={onOpenModelSelector}
          className="flex items-center gap-space-xs bg-surface-container-high px-space-sm py-1 rounded text-mono-sm font-mono text-on-surface hover:bg-surface-variant transition-colors border border-surface-variant/40"
        >
          <span className="w-2 h-2 rounded-full bg-primary-container" />
          <span className="text-on-surface-variant">Provider:</span>
          <span className="text-primary font-semibold">{activeModelName}</span>
          <span className="material-symbols-outlined text-[14px] text-on-surface-variant">
            expand_more
          </span>
        </button>

        {/* Action Toggle: Autonomous Exec / Elevated Mode */}
        <button
          onClick={onToggleElevated}
          className={`flex items-center gap-space-xs px-space-sm py-1 rounded text-mono-sm font-mono transition-all border ${
            elevatedMode
              ? 'bg-primary-container/20 border-primary-container text-primary-container'
              : 'bg-surface-container border-surface-variant/40 text-on-surface-variant hover:text-on-surface'
          }`}
          title="Toggle elevated autonomous execution with auto-confirm"
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              elevatedMode ? 'bg-primary-container animate-pulse' : 'bg-on-surface-variant'
            }`}
          />
          <span>Exec:</span>
          <span className="font-semibold">{elevatedMode ? 'ELEVATED (AUTONOMOUS)' : 'STANDARD (CONFIRM)'}</span>
        </button>

        {/* Action Toggle: Sandbox Mode */}
        <div className="flex items-center gap-space-xs px-space-sm py-1 bg-surface-container border border-surface-variant/40 text-mono-sm font-mono rounded">
          <span className="material-symbols-outlined text-[13px] text-secondary">
            security
          </span>
          <span className="text-on-surface-variant">Sandbox:</span>
          <span className="text-secondary font-semibold">ISOLATED</span>
        </div>
      </div>
    </section>
  );
};
