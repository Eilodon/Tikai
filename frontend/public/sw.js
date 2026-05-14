/**
 * Tikai PWA Service Worker — minimal vanilla offline support.
 * No external dependencies (avoids next-pwa bloat).
 *
 * Strategy:
 * - HTML pages (navigation requests): network-first → cache fallback → offline page
 * - Static assets (JS, CSS, fonts, images): cache-first → network fallback
 * - API calls (/v1/*): network-only (never cache — financial data must be fresh)
 *
 * VERSIONING — FIX v2.0.1:
 * CACHE_VERSION must be bumped on every production deploy so that PWA users
 * receive fresh JS/CSS instead of stale cached assets.
 *
 * HOW TO AUTO-BUMP (recommended):
 *   In next.config.ts, add to publicRuntimeConfig or NEXT_PUBLIC_ env vars:
 *     NEXT_PUBLIC_APP_VERSION=2.0.1  (set in CI/CD, e.g. from git tag)
 *   Then replace the const below with:
 *     const CACHE_VERSION = self.__APP_VERSION__ || "tikai-v2.0.1"
 *   And in next.config.ts:
 *     webpack: (config) => {
 *       config.plugins.push(new webpack.DefinePlugin({
 *         'self.__APP_VERSION__': JSON.stringify(`tikai-v${process.env.NEXT_PUBLIC_APP_VERSION}`)
 *       }))
 *       return config
 *     }
 *
 * MANUAL BUMP (current approach):
 *   Update the version string below on every deploy. Include it in the deploy checklist.
 *   Format: "tikai-v{MAJOR}.{MINOR}.{PATCH}"
 */

const CACHE_VERSION = "tikai-v2.0.1"   // ← bump this on every deploy
const STATIC_CACHE = `${CACHE_VERSION}-static`
const PAGES_CACHE = `${CACHE_VERSION}-pages`

// Pages to pre-cache for offline use
const OFFLINE_PAGES = ["/overview", "/import", "/offline"]

// Install: pre-cache offline fallback page
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(PAGES_CACHE)
      .then((cache) => cache.addAll(["/offline"]).catch(() => null))
      .then(() => self.skipWaiting())
  )
})

// Activate: clean old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => !k.startsWith(CACHE_VERSION))
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  )
})

// Fetch: route by request type
self.addEventListener("fetch", (event) => {
  const { request } = event
  const url = new URL(request.url)

  // Only handle GET requests from same origin
  if (request.method !== "GET" || url.origin !== location.origin) {
    return
  }

  // CRITICAL: API calls must never be cached — financial data
  if (url.pathname.startsWith("/v1/") || url.pathname.startsWith("/api/")) {
    return // let browser handle normally (network-only)
  }

  // HTML page navigation: network-first → cache fallback → offline page
  if (request.mode === "navigate" || request.headers.get("accept")?.includes("text/html")) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Cache successful HTML responses
          if (response.ok) {
            const clone = response.clone()
            caches.open(PAGES_CACHE).then((cache) => cache.put(request, clone))
          }
          return response
        })
        .catch(() =>
          caches.match(request).then(
            (cached) => cached || caches.match("/offline")
          )
        )
    )
    return
  }

  // Static assets: cache-first → network fallback
  if (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.match(/\.(js|css|woff2?|ttf|png|jpg|svg|webp|ico)$/)
  ) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached
        return fetch(request).then((response) => {
          if (response.ok) {
            const clone = response.clone()
            caches.open(STATIC_CACHE).then((cache) => cache.put(request, clone))
          }
          return response
        })
      })
    )
    return
  }

  // Default: try network, fall back to cache
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  )
})
