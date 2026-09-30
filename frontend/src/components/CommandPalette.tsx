import React, { useEffect, useState } from 'react';
import type { ActiveTab } from './Sidebar';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectTab: (tab: ActiveTab) => void;
  onRunPrompt: (prompt: string) => void;
}

interface ActionItem {
  id: string;
  category: 'Navigate' | 'System Action' | 'Diagnostics' | 'Model Switch';
  label: string;
  sublabel?: string;
  icon: string;
  shortcut?: string;
  action: () => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onSelectTab,
  onRunPrompt,
}) => {
  const [search, setSearch] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);

  const actions: ActionItem[] = [
    {
      id: 'nav-chat',
      category: 'Navigate',
      label: 'Open Autonomous Cockpit Chat',
      sublabel: 'Main real-time streaming console',
      icon: 'terminal',
      shortcut: '⌘1',
      action: () => {
        onSelectTab('chat');
        onClose();
      },
    },
    {
      id: 'nav-dashboard',
      category: 'Navigate',
      label: 'Open Telemetry Dashboard',
      sublabel: 'Live system metrics & benchmarks',
      icon: 'grid_view',
      shortcut: '⌘2',
      action: () => {
        onSelectTab('dashboard');
        onClose();
      },
    },
    {
      id: 'nav-skills',
      category: 'Navigate',
      label: 'Manage Agent Skills',
      sublabel: 'Toggle skill access & sandbox parameters',
      icon: 'extension',
      shortcut: '⌘4',
      action: () => {
        onSelectTab('skills');
        onClose();
      },
    },
    {
      id: 'nav-settings',
      category: 'Navigate',
      label: 'Configure Model Roles & Fallbacks',
      sublabel: 'Set priority targets for Chat, Fast, Reasoning',
      icon: 'tune',
      shortcut: '⌘6',
      action: () => {
        onSelectTab('settings');
        onClose();
      },
    },
    {
      id: 'nav-admin',
      category: 'Navigate',
      label: 'View Security Audit Logs',
      sublabel: 'Cryptographically verified audit trail',
      icon: 'admin_panel_settings',
      shortcut: '⌘5',
      action: () => {
        onSelectTab('admin');
        onClose();
      },
    },
    {
      id: 'diag-health',
      category: 'Diagnostics',
      label: 'Run System Health Check',
      sublabel: 'Validate local SQLite, Ollama, and Cloud providers',
      icon: 'health_and_safety',
      action: () => {
        onRunPrompt('Run complete system diagnostics on database and active LLM providers.');
        onClose();
      },
    },
    {
      id: 'action-skills-list',
      category: 'System Action',
      label: 'List Available Built-in Skills',
      sublabel: 'Inspect loaded skills in context',
      icon: 'apps',
      action: () => {
        onRunPrompt('What skills are currently registered and what are their permissions?');
        onClose();
      },
    },
  ];

  const filteredActions = actions.filter((a) =>
    a.label.toLowerCase().includes(search.toLowerCase()) ||
    (a.sublabel && a.sublabel.toLowerCase().includes(search.toLowerCase())) ||
    a.category.toLowerCase().includes(search.toLowerCase())
  );

  const [prevSearch, setPrevSearch] = useState(search);

  if (search !== prevSearch) {
    setPrevSearch(search);
    setSelectedIndex(0);
  }

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % (filteredActions.length || 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + (filteredActions.length || 1)) % (filteredActions.length || 1));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (filteredActions[selectedIndex]) {
          filteredActions[selectedIndex].action();
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, selectedIndex, filteredActions, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 bg-black/75 backdrop-blur-sm p-4">
      <div className="w-full max-w-xl bg-surface-container-low border border-surface-variant/80 rounded-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150 flex flex-col">
        {/* Search Input Bar */}
        <div className="flex items-center px-4 py-3 bg-surface-container border-b border-surface-variant/40 gap-3">
          <span className="material-symbols-outlined text-primary-container text-xl">
            search
          </span>
          <input
            type="text"
            placeholder="Type a command, prompt, or jump to view..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoFocus
            className="flex-1 bg-transparent border-none outline-none font-mono text-sm text-on-surface placeholder:text-on-surface-variant"
          />
          <kbd className="px-1.5 py-0.5 bg-surface-container-high border border-surface-variant text-[10px] font-mono text-on-surface-variant rounded">
            ESC
          </kbd>
        </div>

        {/* Action List */}
        <div className="max-h-80 overflow-y-auto p-2 flex flex-col gap-1">
          {filteredActions.length === 0 ? (
            <div className="py-8 text-center font-mono text-sm text-on-surface-variant">
              No matching actions found.
            </div>
          ) : (
            filteredActions.map((action, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <button
                  key={action.id}
                  onClick={() => action.action()}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-left transition-colors font-mono ${
                    isSelected
                      ? 'bg-surface-container-high text-primary border border-primary-container/40'
                      : 'text-on-surface hover:bg-surface-container'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span className={`material-symbols-outlined text-[20px] ${isSelected ? 'text-primary-container' : 'text-on-surface-variant'}`}>
                      {action.icon}
                    </span>
                    <div className="flex flex-col min-w-0 truncate">
                      <span className="text-sm font-semibold truncate">{action.label}</span>
                      {action.sublabel && (
                        <span className="text-xs text-on-surface-variant truncate">
                          {action.sublabel}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-container text-on-surface-variant uppercase">
                      {action.category}
                    </span>
                    {action.shortcut && (
                      <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-surface-container-highest text-on-surface-variant font-mono">
                        {action.shortcut}
                      </kbd>
                    )}
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* Footer Hint */}
        <div className="flex items-center justify-between px-4 py-2 bg-surface-container text-xs font-mono text-on-surface-variant border-t border-surface-variant/40">
          <span>Navigate with ↑ / ↓</span>
          <span>Execute with ↵ Enter</span>
        </div>
      </div>
    </div>
  );
};
