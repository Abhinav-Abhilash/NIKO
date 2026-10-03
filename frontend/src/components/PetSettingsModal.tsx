import React from 'react';
import {
  savePetSettings,
  type PetSettings,
} from '../services/petSettings';

export interface PetSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: PetSettings;
  onUpdateSettings: (newSettings: PetSettings) => void;
  onResetPosition?: () => void;
  onTriggerSleepNow?: () => void;
  manualStateOverride: string | null;
  onSetManualState: (state: string | null) => void;
}

const ALL_STATES = [
  'idle',
  'walking',
  'running',
  'sitting',
  'sleeping',
  'happy',
  'surprised',
  'curious',
  'bored',
  'thinking',
  'speaking',
  'acting',
  'waiting_approval',
  'error',
  'cooldown',
  'success',
  'mouse_interaction',
  'playing',
];

export const PetSettingsModal: React.FC<PetSettingsModalProps> = ({
  isOpen,
  onClose,
  settings,
  onUpdateSettings,
  onResetPosition,
  onTriggerSleepNow,
  manualStateOverride,
  onSetManualState,
}) => {
  if (!isOpen) return null;

  return (
    <div
      data-testid="pet-settings-overlay"
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.65)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        zIndex: 999999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'Inter, system-ui, sans-serif',
      }}
    >
      <div
        data-testid="pet-settings-modal"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '310px',
          maxHeight: '92vh',
          overflowY: 'auto',
          backgroundColor: '#0F172A',
          border: '1.5px solid rgba(56, 189, 248, 0.4)',
          borderRadius: '18px',
          padding: '16px',
          boxShadow: '0 20px 45px rgba(0, 0, 0, 0.8), 0 0 24px rgba(56, 189, 248, 0.2)',
          color: '#F8FAFC',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid rgba(255, 255, 255, 0.1)', paddingBottom: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '18px' }}>⚙️</span>
            <span style={{ fontWeight: 700, fontSize: '13px', letterSpacing: '0.04em', color: '#38BDF8' }}>
              NIKO Pet Settings
            </span>
          </div>
          <button
            type="button"
            data-testid="pet-settings-close-btn"
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94A3B8',
              fontSize: '18px',
              cursor: 'pointer',
              padding: '2px 6px',
            }}
          >
            ✕
          </button>
        </div>

        {/* Size Slider */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', fontWeight: 600 }}>
            <span>Pet Size</span>
            <span style={{ color: '#38BDF8', fontFamily: 'monospace' }}>
              {settings.sizeScale.toFixed(2)}x
            </span>
          </div>
          <input
            data-testid="pet-size-slider"
            type="range"
            min="0.5"
            max="1.5"
            step="0.05"
            value={settings.sizeScale}
            onChange={(e) => {
              const val = parseFloat(e.target.value);
              const next = { ...settings, sizeScale: val };
              onUpdateSettings(next);
              savePetSettings(next);
            }}
            style={{ width: '100%', accentColor: '#38BDF8', cursor: 'pointer' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#64748B' }}>
            <span>0.5x (Small)</span>
            <span>1.0x (Default)</span>
            <span>1.5x (Large)</span>
          </div>
        </div>

        {/* Sound FX Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px', fontWeight: 600 }}>
          <span>Sound Effects</span>
          <button
            type="button"
            data-testid="pet-sound-toggle"
            onClick={() => {
              const next = { ...settings, soundEnabled: !settings.soundEnabled };
              onUpdateSettings(next);
              savePetSettings(next);
            }}
            style={{
              padding: '4px 12px',
              borderRadius: '8px',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              backgroundColor: settings.soundEnabled ? 'rgba(56, 189, 248, 0.25)' : 'rgba(255, 255, 255, 0.05)',
              color: settings.soundEnabled ? '#38BDF8' : '#64748B',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            {settings.soundEnabled ? 'ON 🔊' : 'MUTE 🔇'}
          </button>
        </div>

        {/* Inactivity Sleep Timeout Selector */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', fontWeight: 600 }}>
            <span>Inactivity Sleep Timer</span>
          </div>
          <select
            data-testid="pet-inactivity-select"
            value={settings.inactivityTimeoutMs}
            onChange={(e) => {
              const ms = parseInt(e.target.value, 10);
              const next = { ...settings, inactivityTimeoutMs: ms };
              onUpdateSettings(next);
              savePetSettings(next);
            }}
            style={{
              backgroundColor: '#1E293B',
              color: '#F8FAFC',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              borderRadius: '8px',
              padding: '6px 10px',
              fontSize: '11px',
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            <option value={10000}>10 Seconds (Dev Fast Test ⚡)</option>
            <option value={60000}>1 Minute</option>
            <option value={120000}>2 Minutes</option>
            <option value={300000}>5 Minutes (Default)</option>
            <option value={900000}>15 Minutes</option>
            <option value={0}>Never Sleep</option>
          </select>
        </div>

        {/* Reset Position */}
        {onResetPosition && (
          <button
            type="button"
            data-testid="pet-reset-pos-btn"
            onClick={onResetPosition}
            style={{
              padding: '6px 12px',
              backgroundColor: 'rgba(255, 255, 255, 0.08)',
              color: '#E2E8F0',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              borderRadius: '8px',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Reset Window Position to Bottom-Right
          </button>
        )}

        {/* Dev / Test Shortcuts Section */}
        <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.1)', paddingTop: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#FCD34D', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            🛠️ Dev & QA State Testing
          </span>

          {/* Quick Sleep Trigger */}
          {onTriggerSleepNow && (
            <button
              type="button"
              data-testid="pet-trigger-sleep-btn"
              onClick={() => {
                onTriggerSleepNow();
                onClose();
              }}
              style={{
                padding: '6px 10px',
                backgroundColor: 'rgba(245, 158, 11, 0.2)',
                color: '#FCD34D',
                border: '1px solid rgba(245, 158, 11, 0.4)',
                borderRadius: '8px',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Trigger Sleep Now (Dev Shortcut)
            </button>
          )}

          {/* Manual State Override Selector */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontSize: '11px', color: '#94A3B8' }}>Force Preview State:</span>
            <select
              data-testid="pet-manual-state-select"
              value={manualStateOverride || 'auto'}
              onChange={(e) => {
                const val = e.target.value;
                onSetManualState(val === 'auto' ? null : val);
              }}
              style={{
                backgroundColor: '#1E293B',
                color: '#F8FAFC',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: '8px',
                padding: '6px 10px',
                fontSize: '11px',
                cursor: 'pointer',
                outline: 'none',
              }}
            >
              <option value="auto">Auto (Live Backend & Hooks)</option>
              {ALL_STATES.map((st) => (
                <option key={st} value={st}>
                  {st}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PetSettingsModal;
