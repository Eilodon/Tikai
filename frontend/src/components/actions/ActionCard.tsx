"use client"
import { AIActionResponse } from "@/lib/api"
import { ConfidenceBadge } from "./ConfidenceBadge"

interface ActionCardProps {
  action: AIActionResponse
  onComplete: () => void
  onDismiss: () => void
  completing?: boolean
}

export function ActionCard({
  action,
  onComplete,
  onDismiss,
  completing = false,
}: ActionCardProps) {
  return (
    <div className="bg-white rounded-xl border p-5 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <p className="font-semibold text-sm leading-tight">{action.title}</p>
        <ConfidenceBadge confidence={action.confidence} />
      </div>

      <p className="text-sm text-gray-600">{action.why}</p>

      <div className="bg-blue-50 border border-blue-100 rounded-lg px-4 py-3">
        <p className="text-xs font-semibold text-blue-700 mb-1 uppercase tracking-wide">
          Làm ngay hôm nay
        </p>
        <p className="text-sm text-blue-900">{action.do_today}</p>
      </div>

      {action.expected_impact && (
        <p className="text-xs text-gray-400">Kỳ vọng: {action.expected_impact}</p>
      )}

      <div className="flex items-center gap-3 pt-1">
        <button
          onClick={onComplete}
          disabled={completing}
          className="flex-1 bg-gray-900 text-white text-sm py-2 rounded-lg font-medium
                     hover:bg-gray-700 disabled:opacity-50 transition-colors"
        >
          {completing ? "Đang lưu..." : "✓ Đã làm"}
        </button>
        <button
          onClick={onDismiss}
          className="text-sm text-gray-400 hover:text-gray-600 transition-colors px-2"
        >
          Bỏ qua
        </button>
      </div>
    </div>
  )
}
