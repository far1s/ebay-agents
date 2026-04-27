import type { Metadata } from 'next'
import './globals.css'
import Sidebar from '@/components/Sidebar'

export const metadata: Metadata = {
  title: 'EtsyAgents — Dashboard',
  description: 'Automated Etsy digital product sales system',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-gray-950 text-gray-100 min-h-screen">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 ml-60 p-6 overflow-auto">
            {children}
          </main>
        </div>
      </body>
    </html>
  )
}
