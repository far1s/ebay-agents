/** @type {import('next').NextConfig} */

// On Vercel, the FastAPI backend is served at the same domain under /api/*
// so Next.js rewrites are only needed in local development.
const isVercel = process.env.VERCEL === '1'

const nextConfig = {
  reactStrictMode: true,
  ...(!isVercel && {
    async rewrites() {
      return [
        {
          source: '/api/:path*',
          destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/:path*`,
        },
      ]
    },
  }),
}

module.exports = nextConfig
