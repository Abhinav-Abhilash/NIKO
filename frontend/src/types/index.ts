export type RoleType = 'user' | 'assistant' | 'system' | 'tool';

export interface ToolCallItem {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  result?: unknown;
  error?: string;
  status?: 'pending' | 'running' | 'completed' | 'failed' | 'requires_approval';
}

export interface ApprovalRequestItem {
  id: string;
  requestId?: string;
  toolName: string;
  arguments: Record<string, unknown>;
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  reason?: string;
  status: 'pending' | 'approved' | 'rejected' | 'timed_out';
  createdAt: string;
  timeoutSeconds?: number;
}

export interface ChatMessage {
  id: string;
  role: RoleType;
  content: string;
  timestamp: string;
  toolCalls?: ToolCallItem[];
  isExternal?: boolean;
  isStreaming?: boolean;
  error?: string;
  source?: string;
}

export interface CooldownBannerState {
  active: boolean;
  role?: string;
  message?: string;
  shortestResetSeconds?: number;
  remainingSeconds?: number;
  requestId?: string;
}

export interface SystemMetrics {
  coreOnline: boolean;
  cpuPercent: number;
  ramUsageGb: number;
  ramTotalGb: number;
  pingMs: number;
  activeSocket: string;
  contextUsed: number;
  contextMax: number;
}

export interface ModelTarget {
  provider: string;
  model: string;
  temperature?: number;
  maxOutputTokens?: number;
  reasoningEffort?: string;
  priority?: number;
}

export interface ModelRoleMapping {
  role: 'chat' | 'tool_calling' | 'fast' | 'reasoning' | 'vision';
  targets: ModelTarget[];
}

export interface SkillItem {
  id: string;
  name: string;
  description: string;
  category: string;
  enabled: boolean;
  riskLevel: 'low' | 'medium' | 'high';
  requiresApproval: boolean;
  timeoutSeconds: number;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  action: string;
  actor: string;
  resource: string;
  status: 'SUCCESS' | 'FAILURE' | 'DENIED';
  details?: Record<string, unknown>;
  hmacVerified: boolean;
}
