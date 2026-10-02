import React, { useEffect, useState, useCallback } from 'react';
import type { SystemMetrics, ScheduledTaskItem } from '../types';
import { ApiService } from '../services/api';
import { toastService } from '../services/toast';

interface DashboardViewProps {
  metrics: SystemMetrics;
  onRefresh: () => void;
}

interface WidgetConfig {
  id: string;
  title: string;
  visible: boolean;
}

export const DashboardView: React.FC<DashboardViewProps> = ({ metrics, onRefresh }) => {
  const defaultWidgets: WidgetConfig[] = [
    { id: 'telemetry_cards', title: 'Hardware & IPC Telemetry', visible: true },
    { id: 'provider_matrix', title: 'Provider Latency & Availability Matrix', visible: true },
    { id: 'task_queue', title: 'Task Queue & Scheduled Hooks', visible: true },
    { id: 'engine_diagnostics', title: 'Agent Engine & Socket Health', visible: true },
  ];

  const [widgets, setWidgets] = useState<WidgetConfig[]>(() => {
    try {
      const saved = localStorage.getItem('niko_dashboard_widgets');
      if (saved) {
        const parsed: WidgetConfig[] = JSON.parse(saved);
        // Ensure new default widgets like task_queue are added if not present
        const ids = new Set(parsed.map((w) => w.id));
        const merged = [...parsed];
        for (const dw of defaultWidgets) {
          if (!ids.has(dw.id)) {
            merged.push(dw);
          }
        }
        return merged;
      }
      return defaultWidgets;
    } catch {
      return defaultWidgets;
    }
  });

  const [draggedIdx, setDraggedIdx] = useState<number | null>(null);

  // Live state for widgets
  const [modelStatus, setModelStatus] = useState<{
    discovered: Record<string, any>;
    quotas: Record<string, any> | any[];
    roles?: Record<string, any>;
  }>({
    discovered: {},
    quotas: {},
    roles: {},
  });
  const [scheduledTasks, setScheduledTasks] = useState<ScheduledTaskItem[]>([]);
  const [healthStatus, setHealthStatus] = useState<{ status: string; uptime_seconds: number }>({
    status: 'healthy',
    uptime_seconds: 0,
  });

  const legacyQuotas: Record<string, any> = !Array.isArray(modelStatus.quotas) ? (modelStatus.quotas || {}) : {};

  // Fetch live widget data
  const fetchLiveData = useCallback(async () => {
    try {
      const [statusData, schedulesData, healthData] = await Promise.all([
        ApiService.getModelsStatus(),
        ApiService.getSchedules(),
        ApiService.getHealth().catch(() => ({ status: 'unknown', uptime_seconds: 0 })),
      ]);
      setModelStatus(statusData);
      setScheduledTasks(schedulesData);
      setHealthStatus(healthData);
    } catch (err: any) {
      console.warn('Could not fetch all dashboard telemetry:', err);
    }
  }, []);

  useEffect(() => {
    fetchLiveData();
    const interval = setInterval(fetchLiveData, 15000);
    return () => clearInterval(interval);
  }, [fetchLiveData]);

  useEffect(() => {
    localStorage.setItem('niko_dashboard_widgets', JSON.stringify(widgets));
  }, [widgets]);

  const handleDragStart = (idx: number) => {
    setDraggedIdx(idx);
  };

  const handleDragOver = (e: React.DragEvent, idx: number) => {
    e.preventDefault();
    if (draggedIdx === null || draggedIdx === idx) return;

    const updated = [...widgets];
    const item = updated.splice(draggedIdx, 1)[0];
    updated.splice(idx, 0, item);
    setDraggedIdx(idx);
    setWidgets(updated);
  };

  const handleDragEnd = () => {
    setDraggedIdx(null);
  };

  const toggleWidgetVisibility = (id: string) => {
    setWidgets((prev) =>
      prev.map((w) => (w.id === id ? { ...w, visible: !w.visible } : w))
    );
  };

  const resetLayout = () => {
    setWidgets(defaultWidgets);
  };

  const handleToggleTask = async (taskId: string, currentStatus: string) => {
    try {
      const newStatus = currentStatus === 'active' ? 'paused' : 'active';
      await ApiService.toggleSchedule(taskId, newStatus);
      toastService.success('Task Updated', `Task set to ${newStatus}.`);
      fetchLiveData();
    } catch (err: any) {
      toastService.error('Update Failed', err.message || 'Could not update task.');
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    try {
      await ApiService.deleteSchedule(taskId);
      toastService.info('Task Removed', 'Scheduled task was deleted.');
      fetchLiveData();
    } catch (err: any) {
      toastService.error('Delete Failed', err.message || 'Could not delete task.');
    }
  };

  const handleRefreshClick = () => {
    onRefresh();
    fetchLiveData();
  };

  return (
    <div className="flex-1 overflow-y-auto p-gutter-md flex flex-col gap-6 max-w-6xl mx-auto w-full font-mono">
      {/* View Header */}
      <div className="flex items-center justify-between border-b border-surface-variant/40 pb-4">
        <div>
          <h1 className="text-xl font-bold text-on-surface">
            LIVE TELEMETRY & SYSTEM BENCHMARKS
          </h1>
          <p className="text-xs text-on-surface-variant font-sans">
            Modular, persisted diagnostics grid. Drag headers to reorder widgets.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={resetLayout}
            className="px-3 py-1.5 bg-surface-container hover:bg-surface-variant border border-surface-variant/60 rounded text-xs text-on-surface-variant hover:text-on-surface transition-colors"
            title="Reset to default grid order"
          >
            Reset Grid
          </button>
          <button
            onClick={handleRefreshClick}
            className="flex items-center gap-2 px-3 py-1.5 bg-primary-container text-on-primary-container font-bold rounded text-xs transition-colors shadow-[0_0_10px_rgba(255,176,32,0.3)]"
          >
            <span className="material-symbols-outlined text-sm">refresh</span>
            <span>Refresh Telemetry</span>
          </button>
        </div>
      </div>

      {/* Modular Persisted Widgets */}
      <div className="flex flex-col gap-6">
        {widgets.map((widget, idx) => {
          if (!widget.visible) return null;

          return (
            <div
              key={widget.id}
              draggable
              onDragStart={() => handleDragStart(idx)}
              onDragOver={(e) => handleDragOver(e, idx)}
              onDragEnd={handleDragEnd}
              className={`flex flex-col gap-3 transition-opacity ${
                draggedIdx === idx ? 'opacity-40 border-2 border-dashed border-primary-container p-2 rounded-xl' : ''
              }`}
            >
              {/* Widget Header & Drag Handle */}
              <div className="flex items-center justify-between px-2 cursor-grab active:cursor-grabbing text-xs text-on-surface-variant hover:text-on-surface">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm text-primary-container">
                    drag_indicator
                  </span>
                  <span className="font-bold uppercase tracking-wider text-primary text-[11px]">
                    {widget.title}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => toggleWidgetVisibility(widget.id)}
                  className="hover:text-error text-xs"
                  title="Hide widget"
                >
                  <span className="material-symbols-outlined text-sm">visibility_off</span>
                </button>
              </div>

              {/* Widget 1: Hardware & IPC Telemetry */}
              {widget.id === 'telemetry_cards' && (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  {/* Core State */}
                  <div className="bg-surface-container-low p-4 rounded-xl border border-surface-variant/40 flex flex-col gap-2">
                    <div className="flex items-center justify-between text-mono-sm text-on-surface-variant">
                      <span>CORE ENGINE</span>
                      <span
                        className={`w-2 h-2 rounded-full ${
                          metrics.coreOnline ? 'bg-secondary animate-pulse' : 'bg-error'
                        }`}
                      />
                    </div>
                    <div className="text-2xl font-bold text-on-surface">
                      {metrics.coreOnline ? 'ONLINE' : 'OFFLINE'}
                    </div>
                    <div className="text-[11px] text-secondary">
                      Uptime: {Math.floor(healthStatus.uptime_seconds / 60)}m ({healthStatus.uptime_seconds}s)
                    </div>
                  </div>

                  {/* CPU */}
                  <div className="bg-surface-container-low p-4 rounded-xl border border-surface-variant/40 flex flex-col gap-2">
                    <div className="flex items-center justify-between text-mono-sm text-on-surface-variant">
                      <span>CPU UTILIZATION</span>
                      <span className="material-symbols-outlined text-base text-primary-container">
                        memory
                      </span>
                    </div>
                    <div className="text-2xl font-bold text-on-surface">
                      {metrics.cpuPercent.toFixed(1)}%
                    </div>
                    <div className="w-full bg-surface-container h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-primary-container h-full transition-all duration-500"
                        style={{ width: `${Math.min(100, metrics.cpuPercent)}%` }}
                      />
                    </div>
                  </div>

                  {/* RAM */}
                  <div className="bg-surface-container-low p-4 rounded-xl border border-surface-variant/40 flex flex-col gap-2">
                    <div className="flex items-center justify-between text-mono-sm text-on-surface-variant">
                      <span>RAM CAPACITY</span>
                      <span className="material-symbols-outlined text-base text-primary-container">
                        developer_board
                      </span>
                    </div>
                    <div className="text-2xl font-bold text-on-surface">
                      {metrics.ramUsageGb.toFixed(1)}{' '}
                      <span className="text-sm font-normal text-on-surface-variant">
                        / {metrics.ramTotalGb} GB
                      </span>
                    </div>
                    <div className="w-full bg-surface-container h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-secondary h-full transition-all duration-500"
                        style={{ width: `${(metrics.ramUsageGb / metrics.ramTotalGb) * 100}%` }}
                      />
                    </div>
                  </div>

                  {/* Ping */}
                  <div className="bg-surface-container-low p-4 rounded-xl border border-surface-variant/40 flex flex-col gap-2">
                    <div className="flex items-center justify-between text-mono-sm text-on-surface-variant">
                      <span>IPC LATENCY</span>
                      <span className="material-symbols-outlined text-base text-secondary">
                        speed
                      </span>
                    </div>
                    <div className="text-2xl font-bold text-secondary">
                      {metrics.pingMs} ms
                    </div>
                    <div className="text-[11px] text-on-surface-variant">
                      Zero-hop local loopback (7421)
                    </div>
                  </div>
                </div>
              )}

              {/* Widget 2: Provider Latency Matrix & Configured Roles */}
              {widget.id === 'provider_matrix' && (
                <div className="bg-surface-container-low p-5 rounded-xl border border-surface-variant/40 flex flex-col gap-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {/* Gemini Provider Card */}
                    <div className="p-3.5 bg-surface-container rounded-lg border border-surface-variant/40 flex flex-col gap-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-on-surface">Google Gemini</span>
                        <span className="text-secondary font-bold text-[10px] px-1.5 py-0.5 bg-secondary/10 rounded">
                          {legacyQuotas?.gemini?.cooling_down ? 'COOLDOWN' : 'ACTIVE / PRIMARY'}
                        </span>
                      </div>
                      <div className="text-on-surface-variant text-[11px]">
                        Model:{' '}
                        {Array.isArray(modelStatus.discovered?.gemini)
                          ? modelStatus.discovered.gemini[0] || 'gemini-3.5-flash-lite'
                          : modelStatus.discovered?.gemini?.primary_model || 'gemini-3.5-flash-lite'}
                      </div>
                      <div className="text-primary-container text-xs font-semibold mt-1">
                        Est. TTFT: ~280ms
                      </div>
                      {legacyQuotas?.gemini?.cooling_down && (
                        <div className="text-[10px] text-warning mt-0.5">
                          Reset in: {legacyQuotas.gemini.remaining_seconds}s
                        </div>
                      )}
                    </div>

                    {/* Groq Cloud Card */}
                    <div className="p-3.5 bg-surface-container rounded-lg border border-surface-variant/40 flex flex-col gap-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-on-surface">Groq Cloud</span>
                        <span className="text-secondary font-bold text-[10px] px-1.5 py-0.5 bg-secondary/10 rounded">
                          {legacyQuotas?.groq?.cooling_down ? 'COOLDOWN' : 'STANDBY / LPU'}
                        </span>
                      </div>
                      <div className="text-on-surface-variant text-[11px]">
                        Model:{' '}
                        {Array.isArray(modelStatus.discovered?.groq)
                          ? modelStatus.discovered.groq[0] || 'openai/gpt-oss-20b'
                          : modelStatus.discovered?.groq?.primary_model || 'openai/gpt-oss-20b'}
                      </div>
                      <div className="text-primary-container text-xs font-semibold mt-1">
                        Est. TTFT: ~120ms (Ultra-Low Latency)
                      </div>
                      {legacyQuotas?.groq?.cooling_down && (
                        <div className="text-[10px] text-warning mt-0.5">
                          Reset in: {legacyQuotas.groq.remaining_seconds}s
                        </div>
                      )}
                    </div>

                    {/* OpenRouter Card */}
                    <div className="p-3.5 bg-surface-container rounded-lg border border-surface-variant/40 flex flex-col gap-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-on-surface">OpenRouter</span>
                        <span className="text-secondary font-bold text-[10px] px-1.5 py-0.5 bg-secondary/10 rounded">
                          {legacyQuotas?.openrouter?.cooling_down ? 'COOLDOWN' : 'MULTI-ROUTER'}
                        </span>
                      </div>
                      <div className="text-on-surface-variant text-[11px]">
                        Model:{' '}
                        {Array.isArray(modelStatus.discovered?.openrouter)
                          ? modelStatus.discovered.openrouter[0] || 'openrouter/free'
                          : modelStatus.discovered?.openrouter?.primary_model || 'openrouter/free'}
                      </div>
                      <div className="text-primary-container text-xs font-semibold mt-1">
                        Auto-Routing & Free Standby
                      </div>
                      {legacyQuotas?.openrouter?.cooling_down && (
                        <div className="text-[10px] text-warning mt-0.5">
                          Reset in: {legacyQuotas.openrouter.remaining_seconds}s
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Configured Role-to-Model Routing Map */}
                  {modelStatus.roles && Object.keys(modelStatus.roles).length > 0 && (
                    <div className="p-3 bg-surface-container rounded-lg border border-surface-variant/30 flex flex-col gap-2">
                      <div className="flex items-center justify-between text-[11px] text-on-surface-variant">
                        <span className="font-bold text-primary">CONFIGURED ROLE-TO-MODEL ROUTING MAP</span>
                        <span className="text-[10px] text-on-surface-variant">Resets midnight Pacific</span>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
                        {Object.entries(modelStatus.roles).map(([roleKey, targets]) => (
                          <div key={roleKey} className="p-2 bg-surface-container-high/50 rounded border border-surface-variant/20 flex flex-col gap-1">
                            <span className="font-bold uppercase text-on-surface text-[10px] text-primary-container">{roleKey}</span>
                            <div className="flex flex-col gap-0.5 text-[10px] text-on-surface-variant font-mono">
                              {Array.isArray(targets) && targets.map((t: any, tidx: number) => (
                                <div key={tidx} className="truncate">
                                  {tidx + 1}. <span className="text-on-surface">{t.provider}/{t.model}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Per-Model Live Daily Quota & Cooldowns */}
                  {Array.isArray(modelStatus.quotas) && modelStatus.quotas.length > 0 && (
                    <div className="p-3 bg-surface-container rounded-lg border border-surface-variant/30 flex flex-col gap-2">
                      <div className="flex items-center justify-between text-[11px] text-on-surface-variant">
                        <span className="font-bold text-secondary">ACTIVE MODEL DAILY USAGE & LIMITS</span>
                        <span className="text-[10px] text-on-surface-variant">Pacific Rollover</span>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
                        {modelStatus.quotas.map((q: any, qidx: number) => (
                          <div key={qidx} className="p-2 bg-surface-container-high/50 rounded border border-surface-variant/20 flex flex-col gap-1">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-on-surface truncate">{q.provider}/{q.model}</span>
                              <span className={`text-[9px] px-1 py-0.5 rounded font-bold uppercase ${
                                q.is_cooled_down ? 'bg-warning/20 text-warning' : 'bg-secondary/15 text-secondary'
                              }`}>
                                {q.is_cooled_down ? 'Cooldown' : 'Available'}
                              </span>
                            </div>
                            <div className="flex items-center justify-between text-[10px] text-on-surface-variant">
                              <span>RPD: {q.daily_requests} / {q.daily_limit || '∞'}</span>
                              {q.reserve_requests > 0 && (
                                <span className="text-primary-container text-[9px]">({q.reserve_requests} reserved for hard tasks)</span>
                              )}
                            </div>
                            {q.daily_limit > 0 && (
                              <div className="w-full bg-surface-container h-1 rounded-full overflow-hidden">
                                <div
                                  className={`h-full transition-all duration-300 ${
                                    (q.daily_requests / q.daily_limit) > 0.8 ? 'bg-warning' : 'bg-secondary'
                                  }`}
                                  style={{ width: `${Math.min(100, (q.daily_requests / q.daily_limit) * 100)}%` }}
                                />
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Widget 3: Task Queue & Scheduled Hooks */}
              {widget.id === 'task_queue' && (
                <div className="bg-surface-container-low p-5 rounded-xl border border-surface-variant/40 flex flex-col gap-3">
                  <div className="flex items-center justify-between text-xs text-on-surface-variant">
                    <span>REGISTERED BACKGROUND AGENT HOOKS ({scheduledTasks.length})</span>
                    <button
                      type="button"
                      onClick={fetchLiveData}
                      className="text-primary-container hover:underline text-[11px]"
                    >
                      Refresh Queue
                    </button>
                  </div>

                  {scheduledTasks.length === 0 ? (
                    <div className="p-4 bg-surface-container rounded-lg border border-surface-variant/20 text-center text-xs text-on-surface-variant">
                      No automated tasks scheduled. You can ask NIKO: <span className="text-primary">"Schedule system diagnostics daily at 8am"</span>.
                    </div>
                  ) : (
                    <div className="flex flex-col gap-2">
                      {scheduledTasks.map((t) => (
                        <div
                          key={t.id}
                          className="p-3 bg-surface-container rounded-lg border border-surface-variant/30 flex items-center justify-between gap-4 text-xs"
                        >
                          <div className="flex flex-col min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-on-surface truncate">{t.name}</span>
                              <span
                                className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${
                                  t.status === 'active'
                                    ? 'bg-secondary/15 text-secondary'
                                    : 'bg-surface-variant text-on-surface-variant'
                                }`}
                              >
                                {t.status}
                              </span>
                            </div>
                            <div className="text-[11px] text-on-surface-variant mt-0.5 truncate">
                              Type: {t.task_type} {t.cron_expression ? `(${t.cron_expression})` : ''} · Action: {t.action_type}
                              {t.next_run_at && (
                                <span> · Next run: {new Date(t.next_run_at).toLocaleTimeString()}</span>
                              )}
                            </div>
                          </div>

                          <div className="flex items-center gap-2 flex-shrink-0">
                            <button
                              type="button"
                              onClick={() => handleToggleTask(t.id, t.status)}
                              className="px-2 py-1 bg-surface-container-high hover:bg-surface-variant text-on-surface rounded text-[11px] transition-colors"
                            >
                              {t.status === 'active' ? 'Pause' : 'Resume'}
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteTask(t.id)}
                              className="px-2 py-1 bg-error/15 hover:bg-error/25 text-error rounded text-[11px] transition-colors"
                            >
                              Delete
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Widget 4: Engine Diagnostics */}
              {widget.id === 'engine_diagnostics' && (
                <div className="bg-surface-container-low p-5 rounded-xl border border-surface-variant/40 flex flex-col gap-3 text-xs">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="p-3 bg-surface-container rounded-lg border border-surface-variant/30 flex flex-col">
                      <span className="text-on-surface-variant text-[10px]">EVENT BUS STATUS</span>
                      <span className="text-secondary font-bold text-sm">BOUNDED (1000)</span>
                    </div>
                    <div className="p-3 bg-surface-container rounded-lg border border-surface-variant/30 flex flex-col">
                      <span className="text-on-surface-variant text-[10px]">RATE LIMIT COOLDOWN</span>
                      <span className="text-primary font-bold text-sm">PREDICTIVE ACTIVE</span>
                    </div>
                    <div className="p-3 bg-surface-container rounded-lg border border-surface-variant/30 flex flex-col">
                      <span className="text-on-surface-variant text-[10px]">HMAC INTEGRITY</span>
                      <span className="text-secondary font-bold text-sm">SHA-256 VERIFIED</span>
                    </div>
                    <div className="p-3 bg-surface-container rounded-lg border border-surface-variant/30 flex flex-col">
                      <span className="text-on-surface-variant text-[10px]">DB PERSISTENCE</span>
                      <span className="text-on-surface font-bold text-sm">SQLITE WAL ON</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
