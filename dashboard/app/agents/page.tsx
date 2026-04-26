'use client'

import { useEffect, useState, useCallback } from 'react'
import { api, SystemStatus, Run, LogEntry } from '@/lib/api'
import { formatDistanceToNow, format } from 'date-fns'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

const AGENT_NAMES = ['market_agent', 'design_agent', 'telegram_agent', 'listing_agent', 'boss_agent']
const AGENT_LABELS: Record<string, string> = {
  market_agent: 'Market Agent',
  design_agent: 'Design Agent',
  telegram_agent: 'Telegram Agent',
  listing_agent: 'Listing Agent',
  boss_agent: 'Boss Agent',
}
const AGENT_ICONS: Record<string, string> = {
  market_agent: '📊',
  design_agent: '🎨',
  telegram_agent: '📱',
  listing_agent: '🛒',
  boss_agent: '👔',
}

export default function AgentsPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    const [s, r, l] = await Promise.all([
      api.status(),
      api.getRuns(30),
      api.getLogs({ limit: 100 }),
    ])
    setStatus(s)
    setRuns(r.runs)
    setLogs(l.logs)
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 5000)
    return () => clearInterval(interval)
  }, [refresh])

  // Build performance chart data from boss_reports
  const buildChartData = (agentName: string) => {
    return runs
      .filter((r) => r.boss_report?.agent_scores?.[agentName])
      .slice(0, 20)
      .reverse()
      .map((r) => {
        const data = r.boss_report!.agent_scores[agentName]
        const score = typeof data === 'number' ? data : (data as { score: number }).score
        return {
          run: r.run_id.slice(4, 11),
          score,
          date: format(new Date(r.started_at), 'MM/dd'),
        }
      })
  }

  const filteredLogs = selectedAgent ? logs.filter((l) => l.agent_name === selectedAgent) : logs

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Agents</h1>
        <p className="text-gray-400 text-sm mt-1">Performance and activity for each agent</p>
      </div>

      {/* Agent cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {AGENT_NAMES.map((name) => {
          const info = status?.agents?.[name]
          const chartData = buildChartData(name)
          const isActive = selectedAgent === name

          return (
            <button
              key={name}
              onClick={() => setSelectedAgent(isActive ? null : name)}
              className={`bg-gray-900 border rounded-xl p-5 text-left transition-all ${isActive ? 'border-indigo-500' : 'border-gray-800 hover:border-gray-700'}`}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-xl">{AGENT_ICONS[name]}</span>
                  <span className="font-semibold text-white">{AGENT_LABELS[name]}</span>
                </div>
                <StatusPill status={info?.status ?? 'idle'} />
              </div>

              <div className="grid grid-cols-2 gap-3 mb-3">
                <ScoreStat label="Last Score" value={info?.last_score ?? null} />
                <ScoreStat label="Avg Score" value={info?.avg_score ?? null} />
              </div>

              {chartData.length > 1 && (
                <div className="h-24">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                      <XAxis dataKey="date" tick={{ fontSize: 9, fill: '#6b7280' }} />
                      <YAxis domain={[0, 10]} tick={{ fontSize: 9, fill: '#6b7280' }} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 6, fontSize: 11 }}
                        labelStyle={{ color: '#9ca3af' }}
                      />
                      <Line type="monotone" dataKey="score" stroke="#6366f1" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {info?.last_run && (
                <p className="text-xs text-gray-600 mt-2">
                  {formatDistanceToNow(new Date(info.last_run), { addSuffix: true })}
                </p>
              )}
            </button>
          )
        })}
      </div>

      {/* Log viewer */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-white">
            {selectedAgent ? `${AGENT_LABELS[selectedAgent]} Logs` : 'All Agent Logs'}
          </h2>
          {selectedAgent && (
            <button onClick={() => setSelectedAgent(null)} className="text-xs text-gray-400 hover:text-white">
              Clear filter ×
            </button>
          )}
        </div>
        <div className="space-y-1 max-h-96 overflow-y-auto font-mono text-xs">
          {filteredLogs.length === 0 ? (
            <p className="text-gray-500 text-center py-8">No logs</p>
          ) : (
            filteredLogs.map((log) => (
              <div key={log.id} className="flex gap-3 items-start py-0.5 border-b border-gray-800/50">
                <span className="text-gray-600 shrink-0 w-28">
                  {format(new Date(log.timestamp), 'HH:mm:ss MM/dd')}
                </span>
                <LevelTag level={log.level} />
                <span className="text-gray-500 shrink-0 w-28 truncate">{log.agent_name}</span>
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

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    running: 'bg-green-900/60 text-green-300',
    idle: 'bg-gray-800 text-gray-400',
    error: 'bg-red-900/60 text-red-300',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[status] ?? map.idle}`}>
      {status === 'running' && <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400 mr-1 animate-pulse" />}
      {status}
    </span>
  )
}

function ScoreStat({ label, value }: { label: string; value: number | null }) {
  const color = value === null ? 'text-gray-500' : value >= 8 ? 'text-green-400' : value >= 6 ? 'text-yellow-400' : 'text-red-400'
  return (
    <div className="bg-gray-800 rounded-lg p-2">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-lg font-bold ${color}`}>{value ?? '—'}</div>
    </div>
  )
}

function LevelTag({ level }: { level: string }) {
  const map: Record<string, string> = {
    info: 'text-blue-400',
    warning: 'text-yellow-400',
    error: 'text-red-400',
    debug: 'text-gray-600',
  }
  return <span className={`shrink-0 font-bold uppercase w-8 ${map[level] ?? 'text-gray-400'}`}>{level.slice(0, 4)}</span>
}
