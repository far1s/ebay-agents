'use client'

import { useEffect, useState, useCallback } from 'react'
import { api, LogEntry } from '@/lib/api'
import { format } from 'date-fns'

const AGENTS = ['', 'market_agent', 'design_agent', 'telegram_agent', 'listing_agent', 'boss_agent']
const LEVELS = ['', 'info', 'warning', 'error', 'debug']

const LEVEL_STYLES: Record<string, string> = {
  info: 'text-blue-400',
  warning: 'text-yellow-400',
  error: 'text-red-400',
  debug: 'text-gray-600',
}
const LEVEL_ROW: Record<string, string> = {
  error: 'bg-red-950/20',
  warning: 'bg-yellow-950/10',
}

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [agentFilter, setAgentFilter] = useState('')
  const [levelFilter, setLevelFilter] = useState('')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const data = await api.getLogs({
        agent_name: agentFilter || undefined,
        level: levelFilter || undefined,
        limit: 200,
      })
      setLogs(data.logs)
    } finally {
      setLoading(false)
    }
  }, [agentFilter, levelFilter])

  useEffect(() => {
    setLoading(true)
    refresh()
  }, [refresh])

  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(refresh, 3000)
    return () => clearInterval(interval)
  }, [autoRefresh, refresh])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Logs</h1>
          <p className="text-gray-400 text-sm mt-1">Full agent log stream</p>
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
            className="accent-indigo-500"
          />
          Auto-refresh
        </label>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <select
          value={agentFilter}
          onChange={(e) => setAgentFilter(e.target.value)}
          className="bg-gray-800 border border-gray-700 text-gray-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500"
        >
          <option value="">All agents</option>
          {AGENTS.filter(Boolean).map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>

        <select
          value={levelFilter}
          onChange={(e) => setLevelFilter(e.target.value)}
          className="bg-gray-800 border border-gray-700 text-gray-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500"
        >
          <option value="">All levels</option>
          {LEVELS.filter(Boolean).map((l) => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>

        <span className="self-center text-xs text-gray-500">{logs.length} entries</span>
      </div>

      {/* Log table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading logs...</div>
        ) : logs.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No logs match the current filters</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-gray-800 bg-gray-800/40">
                  <th className="text-left px-4 py-2.5 text-gray-400 font-medium whitespace-nowrap">Timestamp</th>
                  <th className="text-left px-4 py-2.5 text-gray-400 font-medium">Level</th>
                  <th className="text-left px-4 py-2.5 text-gray-400 font-medium">Agent</th>
                  <th className="text-left px-4 py-2.5 text-gray-400 font-medium">Run ID</th>
                  <th className="text-left px-4 py-2.5 text-gray-400 font-medium">Message</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr
                    key={log.id}
                    className={`border-b border-gray-800/40 hover:bg-gray-800/30 ${LEVEL_ROW[log.level] ?? ''}`}
                  >
                    <td className="px-4 py-2 text-gray-500 whitespace-nowrap">
                      {format(new Date(log.timestamp), 'MM/dd HH:mm:ss')}
                    </td>
                    <td className={`px-4 py-2 font-bold uppercase ${LEVEL_STYLES[log.level] ?? 'text-gray-400'}`}>
                      {log.level}
                    </td>
                    <td className="px-4 py-2 text-gray-400 whitespace-nowrap">{log.agent_name}</td>
                    <td className="px-4 py-2 text-gray-600 whitespace-nowrap max-w-24 truncate">
                      {log.run_id?.slice(0, 14) ?? '—'}
                    </td>
                    <td className={`px-4 py-2 max-w-xl ${log.level === 'error' ? 'text-red-300' : log.level === 'warning' ? 'text-yellow-300' : 'text-gray-300'}`}>
                      {log.message}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
