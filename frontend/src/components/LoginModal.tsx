import React, { useState } from 'react';
import { ApiService } from '../services/api';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSuccess: () => void;
  currentUser?: { username: string; role: string } | null;
  onLogout?: () => void;
}

export const LoginModal: React.FC<LoginModalProps> = ({
  isOpen,
  onClose,
  onLoginSuccess,
  currentUser,
  onLogout,
}) => {
  const [mode, setMode] = useState<'login' | 'setup'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [setupToken, setSetupToken] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage('');
    setIsLoading(true);

    try {
      if (mode === 'login') {
        await ApiService.login(username, password);
      } else {
        await ApiService.setup(username, password, setupToken);
      }
      setIsLoading(false);
      onLoginSuccess();
      onClose();
    } catch (err: any) {
      setIsLoading(false);
      setErrorMessage(err.message || 'Authentication failed.');
    }
  };

  const handleLogout = async () => {
    try {
      await ApiService.logout();
    } catch {
      // ignore
    }
    if (onLogout) onLogout();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-md bg-surface-container-low border border-primary-container/40 rounded-xl shadow-2xl overflow-hidden p-6 flex flex-col gap-4 font-mono animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary-container/20 border border-primary-container/40 flex items-center justify-center text-primary font-bold">
              <span className="material-symbols-outlined">lock</span>
            </div>
            <div>
              <h3 className="text-base font-bold text-on-surface">
                {currentUser ? 'OPERATOR SESSION' : mode === 'login' ? 'OPERATOR LOGIN' : 'FIRST-BOOT SETUP'}
              </h3>
              <p className="text-xs text-on-surface-variant">
                {currentUser ? `Active Operator: ${currentUser.username} (${currentUser.role})` : 'Secured with Argon2 & httpOnly Session'}
              </p>
            </div>
          </div>

          {!currentUser && (
            <button
              type="button"
              onClick={() => {
                setMode((prev) => (prev === 'login' ? 'setup' : 'login'));
                setErrorMessage('');
              }}
              className="text-[11px] text-primary hover:underline"
            >
              {mode === 'login' ? 'First Boot Setup?' : 'Existing Login?'}
            </button>
          )}
        </div>

        {currentUser ? (
          <div className="flex flex-col gap-4 pt-2">
            <div className="p-3 bg-surface-container rounded border border-surface-variant/40 text-xs">
              <div className="flex justify-between py-1 border-b border-surface-variant/30">
                <span className="text-on-surface-variant">Operator Username:</span>
                <span className="text-primary font-bold">{currentUser.username}</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-on-surface-variant">Role Tier:</span>
                <span className="text-secondary font-bold uppercase">{currentUser.role}</span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 bg-surface-container hover:bg-surface-variant text-on-surface-variant text-xs rounded transition-colors"
              >
                Close
              </button>
              <button
                type="button"
                onClick={handleLogout}
                className="px-5 py-2 bg-error-container/20 hover:bg-error-container/40 text-error border border-error/40 text-xs font-bold rounded transition-colors"
              >
                Logout Session
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-3 pt-2">
            {errorMessage && (
              <div className="p-2.5 bg-error-container/20 border border-error/40 rounded text-xs text-error font-medium">
                {errorMessage}
              </div>
            )}

            {mode === 'setup' && (
              <div className="flex flex-col gap-1">
                <label className="text-xs text-on-surface-variant uppercase font-semibold">
                  Setup Token (From Server Logs / .env)
                </label>
                <input
                  type="password"
                  value={setupToken}
                  onChange={(e) => setSetupToken(e.target.value)}
                  placeholder="32-byte secret token"
                  required
                  className="w-full bg-surface-container-lowest px-3 py-2 rounded border border-surface-variant/60 text-xs text-on-surface outline-none focus:border-primary-container"
                />
              </div>
            )}

            <div className="flex flex-col gap-1">
              <label className="text-xs text-on-surface-variant uppercase font-semibold">
                Operator Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. niko_admin"
                required
                className="w-full bg-surface-container-lowest px-3 py-2 rounded border border-surface-variant/60 text-xs text-on-surface outline-none focus:border-primary-container"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-xs text-on-surface-variant uppercase font-semibold">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Minimum 8 characters"
                required
                className="w-full bg-surface-container-lowest px-3 py-2 rounded border border-surface-variant/60 text-xs text-on-surface outline-none focus:border-primary-container"
              />
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-surface-variant/40">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 bg-surface-container hover:bg-surface-variant text-on-surface-variant text-xs rounded transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isLoading}
                className="px-5 py-2 bg-primary-container hover:bg-primary-fixed text-on-primary-container text-xs font-bold rounded shadow-[0_0_12px_rgba(255,176,32,0.3)] transition-all disabled:opacity-50"
              >
                {isLoading ? 'Processing...' : mode === 'login' ? 'Authenticate' : 'Initialize Owner'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
