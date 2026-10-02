import React, { useEffect, useState } from 'react';
import { ApiService } from '../services/api';
import { toastService } from '../services/toast';
import type { DisplayMode, ModelRoleMapping, ModelTarget } from '../types';

export const SettingsView: React.FC = () => {
  const [roleMappings, setRoleMappings] = useState<Record<string, ModelTarget[]>>({
    chat: [
      { provider: 'groq', model: 'llama-3.3-70b-versatile', temperature: 0.7, priority: 1 },
      { provider: 'gemini', model: 'gemini-2.0-flash', temperature: 0.7, priority: 2 },
      { provider: 'openrouter', model: 'qwen/qwen-2.5-coder-32b-instruct:free', temperature: 0.7, priority: 3 },
    ],
    fast: [
      { provider: 'groq', model: 'llama-3.1-8b-instant', temperature: 0.2, priority: 1 },
      { provider: 'gemini', model: 'gemini-2.0-flash', temperature: 0.2, priority: 2 },
    ],
    reasoning: [
      { provider: 'gemini', model: 'gemini-2.0-flash', reasoningEffort: 'high', priority: 1 },
      { provider: 'groq', model: 'llama-3.3-70b-versatile', priority: 2 },
      { provider: 'openrouter', model: 'qwen/qwen-2.5-coder-32b-instruct:free', priority: 3 },
    ],
  });

  const [petName, setPetName] = useState('NIKO');
  const [petPersona, setPetPersona] = useState('A friendly, embodied, and highly capable desktop AI companion.');
  const [displayMode, setDisplayMode] = useState<DisplayMode>(() => {
    return (localStorage.getItem('niko_display_mode') as DisplayMode) || 'pet-only';
  });

  const [isSaved, setIsSaved] = useState(false);
  const [activeRole, setActiveRole] = useState<'chat' | 'fast' | 'reasoning'>('chat');

  useEffect(() => {
    let active = true;
    ApiService.getModelRoles()
      .then((data) => {
        if (!active || !data || Object.keys(data).length === 0) return;
        const formatted: Record<string, ModelTarget[]> = {};
        for (const [role, val] of Object.entries(data)) {
          if (val && Array.isArray((val as ModelRoleMapping).targets)) {
            formatted[role] = (val as ModelRoleMapping).targets;
          }
        }
        if (Object.keys(formatted).length > 0) {
          setRoleMappings(formatted);
        }
      })
      .catch((err) => {
        console.warn('Could not load custom model roles from backend:', err);
      });

    ApiService.getPersona()
      .then((data) => {
        if (!active || !data) return;
        if (data.name) setPetName(data.name);
        if (data.persona) setPetPersona(data.persona);
      })
      .catch((err) => {
        console.warn('Could not load pet persona from backend:', err);
      });

    return () => {
      active = false;
    };
  }, []);

  const handleSave = async () => {
    try {
      await Promise.all([
        ApiService.updateModelRoles(roleMappings),
        ApiService.updatePersona(petName, petPersona),
      ]);
      localStorage.setItem('niko_display_mode', displayMode);
      setIsSaved(true);
      toastService.success('Configuration Saved', 'Settings updated successfully.');
      setTimeout(() => setIsSaved(false), 3000);
    } catch (err: any) {
      toastService.error('Save Failed', err.message || 'Could not save settings.');
    }
  };

  const currentTargets = roleMappings[activeRole] || [];

  return (
    <div className="flex-1 overflow-y-auto p-gutter-md flex flex-col gap-6 max-w-6xl mx-auto w-full">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-surface-variant/40 pb-4">
        <div>
          <h1 className="font-mono text-xl font-bold text-on-surface">
            MODEL ROLES & MULTI-PROVIDER FALLBACK
          </h1>
          <p className="font-mono text-xs text-on-surface-variant">
            Define sequential fallback priority orders, temperature profiles, and predictive cooldown policies.
          </p>
        </div>
        <button
          onClick={handleSave}
          className="flex items-center gap-2 px-5 py-2 bg-primary-container hover:bg-primary-fixed text-on-primary-container rounded font-mono text-xs font-bold shadow-[0_0_12px_rgba(255,176,32,0.3)] transition-all"
        >
          <span className="material-symbols-outlined text-sm">save</span>
          <span>{isSaved ? 'Saved to System' : 'Save Configuration'}</span>
        </button>
      </div>

      {/* Role Selector Tabs */}
      <div className="flex items-center gap-2 border-b border-surface-variant/40 pb-2">
        {(['chat', 'fast', 'reasoning'] as const).map((role) => (
          <button
            key={role}
            onClick={() => setActiveRole(role)}
            className={`px-4 py-2 font-mono text-xs font-semibold rounded-lg transition-colors ${
              activeRole === role
                ? 'bg-surface-container-high text-primary border border-primary-container/40'
                : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
            }`}
          >
            ROLE: {role.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Target Priority Chain */}
      <div className="flex flex-col gap-3">
        <h3 className="font-mono text-xs font-bold text-on-surface-variant uppercase tracking-wider">
          Sequential Fallback Sequence (Top to Bottom Priority)
        </h3>

        {currentTargets.map((target, idx) => (
          <div
            key={idx}
            className="p-4 bg-surface-container-low rounded-xl border border-surface-variant/60 flex items-center justify-between gap-4"
          >
            <div className="flex items-center gap-4">
              <span className="w-6 h-6 rounded-full bg-surface-container-high flex items-center justify-center font-mono text-xs font-bold text-primary">
                {idx + 1}
              </span>
              <div className="flex flex-col">
                <div className="flex items-center gap-2 font-mono text-sm">
                  <span className="font-bold text-on-surface">{target.provider.toUpperCase()}</span>
                  <span className="text-on-surface-variant">/</span>
                  <span className="text-primary font-semibold">{target.model}</span>
                </div>
                <div className="flex items-center gap-3 font-mono text-xs text-on-surface-variant">
                  {target.temperature !== undefined && <span>Temp: {target.temperature}</span>}
                  {target.reasoningEffort && <span>Reasoning: {target.reasoningEffort}</span>}
                  <span>Auto-cooldown: Predictive (3 consecutive 429s)</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded bg-secondary/10 text-secondary border border-secondary/30 font-mono text-[10px] font-bold">
                READY
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Pet AI Identity & Display Mode Section */}
      <div className="flex flex-col gap-4 border-t border-surface-variant/40 pt-6">
        <div>
          <h2 className="font-mono text-base font-bold text-on-surface">
            PET AI IDENTITY & INTERACTION MODE
          </h2>
          <p className="font-mono text-xs text-on-surface-variant">
            NIKO's desktop pet is the primary embodied AI interface. Configure its identity and display modes below.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Pet Name */}
          <div className="flex flex-col gap-1.5">
            <label className="font-mono text-xs font-semibold text-on-surface-variant">
              Pet Assistant Name
            </label>
            <input
              type="text"
              value={petName}
              onChange={(e) => setPetName(e.target.value)}
              placeholder="e.g. NIKO"
              className="px-3 py-2 bg-surface-container-low border border-surface-variant/60 rounded-lg font-mono text-xs text-on-surface outline-none focus:border-primary"
            />
          </div>

          {/* Display Mode */}
          <div className="flex flex-col gap-1.5">
            <label className="font-mono text-xs font-semibold text-on-surface-variant">
              Desktop Display Mode
            </label>
            <select
              value={displayMode}
              onChange={(e) => setDisplayMode(e.target.value as DisplayMode)}
              className="px-3 py-2 bg-surface-container-low border border-surface-variant/60 rounded-lg font-mono text-xs text-on-surface outline-none focus:border-primary"
            >
              <option value="pet-only">Pet Only (Default: Embodied companion with click-to-type & speech bubble)</option>
              <option value="pet-overlay">Pet + Overlay (Embodied companion + hovering card HUD)</option>
              <option value="overlay-only">Overlay Only (Hovering card HUD without character)</option>
            </select>
          </div>
        </div>

        {/* Pet Persona */}
        <div className="flex flex-col gap-1.5">
          <label className="font-mono text-xs font-semibold text-on-surface-variant">
            Pet Persona & System Instructions
          </label>
          <textarea
            rows={3}
            value={petPersona}
            onChange={(e) => setPetPersona(e.target.value)}
            placeholder="Describe the pet's persona, tone, and traits..."
            className="px-3 py-2 bg-surface-container-low border border-surface-variant/60 rounded-lg font-mono text-xs text-on-surface outline-none focus:border-primary resize-y"
          />
        </div>
      </div>
    </div>
  );
};
