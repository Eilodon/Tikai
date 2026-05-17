import type { NextConfig } from "next"

function getApiOrigin() {
  const raw = process.env.NEXT_PUBLIC_API_URL
  if (!raw) return null
  try {
    return new URL(raw).origin
  } catch {
    return null
  }
}

const nextConfig: NextConfig = {
  typedRoutes: true,
  webpack(config, { webpack }) {
    const version = process.env.npm_package_version || "2.0.2"
    config.plugins.push(
      new webpack.DefinePlugin({
        "self.__APP_VERSION__": JSON.stringify(`tikai-v${version}`),
      })
    )
    return config
  },
  // F-3-05: Security headers for a financial SaaS app
  async headers() {
    const apiOrigin = getApiOrigin()
    const connectSrc = [
      "'self'",
      "https://*.supabase.co",
      "wss://*.supabase.co",
      ...(apiOrigin ? [apiOrigin] : []),
    ]
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options",        value: "DENY" },
          { key: "X-Content-Type-Options",  value: "nosniff" },
          { key: "Referrer-Policy",         value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy",      value: "camera=(), microphone=(), geolocation=()" },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline'",  // Next.js requires unsafe-inline for hydration
              "style-src 'self' 'unsafe-inline'",   // Tailwind inline styles
              "img-src 'self' data: blob:",
              "font-src 'self'",
              `connect-src ${connectSrc.join(" ")}`,
              "frame-ancestors 'none'",
            ].join("; "),
          },
        ],
      },
    ]
  },
}

export default nextConfig
