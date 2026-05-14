import { formatVND, formatPct } from "@/lib/api"
import { cn } from "@/lib/utils"

export function MoneyDisplay({
  value,
  className,
  negative = false,
}: {
  value: string | null | undefined
  className?: string
  negative?: boolean
}) {
  return (
    <span className={cn(negative ? "text-red-600" : "", className)}>
      {formatVND(value)}
    </span>
  )
}

export function PctDisplay({
  value,
  className,
  warningThreshold,
}: {
  value: string | null | undefined
  className?: string
  warningThreshold?: number
}) {
  const num = value ? parseFloat(value) * 100 : null
  const isWarning = warningThreshold !== undefined && num !== null && num > warningThreshold

  return (
    <span className={cn(isWarning ? "text-red-600 font-medium" : "", className)}>
      {formatPct(value)}
    </span>
  )
}

export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className="bg-white rounded-xl border p-5 animate-pulse space-y-3">
      {[...Array(lines)].map((_, i) => (
        <div
          key={i}
          className={cn(
            "h-4 bg-gray-200 rounded",
            i === 0 ? "w-3/4" : i === lines - 1 ? "w-1/2" : "w-full"
          )}
        />
      ))}
    </div>
  )
}

export function EmptyState({
  message,
  action,
  actionLabel,
}: {
  message: string
  action?: () => void
  actionLabel?: string
}) {
  return (
    <div className="bg-white rounded-xl border p-8 text-center">
      <p className="text-gray-400 text-sm">{message}</p>
      {action && actionLabel && (
        <button
          onClick={action}
          className="text-blue-600 text-sm mt-3 hover:underline"
        >
          {actionLabel}
        </button>
      )}
    </div>
  )
}
