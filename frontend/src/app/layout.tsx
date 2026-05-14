import type { Metadata } from "next"
import { Geist } from "next/font/google"
import "./globals.css"
import { Providers } from "./providers"
import { ServiceWorkerRegistration } from "@/components/common/ServiceWorkerRegistration"

const geist = Geist({ subsets: ["latin"] })

// PWA metadata
export const viewport = {
  themeColor: '#FF3B5C',
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
}

export const metadata: Metadata = {
  title: "Tikai — TikTok Shop Analytics",
  description: "Biến số đúng thành hành động đúng cho TikTok Shop seller",
  manifest: "/manifest.json",  // v0.5.2: PWA manifest
  icons: {
    icon: [
      { url: "/favicon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: "/icon-192.png",
  },
  appleWebApp: {
    capable: true,
    title: "Tikai",
    statusBarStyle: "default",
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="vi">
      <body className={geist.className}>
        <Providers>{children}</Providers>
        <ServiceWorkerRegistration />
      </body>
    </html>
  )
}
