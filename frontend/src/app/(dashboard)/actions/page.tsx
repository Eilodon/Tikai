"use client"
import { useActions, useCompleteAction, useDismissAction } from "@/hooks/useApi"
import { AIActionResponse } from "@/lib/api"

export default function ActionsPage() {
  const { data, isLoading } = useActions()
  const complete = useCompleteAction()
  const dismiss = useDismissAction()

  if (isLoading) return <SkeletonActions />

  const pending = data?.items?.filter((a) => a.status === "pending") ?? []
  const done = data?.items?.filter((a) => a.status === "done") ?? []

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold">Hành động</h1>
        <p className="text-sm text-gray-500 mt-1">
          Tikai gợi ý dựa trên dữ liệu import gần nhất.
        </p>
      </div>

      {/* Pending */}
      {pending.length === 0 ? (
        <div className="bg-white rounded-xl border p-8 text-center text-gray-400">
          <p>Không có hành động nào đang chờ.</p>
          <a href="/import" className="text-blue-600 text-sm mt-2 block hover:underline">
            Import dữ liệu mới để nhận gợi ý →
          </a>
        </div>
      ) : (
        <div className="space-y-3">
          {pending.map((action) => (
            <ActionCard
              key={action.id}
              action={action}
              onComplete={() => complete.mutate(action.id.toString())}
              onDismiss={() => dismiss.mutate(action.id.toString())}
              completing={complete.isPending && complete.variables === action.id.toString()}
            />
          ))}
        </div>
      )}

      {/* Done */}
      {done.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-gray-500 mb-3">Đã hoàn thành ({done.length})</h2>
          <div className="space-y-2">
            {done.map((action) => (
              <div key={action.id} className="bg-white rounded-xl border p-4 opacity-60">
                <div className="flex items-center gap-2">
                  <span className="text-green-600 text-sm">✓</span>
                  <p className="text-sm font-medium">{action.title}</p>
                  {action.is_confirmed_impact && action.confirmed_delta && (
                    <span className="ml-auto text-xs text-green-600 font-medium">
                      +{Number(action.confirmed_delta).toLocaleString("vi-VN")}₫ đã xác nhận
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ActionCard({
  action,
  onComplete,
  onDismiss,
  completing,
}: {
  action: AIActionResponse
  onComplete: () => void
  onDismiss: () => void
  completing: boolean
}) {
  const confidenceConfig = {
    high:   { label: "Chắc chắn", cls: "bg-green-100 text-green-700" },
    medium: { label: "Có thể",    cls: "bg-yellow-100 text-yellow-700" },
    low:    { label: "Chưa chắc", cls: "bg-gray-100 text-gray-500" },
  }[action.confidence] ?? { label: action.confidence, cls: "bg-gray-100 text-gray-500" }

  return (
    <div className="bg-white rounded-xl border p-5 space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <p className="font-semibold text-sm leading-tight">{action.title}</p>
        <span className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${confidenceConfig.cls}`}>
          {confidenceConfig.label}
        </span>
      </div>

      {/* Why */}
      <p className="text-sm text-gray-600">{action.why}</p>

      {/* Do today */}
      <div className="bg-blue-50 border border-blue-100 rounded-lg px-4 py-3">
        <p className="text-xs font-semibold text-blue-700 mb-1 uppercase tracking-wide">Làm ngay hôm nay</p>
        <p className="text-sm text-blue-900">{action.do_today}</p>
      </div>

      {/* Expected impact */}
      {action.expected_impact && (
        <p className="text-xs text-gray-400">Kỳ vọng: {action.expected_impact}</p>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3 pt-1">
        <button
          onClick={onComplete}
          disabled={completing}
          className="flex-1 bg-gray-900 text-white text-sm py-2 rounded-lg font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors"
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

function SkeletonActions() {
  return (
    <div className="space-y-3 animate-pulse">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="bg-white rounded-xl border p-5 space-y-3">
          <div className="h-4 bg-gray-200 rounded w-3/4" />
          <div className="h-3 bg-gray-200 rounded w-full" />
          <div className="h-12 bg-gray-100 rounded-lg" />
          <div className="h-9 bg-gray-200 rounded-lg" />
        </div>
      ))}
    </div>
  )
}
