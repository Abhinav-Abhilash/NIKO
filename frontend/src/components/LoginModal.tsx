import React, { useState } from 'react';
import { ApiService } from '../services/api';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSuccess: () => void;
}

export const LoginModal: React.FC<LoginModalProps> = ({
  isOpen,
  onClose,
  onLoginSuccess,
}) => {
  const [tokenInput, setTokenInput] = useState(ApiService.getToken() || '');
  const [statusMsg, setStatusMsg] = useState('');

  if (!isOpen) return null;

  const handleSave = () => {
    if (!tokenInput.trim()) {
      ApiService.setToken(null);
      setStatusMsg('Token cleared. Using anonymous/local session.');
    } else {
      ApiService.setToken(tokenInput.trim());
      setStatusMsg('Operator JWT Token saved to local secure session.');
    }
    setTimeout(() => {
      onLoginSuccess();
      onClose();
    }, 600);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-md bg-surface-container-low border border-primary-container/40 rounded-xl shadow-2xl overflow-hidden p-6 flex flex-col gap-4 font-mono animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary-container/20 border border-primary-container/40 flex items-center justify-center text-primary font-bold">
            <span className="material-symbols-outlined">key</span>
          </div>
          <div>
            <h3 className="text-base font-bold text-on-surface">OPERATOR AUTHENTICATION</h3>
            <p className="text-xs text-on-surface-variant">Provide Bearer JWT Token for protected endpoints</p>
          </div>
        </div>

        {/* Token Input */}
        <div className="flex flex-col gap-1.5">
          <label className="text-xs text-on-surface-variant uppercase tracking-wider font-semibold">
            JWT Access Token
          </label>
          <textarea
            rows={3}
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
            placeholder="Paste eyJhbGciOiJIUzI1NiIs..."
            className="w-full bg-surface-container-lowest p-3 rounded border border-surface-variant/60 text-xs text-on-surface outline-none focus:border-primary-container focus:ring-1 focus:ring-primary-container resize-none"
          />
        </div>

        {statusMsg && (
          <div className="text-xs text-primary font-semibold p-2 bg-primary-container/10 border border-primary-container/30 rounded">
            {statusMsg}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between pt-2 border-t border-surface-variant/40">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-surface-container hover:bg-surface-variant text-on-surface-variant hover:text-on-surface text-xs rounded transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="px-5 py-2 bg-primary-container hover:bg-primary-fixed text-on-primary-container text-xs font-bold rounded shadow-[0_0_12px_rgba(255,176,32,0.3)] transition-all"
          >
            Save & Connect
          </button>
        </div>
      </div>
    </div>
  );
};
