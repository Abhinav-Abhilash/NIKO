import React, { useEffect, useState } from 'react';
import { ApiService } from '../services/api';
import type { ModelRoleMapping, ModelTarget } from '../types';

export const SettingsView: React.FC = () => {
  const [roleMappings, setRoleMappings] = useState<Record<string, ModelTarget[]>>({
    chat: [
      { provider: 'groq', model: 'llama-3.3-70b-versatile', temperature: 0.7, priority: 1 },
      { provider: 'gemini', model: 'gemini-2.0-flash', temperature: 0.7, priority: 2 },
      { provider: 'ollama', model: 'qwen2.5:7b-instruct', temperature: 0.7, priority: 3 },
    ],
    fast: [
      { provider: 'groq', model: 'llama-3.1-8b-instant', temperature: 0.2, priority: 1 },
      { provider: 'gemini', model: 'gemini-2.0-flash', temperature: 0.2, priority: 2 },
    ],
    reasoning: [
      { provider: 'gemini', model: 'gemini-2.0-flash', reasoningEffort: 'high', priority: 1 },
      { provider: 'groq', model: 'llama-3.3-70b-versatile', priority: 2 },
    ],
  });

  const [isSaved, setIsSaved] = useState(false);
  const [activeRole, setActiveRole] = useState<'chat' | 'fast' | 'reasoning'>('chat');

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const data = await ApiService.getModelRoles();
      if (data && Object.keys(data).length > 0) {
        const formatted: Record<string, ModelTarget[]> = {};
        for (const [role, val] of Object.entries(data)) {
          if (val && Array.isArray((val as ModelRoleMapping).targets)) {
            formatted[role] = (val as ModelRoleMapping).targets;
          }
        }
        if (Object.keys(formatted).length > 0) {
          setRoleMappings(formatted);
        }
      }
    } catch (err) {
      console.warn('Could not load custom model roles from backend:', err);
    }
  };

  const handleSave = async () => {
    try {
      await ApiService.updateModelRoles(roleMappings);
      setIsSaved(true);
      setTimeout(() => setIsSaved(false), 3000);
    } catch (err) {
      console.error('Error saving model roles:', err);
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
    </div>
  );
};
