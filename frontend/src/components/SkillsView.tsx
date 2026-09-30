import React, { useEffect, useState } from 'react';
import { ApiService } from '../services/api';
import { toastService } from '../services/toast';
import type { SkillItem } from '../types';

// Default fallback skills if backend is fresh
const defaultSkills: SkillItem[] = [
  {
    id: 'datetime',
    name: 'datetime',
    description: 'Fetch current system time, UTC timestamps, and localized clock values.',
    category: 'System',
    enabled: true,
    riskLevel: 'low',
    requiresApproval: false,
    timeoutSeconds: 5,
  },
  {
    id: 'run_subprocess',
    name: 'run_subprocess',
    description: 'Execute shell commands and local CLI scripts with timeout enforcement.',
    category: 'Execution',
    enabled: true,
    riskLevel: 'high',
    requiresApproval: true,
    timeoutSeconds: 30,
  },
  {
    id: 'read_file',
    name: 'read_file',
    description: 'Read contents from local workspace files with strict boundary controls.',
    category: 'Filesystem',
    enabled: true,
    riskLevel: 'low',
    requiresApproval: false,
    timeoutSeconds: 10,
  },
  {
    id: 'write_file',
    name: 'write_file',
    description: 'Create or update local workspace files with undo window support.',
    category: 'Filesystem',
    enabled: true,
    riskLevel: 'medium',
    requiresApproval: true,
    timeoutSeconds: 15,
  },
];

export const SkillsView: React.FC = () => {
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadSkills = React.useCallback(async () => {
    try {
      const data = await ApiService.getSkills();
      if (data && data.length > 0) {
        setSkills(data);
      } else {
        setSkills(defaultSkills);
      }
    } catch {
      setSkills(defaultSkills);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    ApiService.getSkills()
      .then((data) => {
        if (!active) return;
        if (data && data.length > 0) {
          setSkills(data);
        } else {
          setSkills(defaultSkills);
        }
      })
      .catch(() => {
        if (!active) return;
        setSkills(defaultSkills);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const handleToggle = async (skillId: string, currentEnabled: boolean) => {
    const nextState = !currentEnabled;
    const skillName = skills.find((s) => s.id === skillId)?.name || skillId;

    // Optimistic UI state update
    setSkills((prev) =>
      prev.map((s) => (s.id === skillId ? { ...s, enabled: nextState } : s))
    );

    toastService.undo(
      `Skill ${nextState ? 'Enabled' : 'Disabled'}`,
      `${skillName} is now ${nextState ? 'active in tool calling' : 'disabled'}. Click to revert.`,
      () => {
        // Undo handler
        setSkills((prev) =>
          prev.map((s) => (s.id === skillId ? { ...s, enabled: currentEnabled } : s))
        );
        ApiService.toggleSkill(skillId, currentEnabled).catch(() => {});
      }
    );

    try {
      await ApiService.toggleSkill(skillId, nextState);
    } catch (err: any) {
      // Revert on failure
      setSkills((prev) =>
        prev.map((s) => (s.id === skillId ? { ...s, enabled: currentEnabled } : s))
      );
      toastService.error('Update Failed', err.message || 'Could not update skill.');
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-gutter-md flex flex-col gap-6 max-w-6xl mx-auto w-full">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-surface-variant/40 pb-4">
        <div>
          <h1 className="font-mono text-xl font-bold text-on-surface">
            AGENT SKILLS & EXECUTION SANDBOX
          </h1>
          <p className="font-mono text-xs text-on-surface-variant">
            Manage autonomous tool capabilities, HITL approval policies, and timeout limits.
          </p>
        </div>
        <button
          onClick={loadSkills}
          disabled={isLoading}
          className="flex items-center gap-2 px-3 py-1.5 bg-surface-container hover:bg-surface-variant border border-surface-variant/60 rounded text-xs font-mono text-on-surface transition-colors disabled:opacity-50"
        >
          <span className={`material-symbols-outlined text-sm ${isLoading ? 'animate-spin' : ''}`}>
            refresh
          </span>
          <span>{isLoading ? 'Loading Skills...' : 'Refresh Skills'}</span>
        </button>
      </div>

      {/* Skills Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {skills.map((skill) => (
          <div
            key={skill.id}
            className={`p-4 rounded-xl border transition-all flex flex-col justify-between gap-4 ${
              skill.enabled
                ? 'bg-surface-container-low border-surface-variant/60'
                : 'bg-surface-container-lowest/60 border-surface-variant/30 opacity-70'
            }`}
          >
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary-container text-xl">
                    extension
                  </span>
                  <span className="font-mono text-sm font-bold text-primary">
                    {skill.name}
                  </span>
                </div>
                {/* Toggle Switch */}
                <button
                  type="button"
                  onClick={() => handleToggle(skill.id, skill.enabled)}
                  className={`w-11 h-6 flex items-center rounded-full p-1 transition-colors ${
                    skill.enabled ? 'bg-primary-container' : 'bg-surface-container-high'
                  }`}
                >
                  <div
                    className={`bg-on-primary-container w-4 h-4 rounded-full shadow-md transform transition-transform ${
                      skill.enabled ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>

              <p className="font-sans text-xs text-on-surface-variant leading-relaxed">
                {skill.description}
              </p>
            </div>

            {/* Badges & Telemetry */}
            <div className="flex items-center justify-between pt-3 border-t border-surface-variant/40 font-mono text-xs">
              <div className="flex items-center gap-2">
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                    skill.riskLevel === 'high'
                      ? 'bg-error-container/20 text-error border border-error/30'
                      : skill.riskLevel === 'medium'
                      ? 'bg-primary-container/20 text-primary-container border border-primary-container/30'
                      : 'bg-secondary/10 text-secondary border border-secondary/30'
                  }`}
                >
                  {skill.riskLevel} RISK
                </span>
                {skill.requiresApproval && (
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-surface-container text-on-surface-variant border border-surface-variant/60">
                    HITL APPROVAL
                  </span>
                )}
              </div>
              <span className="text-on-surface-variant text-[11px]">
                Timeout: {skill.timeoutSeconds}s
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
