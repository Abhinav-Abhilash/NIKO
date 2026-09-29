import type { AuditLogEntry, ModelRoleMapping, SkillItem } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:7421/api/v1';

export class ApiService {
  private static token: string | null = localStorage.getItem('niko_token');

  public static setToken(token: string | null): void {
    this.token = token;
    if (token) {
      localStorage.setItem('niko_token', token);
    } else {
      localStorage.removeItem('niko_token');
    }
  }

  public static getToken(): string | null {
    return this.token || localStorage.getItem('niko_token');
  }

  private static async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    const token = this.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      // Trigger token refresh or prompt unlock
      console.warn('Unauthorized API request to', endpoint);
    }

    if (!response.ok) {
      const errorText = await response.text();
      let errorMsg = `API Error ${response.status}: ${response.statusText}`;
      try {
        const errorJson = JSON.parse(errorText);
        errorMsg = errorJson.detail || errorMsg;
      } catch {
        // use raw text
      }
      throw new Error(errorMsg);
    }

    return response.json();
  }

  // Health & System
  public static async getHealth(): Promise<{ status: string; uptime_seconds: number }> {
    return this.request<{ status: string; uptime_seconds: number }>('/health');
  }

  // Models & Roles
  public static async getModelRoles(): Promise<Record<string, ModelRoleMapping>> {
    try {
      return await this.request<Record<string, ModelRoleMapping>>('/settings/model-roles');
    } catch {
      return {};
    }
  }

  public static async updateModelRoles(roles: Record<string, unknown>): Promise<void> {
    await this.request('/settings/model-roles', {
      method: 'PUT',
      body: JSON.stringify(roles),
    });
  }

  // Skills
  public static async getSkills(): Promise<SkillItem[]> {
    try {
      const data = await this.request<{ skills: SkillItem[] }>('/skills');
      return data.skills || [];
    } catch {
      return [];
    }
  }

  public static async toggleSkill(skillId: string, enabled: boolean): Promise<void> {
    await this.request(`/skills/${skillId}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    });
  }

  // Human-in-the-Loop Approvals
  public static async respondToApproval(
    approvalId: string,
    decision: 'approved' | 'rejected'
  ): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/approvals/${approvalId}/respond`, {
      method: 'POST',
      body: JSON.stringify({ decision }),
    });
  }

  // Audit Logs
  public static async getAuditLogs(): Promise<AuditLogEntry[]> {
    try {
      const data = await this.request<{ logs: AuditLogEntry[] }>('/audit/logs');
      return data.logs || [];
    } catch {
      return [];
    }
  }
}
