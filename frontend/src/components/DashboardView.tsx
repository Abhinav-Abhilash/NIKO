import React from 'react';
import type { SystemMetrics } from '../types';

interface DashboardViewProps {
  metrics: SystemMetrics;
  onRefresh: () => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({ metrics, onRefresh }) => {
  return (
    <div className="flex-1 overflow-y-auto p-gutter-md flex flex-col gap-6 max-w-6xl mx-auto w-full">
      {/* View Header */}
      <div className="flex items-center justify-between border-b border-surface-variant/40 pb-4">
        <div>
          <h1 className="font-mono text-xl font-bold text-on-surface">
            LIVE TELEMETRY & SYSTEM BENCHMARKS
          </h1>
          <p className="font-mono text-xs text-on-surface-variant">
            Real-time diagnostics, hardware allocation, and LLM latency telemetry.
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="flex items-center gap-2 px-3 py-1.5 bg-surface-container hover:bg-surface-variant border border-surface-variant/60 rounded text-xs font-mono text-on-surface transition-colors"
        >
          <span className="material-symbols-outlined text-sm">refresh</span>
          <span>Refresh Metrics</span>
        </button>
      </div>

      {/* Main Metric Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Core State */}
        <div className="bg-surface-container-low p-4 rounded-xl border border-surface-variant/40 flex flex-col gap-2">
          <div className="flex items-center justify-between text-mono-sm font-mono text-on-surface-variant">
            <span>CORE ENGINE</span>
            <span className={`w-2 h-2 rounded-full ${metrics.coreOnline ? 'bg-secondary animate-pulse' : 'bg-error'}`} />
          </div>
          <div className="font-mono text-2xl font-bold text-on-surface">
            {metrics.coreOnline ? 'ONLINE' : 'OFFLINE'}
          </div>
          <div className="text-[11px] font-mono text-secondary">
            IPC WebSocket active: 7421
          </div>
        </div>

        {/* CPU Utilization */}
        <div className="bg-surface-container-low p-4 rounded-xl border border-surface-variant/40 flex flex-col gap-2">
          <div className="flex items-center justify-between text-mono-sm font-mono text-on-surface-variant">
            <span>CPU UTILIZATION</span>
            <span className="material-symbols-outlined text-base text-primary-container">memory</span>
          </div>
          <div className="font-mono text-2xl font-bold text-on-surface">
            {metrics.cpuPercent.toFixed(1)}%
          </div>
          <div className="w-full bg-surface-container h-1.5 rounded-full overflow-hidden">
            <div
              className="bg-primary-container h-full transition-all duration-500"
              style={{ width: `${Math.min(100, metrics.cpuPercent)}%` }}
            />
          </div>
        </div>

        {/* RAM Usage */}
        <div className="bg-surface-container-low p-4 rounded-xl border border-surface-variant/40 flex flex-col gap-2">
          <div className="flex items-center justify-between text-mono-sm font-mono text-on-surface-variant">
            <span>RAM CAPACITY</span>
            <span className="material-symbols-outlined text-base text-primary-container">developer_board</span>
          </div>
          <div className="font-mono text-2xl font-bold text-on-surface">
            {metrics.ramUsageGb.toFixed(1)} <span className="text-sm font-normal text-on-surface-variant">/ {metrics.ramTotalGb} GB</span>
          </div>
          <div className="w-full bg-surface-container h-1.5 rounded-full overflow-hidden">
            <div
              className="bg-secondary h-full transition-all duration-500"
              style={{ width: `${(metrics.ramUsageGb / metrics.ramTotalGb) * 100}%` }}
            />
          </div>
        </div>

        {/* Latency / Ping */}
        <div className="bg-surface-container-low p-4 rounded-xl border border-surface-variant/40 flex flex-col gap-2">
          <div className="flex items-center justify-between text-mono-sm font-mono text-on-surface-variant">
            <span>IPC LATENCY</span>
            <span className="material-symbols-outlined text-base text-secondary">speed</span>
          </div>
          <div className="font-mono text-2xl font-bold text-secondary">
            {metrics.pingMs} ms
          </div>
          <div className="text-[11px] font-mono text-on-surface-variant">
            Zero network hop (LocalHost)
          </div>
        </div>
      </div>

      {/* Provider Latency & Health Matrix */}
      <div className="bg-surface-container-low p-5 rounded-xl border border-surface-variant/40 flex flex-col gap-4">
        <h3 className="font-mono text-sm font-bold text-primary tracking-wider uppercase">
          Provider Latency & Availability Matrix
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="p-3 bg-surface-container rounded-lg border border-surface-variant/40 flex flex-col gap-1 font-mono">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-on-surface">Groq Cloud</span>
              <span className="text-secondary font-bold text-[10px] px-1.5 py-0.5 bg-secondary/10 rounded">ACTIVE</span>
            </div>
            <div className="text-on-surface-variant text-[11px]">Model: llama-3.3-70b-versatile</div>
            <div className="text-primary-container text-xs font-semibold mt-1">Average TTFT: ~120ms</div>
          </div>

          <div className="p-3 bg-surface-container rounded-lg border border-surface-variant/40 flex flex-col gap-1 font-mono">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-on-surface">Google Gemini</span>
              <span className="text-secondary font-bold text-[10px] px-1.5 py-0.5 bg-secondary/10 rounded">STANDBY</span>
            </div>
            <div className="text-on-surface-variant text-[11px]">Model: gemini-2.0-flash</div>
            <div className="text-primary-container text-xs font-semibold mt-1">Average TTFT: ~280ms</div>
          </div>

          <div className="p-3 bg-surface-container rounded-lg border border-surface-variant/40 flex flex-col gap-1 font-mono">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-on-surface">Local Ollama</span>
              <span className="text-on-surface-variant font-bold text-[10px] px-1.5 py-0.5 bg-surface-variant rounded">OFFLINE</span>
            </div>
            <div className="text-on-surface-variant text-[11px]">Model: qwen2.5:7b-instruct</div>
            <div className="text-on-surface-variant text-xs font-semibold mt-1">Auto-skipped when unreachable</div>
          </div>
        </div>
      </div>
    </div>
  );
};
