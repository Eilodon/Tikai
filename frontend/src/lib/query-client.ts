"use client"
import { QueryClient } from "@tanstack/react-query"

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,  // 5 minutes
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

// Centralized query keys — NEVER use string literals in components
export const queryKeys = {
  shop:           () => ["shop"] as const,
  insight:        () => ["insight", "latest"] as const,
  insightById:    (id: string) => ["insight", id] as const,
  actions:        () => ["actions"] as const,
  imports:        () => ["imports"] as const,
  importById:     (id: string) => ["imports", id] as const,
} as const
