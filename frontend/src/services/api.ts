import type { AuditLogEntry, ModelRoleMapping, SkillItem } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:7421/api/v1';

export class ApiService {
  private static isRefreshing = false;

  private static async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    // Always include credentials so httpOnly cookies (niko_access_token) are automatically passed
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
      credentials: 'include',
    });

    if (response.status === 401 && endpoint !== '/auth/login' && endpoint !== '/auth/refresh' && endpoint !== '/auth/setup') {
      if (!this.isRefreshing) {
        this.isRefreshing = true;
        try {
          await this.refreshToken();
          this.isRefreshing = false;
          // Retry original request once
          return await this.request<T>(endpoint, options);
        } catch {
          this.isRefreshing = false;
        }
      }
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

  // -------------------------------------------------------------------
  // Authentication & First-Boot Setup (httpOnly Cookies)
  // -------------------------------------------------------------------

  public static async login(username: string, password: string): Promise<{ user_id: string; username: string; role: string }> {
    return this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
  }

  public static async setup(username: string, password: string, setupToken: string): Promise<{ message: string; user_id: string; username: string; role: string }> {
    return this.request('/auth/setup', {
      method: 'POST',
      body: JSON.stringify({ username, password, setup_token: setupToken }),
    });
  }

  public static async refreshToken(): Promise<{ user_id: string }> {
    return this.request('/auth/refresh', {
      method: 'POST',
    });
  }

  public static async logout(): Promise<{ message: string }> {
    return this.request('/auth/logout', {
      method: 'POST',
    });
  }

  public static async getMe(): Promise<{ id: string; username: string; role: string }> {
    return this.request('/auth/me');
  }

  // -------------------------------------------------------------------
  // Health & System
  // -------------------------------------------------------------------

  public static async getHealth(): Promise<{ status: string; uptime_seconds: number }> {
    return this.request<{ status: string; uptime_seconds: number }>('/health');
  }

  // -------------------------------------------------------------------
  // Models & Roles
  // -------------------------------------------------------------------

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

  // -------------------------------------------------------------------
  // Skills
  // -------------------------------------------------------------------

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

  // -------------------------------------------------------------------
  // Human-in-the-Loop Approvals
  // -------------------------------------------------------------------

  public static async respondToApproval(
    approvalId: string,
    decision: 'approved' | 'rejected'
  ): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/approvals/${approvalId}/respond`, {
      method: 'POST',
      body: JSON.stringify({ decision }),
    });
  }

  // -------------------------------------------------------------------
  // Audit Logs
  // -------------------------------------------------------------------

  public static async getAuditLogs(): Promise<AuditLogEntry[]> {
    try {
      const data = await this.request<{ logs: AuditLogEntry[] }>('/audit/logs');
      return data.logs || [];
    } catch {
      return [];
    }
  }
}
