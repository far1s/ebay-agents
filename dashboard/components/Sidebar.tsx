'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import clsx from 'clsx'

const NAV = [
  { href: '/', label: 'Dashboard', icon: '⬛' },
  { href: '/agents', label: 'Agents', icon: '🤖' },
  { href: '/listings', label: 'Listings', icon: '🛒' },
  { href: '/logs', label: 'Logs', icon: '📋' },
  { href: '/settings', label: 'Settings', icon: '⚙️' },
]

export default function Sidebar() {
  const path = usePathname()

  return (
    <aside className="fixed left-0 top-0 h-full w-60 bg-gray-900 border-r border-gray-800 flex flex-col z-10">
      {/* Brand */}
      <div className="px-5 py-5 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🤖</span>
          <div>
            <div className="font-bold text-white text-base leading-tight">EbayAgents</div>
            <div className="text-xs text-gray-500">Automated eBay Sales</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ href, label, icon }) => {
          const active = path === href || (href !== '/' && path.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                active
                  ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-600/30'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
              )}
            >
              <span className="text-base">{icon}</span>
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-gray-800">
        <p className="text-xs text-gray-600">EbayAgents v1.0.0</p>
        <p className="text-xs text-gray-600 mt-0.5">Powered by Claude AI</p>
      </div>
    </aside>
  )
}
