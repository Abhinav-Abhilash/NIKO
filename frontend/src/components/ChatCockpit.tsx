import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ChatMessage, CooldownBannerState } from '../types';
import { CockpitCore } from './CockpitCore';

interface ChatCockpitProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  activeModelName: string;
  cooldownBanner: CooldownBannerState | null;
  onSendMessage: (content: string, role?: string, elevatedMode?: boolean) => void;
  onCancelChat: () => void;
  onOpenModelSelector: () => void;
}

export const ChatCockpit: React.FC<ChatCockpitProps> = ({
  messages,
  isStreaming,
  activeModelName,
  cooldownBanner,
  onSendMessage,
  onCancelChat,
  onOpenModelSelector,
}) => {
  const [inputContent, setInputContent] = useState('');
  const [elevatedMode, setElevatedMode] = useState(false);
  const [selectedRole, setSelectedRole] = useState<'chat' | 'fast' | 'reasoning'>('chat');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputContent.trim() || isStreaming) return;

    onSendMessage(inputContent.trim(), selectedRole, elevatedMode);
    setInputContent('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleTextareaInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputContent(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`;
  };

  return (
    <div className="flex flex-col w-full h-full bg-surface-container-lowest text-on-surface overflow-hidden">
      {/* Top Cockpit Reactor Core Strip */}
      <CockpitCore
        isStreaming={isStreaming}
        activeModelName={activeModelName}
        contextUsed={messages.reduce((acc, m) => acc + (m.content.length / 4), 0)}
        contextMax={128000}
        elevatedMode={elevatedMode}
        onToggleElevated={() => setElevatedMode((prev) => !prev)}
        onOpenModelSelector={onOpenModelSelector}
      />

      {/* Workspace Telemetry Overlay Bar */}
      <div className="w-full bg-surface-container px-gutter-md py-1 flex items-center justify-between text-mono-sm font-mono text-on-surface-variant border-b border-surface-variant/40 select-none">
        <div className="flex items-center gap-space-md truncate">
          <span>THREAD: 0x9F41_DISPATCH</span>
          <span>MEMORY_SURFACE: 78.4 MB</span>
          <span>ACTIVE_SOCKET: IPC:///ws?hub</span>
        </div>
        <div className="flex items-center gap-space-sm flex-shrink-0">
          <span className="text-label-caps font-semibold text-on-surface-variant">DIAGNOSTIC TRACE</span>
          <span className="w-1.5 h-1.5 bg-secondary rounded-full" />
          <span className="text-on-surface font-semibold">NOMINAL</span>
        </div>
      </div>

      {/* Cooldown Banner Alert */}
      {cooldownBanner && cooldownBanner.active && (
        <div className="w-full bg-primary-container/15 border-b border-primary-container/40 px-gutter-md py-2.5 flex items-center justify-between animate-in fade-in slide-in-from-top-2">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-primary-container animate-spin">
              hourglass_top
            </span>
            <div className="flex flex-col">
              <span className="font-mono text-xs text-primary font-bold">
                RATE LIMIT COOLDOWN ACTIVE // ROLE: {cooldownBanner.role?.toUpperCase()}
              </span>
              <span className="font-mono text-xs text-on-surface-variant">
                {cooldownBanner.message || 'All providers cooling down. Request queued for auto-retry.'}
              </span>
            </div>
          </div>
          {cooldownBanner.remainingSeconds !== undefined && (
            <div className="flex items-center gap-2 font-mono text-xs">
              <span className="text-on-surface-variant">RESET IN:</span>
              <span className="px-2 py-1 bg-primary-container text-on-primary-container font-bold rounded">
                {Math.max(1, Math.round(cooldownBanner.remainingSeconds))}s
              </span>
            </div>
          )}
        </div>
      )}

      {/* Conversation Viewport */}
      <div className="flex-1 overflow-y-auto px-gutter-md py-space-lg flex flex-col gap-6 max-w-5xl mx-auto w-full">
        {messages.length === 0 ? (
          <div className="my-auto flex flex-col items-center justify-center text-center p-8 border border-dashed border-surface-variant/40 rounded-2xl bg-surface-container/20">
            <div className="w-16 h-16 rounded-2xl bg-primary-container/10 border border-primary-container/30 flex items-center justify-center text-primary mb-4">
              <span className="material-symbols-outlined text-3xl text-primary-container">
                terminal
              </span>
            </div>
            <h2 className="font-mono text-lg font-bold text-on-surface mb-1">
              NIKO AUTONOMOUS COCKPIT READY
            </h2>
            <p className="font-mono text-xs text-on-surface-variant max-w-md mb-6">
              Full streaming chat with multi-provider fallback, tool dispatch, and security provenance tracking.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-lg text-left font-mono text-xs">
              <button
                onClick={() => onSendMessage('What models are currently active in my fallback chain?')}
                className="p-3 rounded-lg bg-surface-container-low border border-surface-variant/40 hover:border-primary-container/60 transition-colors text-on-surface"
              >
                <div className="text-primary font-semibold mb-1">Model Chain Check</div>
                <div className="text-on-surface-variant text-[11px]">Inspect active providers & fallbacks</div>
              </button>
              <button
                onClick={() => onSendMessage('Show system diagnostics and memory telemetry.')}
                className="p-3 rounded-lg bg-surface-container-low border border-surface-variant/40 hover:border-primary-container/60 transition-colors text-on-surface"
              >
                <div className="text-primary font-semibold mb-1">System Telemetry</div>
                <div className="text-on-surface-variant text-[11px]">View memory, CPU, and socket states</div>
              </button>
            </div>
          </div>
        ) : (
          messages.map((msg) => {
            const isUser = msg.role === 'user';
            return (
              <div
                key={msg.id}
                className={`flex flex-col w-full group ${
                  isUser ? 'items-end' : 'items-start'
                }`}
              >
                {/* Meta Header */}
                <div className="flex items-center gap-space-xs text-mono-sm font-mono text-on-surface-variant mb-1">
                  <span className={`font-semibold ${isUser ? 'text-primary' : 'text-secondary'}`}>
                    {isUser ? 'OPERATOR' : 'NIKO_AGENT'}
                  </span>
                  <span>•</span>
                  <span>{new Date(msg.timestamp).toLocaleTimeString()}</span>
                  {msg.isExternal && (
                    <span className="px-1.5 py-0.5 bg-error-container/20 text-error border border-error/30 text-[10px] rounded font-bold">
                      UNTRUSTED DATA
                    </span>
                  )}
                </div>

                {/* Message Bubble */}
                <div
                  className={`max-w-[85%] rounded-xl p-4 font-mono text-sm leading-relaxed border shadow-md ${
                    isUser
                      ? 'bg-surface-container-high border-surface-variant/60 text-on-surface'
                      : 'bg-surface-container-low border-surface-variant/40 text-on-surface'
                  }`}
                >
                  {/* Untrusted wrapper warning */}
                  {msg.isExternal && (
                    <div className="mb-3 p-2.5 bg-error-container/10 border border-error/40 rounded flex items-center gap-2 text-xs text-error font-mono">
                      <span className="material-symbols-outlined text-sm">security</span>
                      <span>Content enclosed within untrusted provenance boundary. Treated strictly as data.</span>
                    </div>
                  )}

                  {/* Tool Calls Execution Cards */}
                  {msg.toolCalls && msg.toolCalls.length > 0 && (
                    <div className="mb-3 flex flex-col gap-2">
                      {msg.toolCalls.map((tc) => (
                        <div
                          key={tc.id}
                          className="bg-surface-container p-3 rounded-lg border border-surface-variant/60 font-mono text-xs flex flex-col gap-1.5"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="material-symbols-outlined text-primary-container text-base">
                                build
                              </span>
                              <span className="text-on-surface-variant">TOOL CALL:</span>
                              <span className="text-primary font-bold">{tc.name}</span>
                            </div>
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                                tc.status === 'completed'
                                  ? 'bg-secondary/10 text-secondary border border-secondary/30'
                                  : tc.status === 'failed'
                                  ? 'bg-error/10 text-error border border-error/30'
                                  : 'bg-primary-container/10 text-primary-container border border-primary-container/30'
                              }`}
                            >
                              {tc.status || 'running'}
                            </span>
                          </div>

                          {/* Arguments */}
                          {tc.arguments && Object.keys(tc.arguments).length > 0 && (
                            <div className="bg-surface-container-lowest p-2 rounded text-[11px] text-on-surface-variant overflow-x-auto">
                              <pre>{JSON.stringify(tc.arguments, null, 2)}</pre>
                            </div>
                          )}

                          {/* Tool Result Output */}
                          {tc.result !== undefined && (
                            <div className="bg-surface-container-lowest p-2 rounded text-[11px] text-secondary overflow-x-auto border-l-2 border-secondary">
                              <span className="font-bold">RESULT:</span>
                              <pre className="mt-1">{typeof tc.result === 'string' ? tc.result : JSON.stringify(tc.result, null, 2)}</pre>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Content Body */}
                  <div className="prose prose-invert max-w-none text-on-surface text-sm font-sans">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  </div>

                  {/* Streaming indicator */}
                  {msg.isStreaming && (
                    <span className="inline-block w-2 h-4 ml-1 bg-primary-container animate-pulse align-middle" />
                  )}
                </div>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Bottom Cockpit Input Panel */}
      <div className="p-gutter-md bg-surface-container-low border-t border-surface-variant/40">
        <form onSubmit={handleSubmit} className="max-w-5xl mx-auto flex flex-col gap-2">
          {/* Input Controls Header */}
          <div className="flex items-center justify-between text-mono-sm font-mono text-on-surface-variant px-1">
            <div className="flex items-center gap-3">
              {/* Role Selector */}
              <div className="flex items-center gap-1">
                <span>Role:</span>
                {(['chat', 'fast', 'reasoning'] as const).map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setSelectedRole(r)}
                    className={`px-2 py-0.5 rounded text-xs transition-colors ${
                      selectedRole === r
                        ? 'bg-primary-container text-on-primary-container font-bold'
                        : 'bg-surface-container text-on-surface-variant hover:text-on-surface'
                    }`}
                  >
                    {r.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            {/* Cancel Streaming Button */}
            {isStreaming && (
              <button
                type="button"
                onClick={onCancelChat}
                className="flex items-center gap-1.5 px-3 py-1 bg-error-container/20 text-error border border-error/40 hover:bg-error-container/40 rounded text-xs font-mono font-semibold transition-colors animate-pulse"
              >
                <span className="material-symbols-outlined text-sm">cancel</span>
                <span>Abort Inference</span>
              </button>
            )}
          </div>

          {/* Text Input Area */}
          <div className="relative flex items-end bg-surface-container border border-surface-variant/60 rounded-xl overflow-hidden focus-within:border-primary-container focus-within:ring-1 focus-within:ring-primary-container transition-all">
            <textarea
              ref={textareaRef}
              rows={1}
              value={inputContent}
              onChange={handleTextareaInput}
              onKeyDown={handleKeyDown}
              placeholder="Transmit prompt or invoke tool execution... (Shift+Enter for newline)"
              className="w-full bg-transparent px-4 py-3.5 pr-24 font-mono text-sm text-on-surface placeholder:text-on-surface-variant outline-none resize-none min-h-[50px] max-h-[180px]"
            />

            {/* Submit Button */}
            <div className="absolute right-2 bottom-2">
              <button
                type="submit"
                disabled={!inputContent.trim() || isStreaming}
                className={`flex items-center justify-center w-9 h-9 rounded-lg transition-all ${
                  inputContent.trim() && !isStreaming
                    ? 'bg-primary-container text-on-primary-container hover:bg-primary-fixed shadow-[0_0_10px_rgba(255,176,32,0.4)]'
                    : 'bg-surface-container-high text-on-surface-variant/40 cursor-not-allowed'
                }`}
              >
                <span className="material-symbols-outlined text-lg">
                  arrow_upward
                </span>
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
