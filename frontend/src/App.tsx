import React, { useCallback, useEffect, useState } from 'react';
import { ApprovalModal } from './components/ApprovalModal';
import { AuditView } from './components/AuditView';
import { ChatCockpit } from './components/ChatCockpit';
import { CommandPalette } from './components/CommandPalette';
import { DashboardView } from './components/DashboardView';
import { Header } from './components/Header';
import { KeyboardShortcutsModal } from './components/KeyboardShortcutsModal';
import { LoginModal } from './components/LoginModal';
import { SettingsView } from './components/SettingsView';
import { Sidebar } from './components/Sidebar';
import type { ActiveTab } from './components/Sidebar';
import { SkillsView } from './components/SkillsView';
import { ToastContainer } from './components/ToastContainer';
import { ApiService } from './services/api';
import { toastService } from './services/toast';
import { wsClient } from './services/websocket';
import { DesktopPet } from './components/DesktopPet';
import type { ApprovalRequestItem, ChatMessage, CooldownBannerState, SystemMetrics } from './types';

export const App: React.FC = () => {
  const [viewMode] = useState<'overlay' | 'dashboard'>(() => {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('view') === 'dashboard' ? 'dashboard' : 'overlay';
  });

  const [activeTab, setActiveTab] = useState<ActiveTab>('chat');
  const [isOnline, setIsOnline] = useState<boolean>(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isShortcutsHelpOpen, setIsShortcutsHelpOpen] = useState(false);
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentRequestId, setCurrentRequestId] = useState<string | null>(null);
  const [cooldownBanner, setCooldownBanner] = useState<CooldownBannerState | null>(null);
  const [currentApproval, setCurrentApproval] = useState<ApprovalRequestItem | null>(null);
  const [currentUser, setCurrentUser] = useState<{ username: string; role: string } | null>(null);

  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return (localStorage.getItem('niko_theme') as 'dark' | 'light') || 'dark';
  });

  const [activeModelName] = useState('groq/llama-3.3-70b');

  const [metrics, setMetrics] = useState<SystemMetrics>({
    coreOnline: false,
    cpuPercent: 18,
    ramUsageGb: 6.4,
    ramTotalGb: 32,
    pingMs: 24,
    activeSocket: 'IPC:///ws?hub',
    contextUsed: 4812,
    contextMax: 128000,
  });

  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // Apply theme class to <html>
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
      root.classList.remove('light');
    } else {
      root.classList.add('light');
      root.classList.remove('dark');
    }
    localStorage.setItem('niko_theme', theme);
  }, [theme]);

  // Check current session
  const checkSession = useCallback(async () => {
    try {
      const me = await ApiService.getMe();
      if (me && me.username) {
        setCurrentUser({ username: me.username, role: me.role });
      } else {
        setCurrentUser(null);
      }
    } catch {
      setCurrentUser(null);
    }
  }, []);

  useEffect(() => {
    let active = true;
    ApiService.getMe()
      .then((me) => {
        if (!active) return;
        if (me && me.username) {
          setCurrentUser({ username: me.username, role: me.role });
        } else {
          setCurrentUser(null);
        }
      })
      .catch(() => {
        if (active) setCurrentUser(null);
      });

    return () => {
      active = false;
    };
  }, []);

  // Initialize WebSocket & Event Listeners
  useEffect(() => {
    wsClient.connect();

    const unsubConnection = wsClient.on('connection_status', (payload: any) => {
      setIsOnline(Boolean(payload.connected));
      setMetrics((prev) => ({ ...prev, coreOnline: Boolean(payload.connected) }));
    });

    const unsubChunk = wsClient.on('chat:chunk', (data: any) => {
      const chunkText = data.chunk || '';
      setMessages((prev) => {
        const lastMsg = prev[prev.length - 1];
        if (lastMsg && lastMsg.role === 'assistant' && lastMsg.isStreaming) {
          return [
            ...prev.slice(0, -1),
            { ...lastMsg, content: lastMsg.content + chunkText },
          ];
        }
        return [
          ...prev,
          {
            id: `msg_${Date.now()}`,
            role: 'assistant',
            content: chunkText,
            timestamp: new Date().toISOString(),
            isStreaming: true,
          },
        ];
      });
    });

    const unsubToolCall = wsClient.on('chat:tool_call', (data: any) => {
      setMessages((prev) => {
        const lastMsg = prev[prev.length - 1];
        const newToolCall = {
          id: data.tool_call_id || `tc_${Date.now()}`,
          name: data.name,
          arguments: data.arguments || {},
          status: 'running' as const,
        };

        if (lastMsg && lastMsg.role === 'assistant') {
          const currentTools = lastMsg.toolCalls || [];
          return [
            ...prev.slice(0, -1),
            { ...lastMsg, toolCalls: [...currentTools, newToolCall] },
          ];
        }

        return [
          ...prev,
          {
            id: `msg_${Date.now()}`,
            role: 'assistant',
            content: '',
            timestamp: new Date().toISOString(),
            toolCalls: [newToolCall],
            isStreaming: true,
          },
        ];
      });
    });

    const unsubToolResult = wsClient.on('chat:tool_result', (data: any) => {
      setMessages((prev) => {
        const lastMsg = prev[prev.length - 1];
        if (!lastMsg || !lastMsg.toolCalls) return prev;

        const updatedTools = lastMsg.toolCalls.map((tc) => {
          if (tc.name === data.name || tc.id === data.tool_call_id) {
            return {
              ...tc,
              result: data.result,
              error: data.error,
              status: (data.status === 'failed' ? 'failed' : 'completed') as any,
            };
          }
          return tc;
        });

        return [...prev.slice(0, -1), { ...lastMsg, toolCalls: updatedTools }];
      });
    });

    const unsubApproval = wsClient.on('chat:approval_required', (data: any) => {
      const approvalData = data.approval || {};
      setCurrentApproval({
        id: approvalData.id || `appr_${Date.now()}`,
        requestId: data.request_id,
        toolName: approvalData.tool_name || 'restricted_skill',
        arguments: approvalData.arguments || {},
        riskLevel: approvalData.risk_level || 'high',
        reason: approvalData.reason,
        status: 'pending',
        createdAt: new Date().toISOString(),
        timeoutSeconds: approvalData.timeout_seconds || 30,
      });
    });

    const unsubDone = wsClient.on('chat:done', (data: any) => {
      setIsStreaming(false);
      setCurrentRequestId(null);
      setMessages((prev) => {
        const lastMsg = prev[prev.length - 1];
        if (lastMsg && lastMsg.role === 'assistant') {
          return [
            ...prev.slice(0, -1),
            {
              ...lastMsg,
              content: lastMsg.content || data.response?.content || '',
              isStreaming: false,
            },
          ];
        }
        return prev;
      });
    });

    const unsubCancelled = wsClient.on('chat:cancelled', () => {
      setIsStreaming(false);
      setCurrentRequestId(null);
      setMessages((prev) => {
        const lastMsg = prev[prev.length - 1];
        if (lastMsg && lastMsg.role === 'assistant') {
          return [
            ...prev.slice(0, -1),
            { ...lastMsg, isStreaming: false, content: lastMsg.content + ' [Inference Cancelled]' },
          ];
        }
        return prev;
      });
    });

    const unsubCooldown = wsClient.on('chat:cooldown_banner', (data: any) => {
      const shortestSec = data.shortest_reset_seconds || 30;
      setCooldownBanner({
        active: true,
        role: data.role,
        message: data.message,
        shortestResetSeconds: shortestSec,
        remainingSeconds: shortestSec,
        requestId: data.request_id,
      });
    });

    return () => {
      unsubConnection();
      unsubChunk();
      unsubToolCall();
      unsubToolResult();
      unsubApproval();
      unsubDone();
      unsubCancelled();
      unsubCooldown();
      wsClient.disconnect();
    };
  }, []);

  // Cooldown countdown timer
  useEffect(() => {
    if (!cooldownBanner || !cooldownBanner.active || !cooldownBanner.remainingSeconds) return;

    const timer = setInterval(() => {
      setCooldownBanner((prev) => {
        if (!prev || !prev.remainingSeconds || prev.remainingSeconds <= 1) {
          clearInterval(timer);
          return null;
        }
        return { ...prev, remainingSeconds: prev.remainingSeconds - 1 };
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [cooldownBanner]);

  const handleApprovalResponse = useCallback(async (approvalId: string, decision: 'approved' | 'rejected') => {
    try {
      await ApiService.respondToApproval(approvalId, decision);
      toastService.info(
        'Approval Sent',
        `Action was ${decision === 'approved' ? 'approved for execution' : 'denied'}.`
      );
    } catch (err: any) {
      toastService.error('Dispatch Failed', err.message || 'Could not dispatch approval decision.');
    } finally {
      setCurrentApproval(null);
    }
  }, []);

  // Global Keyboard Shortcuts (⌘K, ⌘1-6, ?, Y/N for approvals)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Approval hotkeys when approval modal is open
      if (currentApproval) {
        if (e.key === 'y' || e.key === 'Y') {
          e.preventDefault();
          handleApprovalResponse(currentApproval.id, 'approved');
          return;
        }
        if (e.key === 'n' || e.key === 'N' || e.key === 'Escape') {
          e.preventDefault();
          handleApprovalResponse(currentApproval.id, 'rejected');
          return;
        }
      }

      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsCommandPaletteOpen((prev) => !prev);
      } else if (e.key === '?' && !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) {
        e.preventDefault();
        setIsShortcutsHelpOpen((prev) => !prev);
      } else if ((e.metaKey || e.ctrlKey) && e.key === '1') {
        e.preventDefault();
        setActiveTab('chat');
      } else if ((e.metaKey || e.ctrlKey) && e.key === '2') {
        e.preventDefault();
        setActiveTab('dashboard');
      } else if ((e.metaKey || e.ctrlKey) && e.key === '3') {
        e.preventDefault();
        setActiveTab('usage');
      } else if ((e.metaKey || e.ctrlKey) && e.key === '4') {
        e.preventDefault();
        setActiveTab('skills');
      } else if ((e.metaKey || e.ctrlKey) && e.key === '5') {
        e.preventDefault();
        setActiveTab('admin');
      } else if ((e.metaKey || e.ctrlKey) && e.key === '6') {
        e.preventDefault();
        setActiveTab('settings');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentApproval, handleApprovalResponse]);

  const handleSendMessage = (content: string, role = 'chat', elevatedMode = false) => {
    const reqId = `req_${Date.now()}`;
    setCurrentRequestId(reqId);
    setIsStreaming(true);

    const isExternal = content.includes('<untrusted_external_content>') || content.toLowerCase().includes('http');

    // Optimistically add user message immediately
    setMessages((prev) => [
      ...prev,
      {
        id: `usr_${Date.now()}`,
        role: 'user',
        content,
        timestamp: new Date().toISOString(),
        isExternal,
      },
    ]);

    wsClient.sendChat(reqId, content, undefined, role, elevatedMode);
  };

  const handleCancelChat = () => {
    if (currentRequestId) {
      wsClient.cancelChat(currentRequestId);
      toastService.info('Cancelled', 'Inference stream aborted.');
    }
    setIsStreaming(false);
  };

  if (viewMode === 'overlay') {
    return <DesktopPet />;
  }

  return (
    <div className="flex h-screen w-screen bg-surface-container-lowest text-on-surface font-sans overflow-hidden">
      {/* Left Sidebar Rail */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        isOnline={isOnline}
        activeModelName={activeModelName}
      />

      {/* Main Container */}
      <div className="flex-1 flex flex-col pl-16 h-full overflow-hidden">
        {/* Top Header */}
        <Header
          metrics={metrics}
          activeModelName={activeModelName}
          theme={theme}
          onToggleTheme={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))}
          onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
          onOpenShortcutsHelp={() => setIsShortcutsHelpOpen(true)}
          onOpenSettings={() => setActiveTab('settings')}
          onOpenLogin={() => setIsLoginOpen(true)}
          currentUser={currentUser}
        />

        {/* View Routing */}
        <main className="flex-1 pt-12 h-full overflow-hidden flex flex-col">
          {activeTab === 'chat' && (
            <ChatCockpit
              messages={messages}
              isStreaming={isStreaming}
              activeModelName={activeModelName}
              cooldownBanner={cooldownBanner}
              onSendMessage={handleSendMessage}
              onCancelChat={handleCancelChat}
              onOpenModelSelector={() => setActiveTab('settings')}
            />
          )}

          {activeTab === 'dashboard' && (
            <DashboardView
              metrics={metrics}
              onRefresh={async () => {
                try {
                  const health = await ApiService.getHealth();
                  setIsOnline(health.status === 'healthy');
                  toastService.success('Telemetry Refreshed', `Core is online (Uptime: ${health.uptime_seconds}s).`);
                } catch {
                  setIsOnline(false);
                  toastService.error('Telemetry Error', 'Backend service unreachable.');
                }
              }}
            />
          )}

          {activeTab === 'usage' && (
            <DashboardView
              metrics={metrics}
              onRefresh={() => {}}
            />
          )}

          {activeTab === 'skills' && <SkillsView />}

          {activeTab === 'settings' && <SettingsView />}

          {activeTab === 'admin' && <AuditView />}
        </main>
      </div>

      {/* HITL Approval Modal */}
      <ApprovalModal
        request={currentApproval}
        onApprove={(id) => handleApprovalResponse(id, 'approved')}
        onReject={(id) => handleApprovalResponse(id, 'rejected')}
        onClose={() => setCurrentApproval(null)}
      />

      {/* ⌘K Command Palette Modal */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onSelectTab={setActiveTab}
        onRunPrompt={(prompt) => {
          setActiveTab('chat');
          handleSendMessage(prompt);
        }}
      />

      {/* Keyboard Shortcuts Reference Modal */}
      <KeyboardShortcutsModal
        isOpen={isShortcutsHelpOpen}
        onClose={() => setIsShortcutsHelpOpen(false)}
      />

      {/* Operator Login / Setup Modal */}
      <LoginModal
        isOpen={isLoginOpen}
        onClose={() => setIsLoginOpen(false)}
        currentUser={currentUser}
        onLoginSuccess={() => {
          checkSession();
          wsClient.disconnect();
          wsClient.connect();
          toastService.success('Authenticated', 'Session authenticated successfully.');
        }}
        onLogout={() => {
          setCurrentUser(null);
          wsClient.disconnect();
          wsClient.connect();
          toastService.info('Logged Out', 'Operator session terminated.');
        }}
      />

      {/* Reactive Toast Notification Stack */}
      <ToastContainer />
    </div>
  );
};

export default App;
