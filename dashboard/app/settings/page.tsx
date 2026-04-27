'use client'

import { useEffect, useState } from 'react'
import { api, ScheduleSettings, HealthCheck } from '@/lib/api'

export default function SettingsPage() {
  const [schedule, setSchedule] = useState<ScheduleSettings>({ enabled: true, cron: '0 9 * * *', timezone: 'UTC' })
  const [health, setHealth] = useState<HealthCheck | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    Promise.all([api.getSchedule(), api.health()]).then(([s, h]) => {
      setSchedule(s)
      setHealth(h)
    }).catch(console.error)
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.updateSchedule(schedule)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-gray-400 text-sm mt-1">Configure schedule and API connections</p>
      </div>

      {/* API Status */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-base font-semibold text-white mb-4">API Key Status</h2>
        {health ? (
          <div className="space-y-3">
            {(
              [
                { key: 'anthropic', label: 'Anthropic (Claude AI)' },
                { key: 'etsy', label: 'Etsy API Key' },
                { key: 'etsy_shop', label: 'Etsy Shop ID' },
                { key: 'telegram', label: 'Telegram Bot' },
                { key: 'supabase', label: 'Supabase Database' },
              ] as const
            ).map(({ key, label }) => {
              const val = health[key as keyof HealthCheck]
              const ok = val === 'ok'
              return (
                <div key={key} className="flex items-center justify-between">
                  <span className="text-gray-300 text-sm">{label}</span>
                  <span
                    className={`flex items-center gap-1.5 text-sm font-medium ${ok ? 'text-green-400' : 'text-red-400'}`}
                  >
                    <span className={`w-2 h-2 rounded-full ${ok ? 'bg-green-400' : 'bg-red-400'}`} />
                    {ok ? 'Connected' : val}
                  </span>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-6 bg-gray-800 rounded animate-pulse" />
            ))}
          </div>
        )}
      </div>

      {/* Schedule settings */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-base font-semibold text-white mb-4">Cron Schedule</h2>

        <div className="space-y-4">
          <label className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-gray-200">Enable automatic runs</div>
              <div className="text-xs text-gray-500 mt-0.5">Run the pipeline automatically on schedule</div>
            </div>
            <button
              onClick={() => setSchedule((s) => ({ ...s, enabled: !s.enabled }))}
              className={`relative inline-flex h-6 w-11 shrink-0 rounded-full border-2 border-transparent transition-colors ${
                schedule.enabled ? 'bg-indigo-600' : 'bg-gray-700'
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
                  schedule.enabled ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </label>

          <div>
            <label className="block text-sm font-medium text-gray-200 mb-1">Cron Expression</label>
            <input
              type="text"
              value={schedule.cron}
              onChange={(e) => setSchedule((s) => ({ ...s, cron: e.target.value }))}
              className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg px-3 py-2.5 focus:outline-none focus:border-indigo-500 font-mono"
              placeholder="0 9 * * *"
            />
            <p className="text-xs text-gray-500 mt-1">
              Default: <code className="text-gray-400">0 9 * * *</code> = daily at 09:00 UTC
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-200 mb-1">Timezone</label>
            <select
              value={schedule.timezone}
              onChange={(e) => setSchedule((s) => ({ ...s, timezone: e.target.value }))}
              className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg px-3 py-2.5 focus:outline-none focus:border-indigo-500"
            >
              <option value="UTC">UTC</option>
              <option value="America/New_York">America/New_York (ET)</option>
              <option value="America/Los_Angeles">America/Los_Angeles (PT)</option>
              <option value="Europe/London">Europe/London (GMT/BST)</option>
              <option value="Europe/Paris">Europe/Paris (CET)</option>
              <option value="Asia/Dubai">Asia/Dubai (GST)</option>
            </select>
          </div>

          <button
            onClick={handleSave}
            disabled={saving}
            className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 text-white font-semibold rounded-lg transition-colors text-sm"
          >
            {saving ? 'Saving...' : saved ? '✓ Saved!' : 'Save Settings'}
          </button>
        </div>
      </div>

      {/* Etsy API info */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-base font-semibold text-white mb-2">Etsy API</h2>
        <p className="text-gray-400 text-sm mb-3">
          Get your free API key from{' '}
          <span className="text-indigo-400">developers.etsy.com</span>{' '}
          and complete the OAuth flow to obtain an access token.
        </p>
        <div className="bg-gray-800 rounded-lg p-3 text-xs font-mono text-gray-300 space-y-1">
          <div><span className="text-gray-500">ETSY_API_KEY</span>=your_api_key</div>
          <div><span className="text-gray-500">ETSY_SHOP_ID</span>=your_shop_id</div>
          <div><span className="text-gray-500">ETSY_ACCESS_TOKEN</span>=your_oauth_token</div>
        </div>
      </div>

      {/* Telegram info */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-base font-semibold text-white mb-2">Telegram Approval</h2>
        <p className="text-gray-400 text-sm mb-3">
          The system requires your approval via Telegram before listing any product on Etsy.
          Configure your bot token and chat ID in the <code className="text-indigo-400">.env</code> file.
        </p>
        <div className="bg-gray-800 rounded-lg p-3 text-xs font-mono text-gray-300 space-y-1">
          <div><span className="text-gray-500">TELEGRAM_BOT_TOKEN</span>=your_bot_token</div>
          <div><span className="text-gray-500">TELEGRAM_CHAT_ID</span>=your_chat_id</div>
        </div>
        <p className="text-xs text-gray-500 mt-2">
          Get your chat ID by messaging <span className="text-indigo-400">@userinfobot</span> on Telegram.
        </p>
      </div>
    </div>
  )
}
