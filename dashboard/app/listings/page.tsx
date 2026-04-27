'use client'

import { useEffect, useState, useCallback } from 'react'
import { api, Listing } from '@/lib/api'
import { format } from 'date-fns'

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-900/60 text-green-300',
  sold: 'bg-blue-900/60 text-blue-300',
  ended: 'bg-gray-800 text-gray-400',
  error: 'bg-red-900/60 text-red-300',
}

export default function ListingsPage() {
  const [listings, setListings] = useState<Listing[]>([])
  const [stats, setStats] = useState<Record<string, number>>({})
  const [filter, setFilter] = useState<string>('all')
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    const data = await api.getListings(filter === 'all' ? undefined : filter)
    setListings(data.listings)
    setStats(data.stats)
    setLoading(false)
  }, [filter])

  useEffect(() => {
    setLoading(true)
    refresh()
  }, [refresh])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Listings</h1>
        <p className="text-gray-400 text-sm mt-1">All Etsy listings created by the agents</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {(['active', 'sold', 'ended'] as const).map((s) => (
          <div key={s} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div className="text-xs text-gray-400 capitalize mb-1">{s}</div>
            <div className="text-2xl font-bold text-white">{stats[s] ?? 0}</div>
          </div>
        ))}
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2">
        {['all', 'active', 'sold', 'ended'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors capitalize ${
              filter === f ? 'bg-indigo-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading...</div>
        ) : listings.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No listings yet. Run the pipeline to create your first Etsy listing.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-800/50">
                <th className="text-left px-4 py-3 text-gray-400 font-medium">Title</th>
                <th className="text-left px-4 py-3 text-gray-400 font-medium">Price</th>
                <th className="text-left px-4 py-3 text-gray-400 font-medium">Status</th>
                <th className="text-left px-4 py-3 text-gray-400 font-medium">Listed</th>
                <th className="text-left px-4 py-3 text-gray-400 font-medium">Link</th>
              </tr>
            </thead>
            <tbody>
              {listings.map((listing) => (
                <tr key={listing.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                  <td className="px-4 py-3 text-white max-w-xs truncate" title={listing.title}>
                    {listing.title}
                  </td>
                  <td className="px-4 py-3 text-green-400 font-semibold">${listing.price.toFixed(2)}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[listing.status] ?? STATUS_COLORS.ended}`}>
                      {listing.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {format(new Date(listing.listed_at), 'MMM d, yyyy HH:mm')}
                  </td>
                  <td className="px-4 py-3">
                    {listing.etsy_url ? (
                      <a
                        href={listing.etsy_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-indigo-400 hover:text-indigo-300 text-xs underline"
                      >
                        View on Etsy ↗
                      </a>
                    ) : (
                      <span className="text-gray-600 text-xs">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
