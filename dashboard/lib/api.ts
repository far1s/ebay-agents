const BASE = process.env.NEXT_PUBLIC_API_URL || ''

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(`API error ${res.status}: ${err}`)
  }
  return res.json()
}

// ── Types ─────────────────────────────────────────────────────────────────────

export type SystemStatus = {
  system_status: 'running' | 'idle' | 'error'
  active_run_id: string | null
  latest_run: Run | null
  agents: Record<string, AgentInfo>
  pending_approvals: number
}

export type AgentInfo = {
  last_score: number | null
  avg_score: number
  last_run: string | null
  status: 'running' | 'idle' | 'error'
}

export type Run = {
  id: string
  run_id: string
  started_at: string
  completed_at: string | null
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  boss_report: {
    summary: string
    agent_scores: Record<string, { score: number; notes: string }>
  } | null
}

export type Listing = {
  id: string
  run_id: string
  ebay_listing_id: string
  ebay_url: string
  title: string
  price: number
  status: 'active' | 'sold' | 'ended' | 'error'
  listed_at: string
}

export type LogEntry = {
  id: string
  run_id: string | null
  agent_name: string
  level: 'debug' | 'info' | 'warning' | 'error'
  message: string
  timestamp: string
}

export type ScheduleSettings = {
  enabled: boolean
  cron: string
  timezone: string
}

export type HealthCheck = {
  api: string
  anthropic: string
  ebay: string
  telegram: string
  supabase: string
  ebay_sandbox: string
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const api = {
  health: () => apiFetch<HealthCheck>('/api/health'),

  status: () => apiFetch<SystemStatus>('/api/agents/status'),
  triggerRun: () => apiFetch<{ run_id: string; status: string }>('/api/agents/run', { method: 'POST', body: '{}' }),
  getRuns: (limit = 20) => apiFetch<{ runs: Run[] }>(`/api/agents/runs?limit=${limit}`),
  getRun: (runId: string) => apiFetch<{ run: Run; agent_performance: unknown[]; recent_logs: LogEntry[] }>(`/api/agents/runs/${runId}`),

  getListings: (status?: string, limit = 50) =>
    apiFetch<{ listings: Listing[]; total: number; stats: Record<string, number> }>(
      `/api/listings${status ? `?status=${status}&limit=${limit}` : `?limit=${limit}`}`
    ),

  getLogs: (params?: { run_id?: string; agent_name?: string; level?: string; limit?: number }) => {
    const qs = new URLSearchParams()
    if (params?.run_id) qs.set('run_id', params.run_id)
    if (params?.agent_name) qs.set('agent_name', params.agent_name)
    if (params?.level) qs.set('level', params.level)
    if (params?.limit) qs.set('limit', String(params.limit))
    return apiFetch<{ logs: LogEntry[]; count: number }>(`/api/logs?${qs}`)
  },

  getSchedule: () => apiFetch<ScheduleSettings>('/api/schedule'),
  updateSchedule: (s: ScheduleSettings) =>
    apiFetch<{ saved: boolean; settings: ScheduleSettings }>('/api/schedule', { method: 'POST', body: JSON.stringify(s) }),
}
