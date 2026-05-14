import { cn } from "@/lib/utils"

type Confidence = "high" | "medium" | "low"

const CONFIG: Record<Confidence, { label: string; cls: string }> = {
  high:   { label: "Chắc chắn", cls: "bg-green-100 text-green-700" },
  medium: { label: "Có thể",    cls: "bg-yellow-100 text-yellow-700" },
  low:    { label: "Chưa chắc", cls: "bg-gray-100 text-gray-500" },
}

export function ConfidenceBadge({
  confidence,
  className,
}: {
  confidence: string
  className?: string
}) {
  const cfg = CONFIG[confidence as Confidence] ?? { label: confidence, cls: "bg-gray-100 text-gray-500" }
  return (
    <span className={cn("text-xs px-2 py-0.5 rounded-full flex-shrink-0", cfg.cls, className)}>
      {cfg.label}
    </span>
  )
}
