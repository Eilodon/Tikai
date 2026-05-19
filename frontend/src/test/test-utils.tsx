/**
 * Shared test utilities.
 * renderWithProviders: wraps components with QueryClientProvider
 * so hooks like useActions, useLatestInsight work in tests.
 */
import React from "react"
import { render, type RenderOptions } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

/** Fresh QueryClient per test — avoids cache bleed between tests */
function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,        // don't retry in tests — fail fast
        staleTime: 0,        // always fetch in tests
        gcTime: 0,
      },
    },
  })
}

interface WrapperProps {
  children: React.ReactNode
}

function Wrapper({ children }: WrapperProps) {
  const qc = makeQueryClient()
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

export function renderWithProviders(
  ui: React.ReactElement,
  options?: Omit<RenderOptions, "wrapper">
) {
  return render(ui, { wrapper: Wrapper, ...options })
}

/** Returns a wrapper component for renderHook — each call creates a fresh QueryClient */
export function makeTestWrapper() {
  return function TestWrapper({ children }: WrapperProps) {
    const qc = makeQueryClient()
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  }
}

/** Flush all pending promises and microtasks in tests */
export const flushPromises = () =>
  new Promise((resolve) => setTimeout(resolve, 0))
