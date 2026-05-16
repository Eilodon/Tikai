"use client"

import React from "react"

interface Props {
  children: React.ReactNode
  fallback?: React.ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

/**
 * Component-level error boundary for catching render errors in subtrees.
 * Wrap around feature sections (charts, data tables) so one broken component
 * doesn't take down the whole page.
 *
 * Usage:
 *   <ErrorBoundary fallback={<p>Không tải được dữ liệu.</p>}>
 *     <SomeFeatureWidget />
 *   </ErrorBoundary>
 *
 * Next.js `error.tsx` handles route-level errors; this handles component-level ones.
 * React Error Boundaries must be class components — functional components cannot
 * implement componentDidCatch.
 */
export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error("[ErrorBoundary]", error, info.componentStack)
  }

  reset = (): void => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }
      return (
        <div className="rounded-xl border border-red-100 bg-red-50 p-4 text-sm text-red-700">
          <p className="font-medium mb-1">Không tải được nội dung này.</p>
          <button
            onClick={this.reset}
            className="text-xs underline hover:no-underline"
          >
            Thử lại
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
