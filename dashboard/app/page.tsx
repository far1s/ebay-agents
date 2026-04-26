'use client'

import { useEffect, useState, useCallback } from 'react'
import { api, SystemStatus, LogEntry } from '@/lib/api'
import { formatDistanceToNow } from 'date-fns'

const AGENT_LABELS: Record<string, string> = {
  market_agent: 'Market Agent',
  design_agent: 'Design Agent',
  telegram_agent: 'Telegram Agent',
  listing_agent: 'Listing Agent',
  boss_agent: 'Boss Agent',
}

export default function DashboardPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [s, l] = await Promise.all([api.status(), api.getLogs({ limit: 20 })])
      setStatus(s)
      setLogs(l.logs)
      setError(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to fetch status')
    }
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 5000)
    return () => clearInterval(interval)
  }, [refresh])

  const handleRun = async () => {
    setRunning(true)
    try {
      await api.triggerRun()
      await refresh()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to start run')
    } finally {
      setRunning(false)
    }
  }

  const isRunning = status?.system_status === 'running'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-gray-400 text-sm mt-1">Automated eBay Digital Product Sales</p>
        </div>
        <button
          onClick={handleRun}
          disabled={isRunning || running}
          className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:cursor-not-allowed
                     text-white font-semibold rounded-lg transition-colors text-sm"
        >
          {isRunning ? (
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              Running...
            </span>
          ) : running ? 'Starting...' : '▶ Run Now'}
        </button>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-3 text-sm">{error}</div>
      )}

      {/* Quick stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="System Status" value={isRunning ? 'Running' : 'Idle'} color={isRunning ? 'green' : 'gray'} />
        <StatCard label="Active Run" value={status?.active_run_id ? status.active_run_id.slice(0, 16) + '...' : '—'} />
        <StatCard label="Pending Approvals" value={String(status?.pending_approvals ?? 0)} color={status?.pending_approvals ? 'yellow' : 'gray'} />
        <StatCard label="Last Run Status" value={status?.latest_run?.status ?? '—'} color={status?.latest_run?.status === 'completed' ? 'green' : status?.latest_run?.status === 'failed' ? 'red' : 'gray'} />
      </div>

      {/* Last run boss report */}
      {status?.latest_run?.boss_report && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="text-base font-semibold text-white mb-2">Last Run Summary</h2>
          <p className="text-gray-300 text-sm mb-4">{status.latest_run.boss_report.summary}</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(status.latest_run.boss_report.agent_scores || {}).map(([agent, data]) => {
              const score = typeof data === 'number' ? data : (data as { score: number }).score
              return (
                <div key={agent} className="bg-gray-800 rounded-lg p-3">
                  <div className="text-xs text-gray-400 mb-1">{AGENT_LABELS[agent] ?? agent}</div>
                  <div className="flex items-center gap-1">
                    <span className={`text-lg font-bold ${score >= 8 ? 'text-green-400' : score >= 6 ? 'text-yellow-400' : 'text-red-400'}`}>
                      {score}
                    </span>
                    <span className="text-gray-500 text-xs">/10</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Agent status cards */}
      <div>
        <h2 className="text-base font-semibold text-white mb-3">Agent Activity</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {status?.agents
            ? Object.entries(status.agents).map(([name, info]) => (
                <AgentMiniCard key={name} name={AGENT_LABELS[name] ?? name} info={info} />
              ))
            : Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>

      {/* Live log feed */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-base font-semibold text-white mb-3">Live Activity Feed</h2>
        <div className="space-y-1.5 max-h-72 overflow-y-auto font-mono text-xs">
          {logs.length === 0 ? (
            <p className="text-gray-500 text-center py-6">No recent activity</p>
          ) : (
            logs.map((log) => (
              <div key={log.id} className="flex gap-3 items-start">
                <span className="text-gray-600 shrink-0 w-16 text-right">
                  {formatDistanceToNow(new Date(log.timestamp), { addSuffix: true })}
                </span>
                <LevelBadge level={log.level} />
                <span className="text-gray-400 shrink-0">{log.agent_name}</span>
                <span className={log.level === 'error' ? 'text-red-300' : log.level === 'warning' ? 'text-yellow-300' : 'text-gray-300'}>
                  {log.message}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value, color = 'gray' }: { label: string; value: string; color?: string }) {
  const colorMap: Record<string, string> = {
    green: 'text-green-400',
    red: 'text-red-400',
    yellow: 'text-yellow-400',
    gray: 'text-white',
  }
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className={`text-lg font-bold truncate ${colorMap[color]}`}>{value}</div>
    </div>
  )
}

function AgentMiniCard({ name, info }: { name: string; info: { last_score: number | null; avg_score: number; last_run: string | null; status: string } }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-white">{name}</span>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${info.status === 'running' ? 'bg-green-900 text-green-300' : 'bg-gray-800 text-gray-400'}`}>
          {info.status}
        </span>
      </div>
      <div className="flex items-center gap-4 text-xs text-gray-400">
        <span>Last: <strong className="text-white">{info.last_score ?? '—'}/10</strong></span>
        <span>Avg: <strong className="text-white">{info.avg_score || '—'}</strong></span>
      </div>
      {info.last_run && (
        <div className="text-xs text-gray-600 mt-1 truncate">
          {formatDistanceToNow(new Date(info.last_run), { addSuffix: true })}
        </div>
      )}
    </div>
  )
}

function LevelBadge({ level }: { level: string }) {
  const map: Record<string, string> = {
    info: 'text-blue-400',
    warning: 'text-yellow-400',
    error: 'text-red-400',
    debug: 'text-gray-500',
  }
  return <span className={`shrink-0 uppercase font-bold ${map[level] ?? 'text-gray-400'}`}>{level.slice(0, 4)}</span>
}

function SkeletonCard() {
  return <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 animate-pulse h-20" />
}
