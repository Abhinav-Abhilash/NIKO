import React from 'react';

interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const KeyboardShortcutsModal: React.FC<KeyboardShortcutsModalProps> = ({
  isOpen,
  onClose,
}) => {
  if (!isOpen) return null;

  const shortcutGroups = [
    {
      category: 'Navigation & View Switching',
      shortcuts: [
        { key: '⌘ 1 / Ctrl 1', desc: 'Switch to Autonomous Cockpit Chat' },
        { key: '⌘ 2 / Ctrl 2', desc: 'Switch to Live Telemetry Dashboard' },
        { key: '⌘ 3 / Ctrl 3', desc: 'Switch to Usage & Telemetry' },
        { key: '⌘ 4 / Ctrl 4', desc: 'Switch to Agent Skills Sandbox' },
        { key: '⌘ 5 / Ctrl 5', desc: 'Switch to Cryptographic Audit Logs' },
        { key: '⌘ 6 / Ctrl 6', desc: 'Switch to Model Roles Configuration' },
      ],
    },
    {
      category: 'Command & Control',
      shortcuts: [
        { key: '⌘ K / Ctrl K', desc: 'Open Global Command & Action Palette' },
        { key: '? / Shift /', desc: 'Toggle Keyboard Shortcuts Help Overlay' },
        { key: 'Esc', desc: 'Close any active modal or palette' },
      ],
    },
    {
      category: 'Human-in-the-Loop Approvals',
      shortcuts: [
        { key: 'Y / Enter', desc: 'Approve execution of requested skill' },
        { key: 'N / Esc', desc: 'Deny execution of requested skill' },
      ],
    },
    {
      category: 'Chat & Prompting',
      shortcuts: [
        { key: 'Enter', desc: 'Transmit prompt to LLM streaming engine' },
        { key: 'Shift Enter', desc: 'Insert new line in chat input box' },
      ],
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-xl bg-surface-container-low border border-primary-container/40 rounded-xl shadow-2xl overflow-hidden p-6 flex flex-col gap-5 font-mono animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between border-b border-surface-variant/40 pb-3">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-primary-container text-xl">
              keyboard
            </span>
            <h3 className="text-base font-bold text-on-surface">KEYBOARD SHORTCUTS REFERENCE</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-on-surface-variant hover:text-on-surface"
          >
            <span className="material-symbols-outlined text-base">close</span>
          </button>
        </div>

        <div className="flex flex-col gap-4 max-h-[60vh] overflow-y-auto pr-1">
          {shortcutGroups.map((group, idx) => (
            <div key={idx} className="flex flex-col gap-2">
              <h4 className="text-[11px] uppercase font-bold text-primary tracking-wider">
                {group.category}
              </h4>
              <div className="grid grid-cols-1 gap-1.5 bg-surface-container p-3 rounded-lg border border-surface-variant/30">
                {group.shortcuts.map((s, sIdx) => (
                  <div key={sIdx} className="flex items-center justify-between py-1 text-xs">
                    <span className="text-on-surface-variant text-[11px]">{s.desc}</span>
                    <kbd className="px-2 py-0.5 bg-surface-container-high border border-surface-variant rounded text-[10px] text-primary font-bold">
                      {s.key}
                    </kbd>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="flex justify-end pt-2 border-t border-surface-variant/40">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2 bg-primary-container hover:bg-primary-fixed text-on-primary-container text-xs font-bold rounded shadow transition-colors"
          >
            Close Reference
          </button>
        </div>
      </div>
    </div>
  );
};
