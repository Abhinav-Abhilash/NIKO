import React from 'react';

export type ActiveTab = 'chat' | 'dashboard' | 'usage' | 'skills' | 'admin' | 'settings';

interface SidebarProps {
  activeTab: ActiveTab;
  setActiveTab: (tab: ActiveTab) => void;
  isOnline: boolean;
  activeModelName?: string;
  onOpenSettings?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  isOnline,
  activeModelName = 'groq/llama-3.3-70b',
}) => {
  const navItems: { id: ActiveTab; label: string; icon: string; shortcut: string }[] = [
    { id: 'chat', label: 'Cockpit Chat', icon: 'terminal', shortcut: '⌘1' },
    { id: 'dashboard', label: 'Live Telemetry', icon: 'grid_view', shortcut: '⌘2' },
    { id: 'usage', label: 'Usage & Quotas', icon: 'monitoring', shortcut: '⌘3' },
    { id: 'skills', label: 'Agent Skills', icon: 'extension', shortcut: '⌘4' },
    { id: 'admin', label: 'Audit & Admin', icon: 'admin_panel_settings', shortcut: '⌘5' },
    { id: 'settings', label: 'Model Roles', icon: 'tune', shortcut: '⌘6' },
  ];

  return (
    <aside className="fixed left-0 top-0 h-full w-16 bg-surface-container-lowest z-50 flex flex-col items-center justify-between border-r border-surface-variant/40 py-space-sm select-none">
      {/* Top Logo & Navigation */}
      <div className="flex flex-col items-center w-full gap-space-md">
        {/* Core Logo */}
        <div
          onClick={() => setActiveTab('chat')}
          className="relative flex items-center justify-center w-10 h-10 group cursor-pointer"
          title="NIKO Core"
        >
          <div className="w-8 h-8 rounded-lg bg-primary-container/20 border border-primary-container/40 flex items-center justify-center text-primary font-bold text-lg shadow-[0_0_12px_rgba(255,176,32,0.3)]">
            N
          </div>
          <span className="absolute left-14 ml-space-xs px-space-sm py-space-xs bg-surface-container-highest text-on-surface text-mono-sm font-mono rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50 shadow-lg border border-surface-variant/60">
            Niko Core Cockpit
          </span>
        </div>

        {/* Navigation Items */}
        <nav className="flex flex-col items-center w-full gap-space-xs">
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`relative flex items-center justify-center w-12 h-10 transition-colors rounded group ${
                  isActive
                    ? 'bg-surface-container-high text-primary-container border-l-2 border-primary-container'
                    : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
                }`}
                title={item.label}
              >
                <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
                <span className="absolute left-14 ml-space-xs px-space-sm py-space-xs bg-surface-container-highest text-on-surface text-mono-sm font-mono rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50 shadow-lg border border-surface-variant/60">
                  {item.label} ({item.shortcut})
                </span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Status & Hardware Indicators */}
      <div className="flex flex-col items-center w-full gap-space-sm border-t border-surface-variant/40 pt-space-sm">
        {/* Model Indicator */}
        <div
          onClick={() => setActiveTab('settings')}
          className="relative flex items-center justify-center w-10 h-10 group cursor-pointer"
        >
          <span className="material-symbols-outlined text-[18px] text-on-surface-variant group-hover:text-primary-container transition-colors">
            dns
          </span>
          <span className="absolute left-14 ml-space-xs px-space-sm py-space-xs bg-surface-container-highest text-on-surface text-mono-sm font-mono rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50 shadow-lg border border-surface-variant/60">
            {activeModelName}
          </span>
        </div>

        {/* Local Online Indicator */}
        <div className="relative flex items-center justify-center w-8 h-8 group cursor-pointer">
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              isOnline
                ? 'bg-secondary shadow-[0_0_8px_rgba(74,225,118,0.7)]'
                : 'bg-error shadow-[0_0_8px_rgba(255,180,171,0.7)]'
            }`}
          />
          <span
            className={`absolute left-14 ml-space-xs px-space-sm py-space-xs bg-surface-container-highest text-mono-sm font-mono rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50 shadow-lg border border-surface-variant/60 ${
              isOnline ? 'text-secondary' : 'text-error'
            }`}
          >
            {isOnline ? 'LOCAL :7421 ONLINE' : 'DISCONNECTED'}
          </span>
        </div>

        {/* IPC Hub Icon */}
        <div className="w-7 h-7 rounded-full bg-surface-container-high border border-surface-variant flex items-center justify-center">
          <span className="material-symbols-outlined text-primary-container text-[14px]">hub</span>
        </div>
      </div>
    </aside>
  );
};
