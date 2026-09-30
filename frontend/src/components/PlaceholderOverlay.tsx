import React, { useState } from 'react';
import {
  useOverlay,
  useChatStream,
  useApprovals,
  useOrbState,
  useProviderStatus,
} from '../hooks';

/**
 * Plain, unstyled placeholder UI proving end-to-end wiring.
 * Intentionally void of styling, colors, glow, or animations.
 * Ready to be replaced by Flow design import.
 */
export const PlaceholderOverlay: React.FC = () => {
  const overlay = useOverlay(true, 'compact');
  const chat = useChatStream();
  const approvals = useApprovals({
    onApprovalArrive: () => {
      overlay.show('approval');
    },
  });
  const orb = useOrbState({
    hasPendingApproval: approvals.hasPendingApproval,
    isStreaming: chat.isStreaming,
    activeToolCallsCount: chat.activeToolCalls.length,
  });
  const providers = useProviderStatus();

  const [inputVal, setInputVal] = useState('');

  if (!overlay.isVisible) {
    return (
      <div id="niko-overlay-hidden" style={{ display: 'none' }}>
        {/* Render paused while hidden */}
      </div>
    );
  }

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim()) return;
    chat.sendMessage(inputVal);
    setInputVal('');
  };

  return (
    <div
      id="niko-overlay-container"
      style={{
        padding: '16px',
        maxWidth: overlay.mode === 'expanded' ? '800px' : '500px',
        margin: '20px auto',
        backgroundColor: 'rgba(20, 20, 20, 0.95)',
        color: '#ffffff',
        border: '1px solid #444',
        borderRadius: '8px',
        fontFamily: 'monospace',
      }}
    >
      {/* Header bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
        <span>NIKO (State: <strong>{orb.orbState}</strong>)</span>
        <div>
          <button
            type="button"
            onClick={() => overlay.setMode(overlay.mode === 'compact' ? 'expanded' : 'compact')}
            style={{ marginRight: '8px' }}
          >
            {overlay.mode === 'compact' ? 'Expand' : 'Compact'}
          </button>
          <button type="button" onClick={overlay.hide}>
            Hide (Esc)
          </button>
        </div>
      </div>

      {/* Provider Cooldown Banner */}
      {providers.isCoolingDown && (
        <div style={{ background: '#773300', padding: '6px', marginBottom: '8px', borderRadius: '4px' }}>
          <strong>COOLDOWN:</strong> {providers.cooldownMessage} (reset in {providers.shortestResetSeconds}s)
        </div>
      )}

      {/* Active Approval Modal / Dialog */}
      {approvals.hasPendingApproval && approvals.pendingApproval && (
        <div
          id="niko-approval-card"
          style={{
            border: '2px solid #ffaa00',
            padding: '12px',
            marginBottom: '12px',
            backgroundColor: '#221100',
          }}
        >
          <h4 style={{ margin: '0 0 6px 0', color: '#ffaa00' }}>
            CONFIRMATION REQUIRED ({approvals.remainingSeconds}s)
          </h4>
          <p style={{ margin: '4px 0' }}>
            Skill: <strong>{approvals.pendingApproval.skillName}</strong>
          </p>
          <p style={{ margin: '4px 0' }}>
            Arguments: <code>{JSON.stringify(approvals.pendingApproval.arguments)}</code>
          </p>
          <p style={{ margin: '4px 0', fontSize: '11px', color: '#aaa' }}>
            Provenance: {approvals.pendingApproval.provenance}
          </p>

          <div style={{ marginTop: '10px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              id="approve-once-btn"
              type="button"
              onClick={() => approvals.approve('once')}
              style={{ fontWeight: 'bold' }}
            >
              Approve (Enter)
            </button>
            <button
              id="approve-session-btn"
              type="button"
              onClick={() => approvals.approve('session')}
            >
              Allow for this session
            </button>
            <button
              id="approve-always-btn"
              type="button"
              onClick={() => approvals.approve('always')}
            >
              Always allow this action
            </button>
            <button
              id="deny-btn"
              type="button"
              onClick={() => approvals.deny('denied_by_user')}
            >
              Deny (Esc)
            </button>
          </div>
        </div>
      )}

      {/* Message stream */}
      <div
        id="niko-message-list"
        style={{
          maxHeight: overlay.mode === 'expanded' ? '400px' : '200px',
          overflowY: 'auto',
          marginBottom: '12px',
          borderBottom: '1px solid #333',
          paddingBottom: '8px',
        }}
      >
        {chat.messages.length === 0 ? (
          <div style={{ color: '#888', fontStyle: 'italic' }}>
            No messages yet. Type a query below.
          </div>
        ) : (
          chat.messages.map((m) => (
            <div key={m.id} style={{ margin: '6px 0' }}>
              <strong>{m.role}: </strong>
              <span>{m.content}</span>

              {m.toolCalls && m.toolCalls.length > 0 && (
                <div style={{ paddingLeft: '12px', fontSize: '12px', color: '#88cc88' }}>
                  {m.toolCalls.map((tc) => (
                    <div key={tc.id}>
                      [Tool: {tc.name} ({tc.status})]
                      {tc.result !== undefined && <span> -&gt; {JSON.stringify(tc.result)}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Input bar */}
      <form onSubmit={handleSend} style={{ display: 'flex', gap: '8px' }}>
        <input
          id="niko-chat-input"
          ref={overlay.inputRef}
          type="text"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          placeholder="Ask NIKO (e.g. what time is it and how's my CPU)..."
          style={{
            flex: 1,
            padding: '8px',
            backgroundColor: '#111',
            color: '#fff',
            border: '1px solid #555',
            fontFamily: 'monospace',
          }}
          disabled={chat.isStreaming}
        />
        {chat.isStreaming ? (
          <button type="button" onClick={chat.cancelStream}>
            Cancel
          </button>
        ) : (
          <button type="submit" id="niko-submit-btn">
            Send
          </button>
        )}
      </form>

      {/* Footer Settings */}
      <div style={{ marginTop: '8px', fontSize: '11px', color: '#777', display: 'flex', justifyContent: 'space-between' }}>
        <label>
          <input
            type="checkbox"
            checked={overlay.autoHideOnBlur}
            onChange={(e) => overlay.setAutoHideOnBlur(e.target.checked)}
          />{' '}
          Auto-hide on blur
        </label>
        {chat.messages.length > 0 && (
          <button type="button" onClick={chat.clearMessages} style={{ fontSize: '10px' }}>
            Clear History
          </button>
        )}
      </div>
    </div>
  );
};
