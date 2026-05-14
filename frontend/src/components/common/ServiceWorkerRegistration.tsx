"use client"
import { useEffect } from "react"

/**
 * Registers the PWA service worker.
 * Mount once in root layout. Silently no-ops in dev/HTTP/unsupported browsers.
 */
export function ServiceWorkerRegistration() {
  useEffect(() => {
    if (
      typeof window === "undefined" ||
      !("serviceWorker" in navigator) ||
      window.location.hostname === "localhost"
    ) {
      // Don't register on localhost — interferes with dev hot-reload
      return
    }

    const register = async () => {
      try {
        const reg = await navigator.serviceWorker.register("/sw.js", {
          scope: "/",
          updateViaCache: "none",
        })
        // Check for updates every hour
        setInterval(() => reg.update().catch(() => {}), 60 * 60 * 1000)
      } catch (err) {
        // Silent failure — SW registration is best-effort
        console.warn("SW registration failed:", err)
      }
    }

    register()
  }, [])

  return null
}
