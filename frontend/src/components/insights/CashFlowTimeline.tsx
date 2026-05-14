import { InsightSnapshotResponse, formatVND } from "@/lib/api"

function ProgressBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
      <div
        className={`h-3 rounded-full transition-all duration-500 ${color}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

export function CashFlowTimeline({ insight }: { insight: InsightSnapshotResponse }) {
  const has14 = !!insight.cash_in_14d
  const has30 = !!insight.cash_in_30d
  const hasPending = !!insight.cash_pending_total

  if (!has14 && !has30 && !hasPending) return null

  const v14 = parseFloat(insight.cash_in_14d ?? "0")
  const v30 = parseFloat(insight.cash_in_30d ?? "0")
  const vPending = parseFloat(insight.cash_pending_total ?? "0")
  const maxVal = Math.max(v14, v30, vPending, 1)

  return (
    <div className="bg-white rounded-xl border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-sm">Dòng tiền dự báo</h2>
        <span className="text-xs text-gray-400">TikTok giữ 14 ngày sau giao hàng</span>
      </div>

      <div className="space-y-3">
        {has14 && (
          <div className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Về trong 14 ngày tới</span>
              <span className="font-semibold text-blue-700">{formatVND(insight.cash_in_14d)}</span>
            </div>
            <ProgressBar value={v14} max={maxVal} color="bg-blue-500" />
          </div>
        )}

        {has30 && (
          <div className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Về trong 30 ngày tới</span>
              <span className="font-semibold text-indigo-700">{formatVND(insight.cash_in_30d)}</span>
            </div>
            <ProgressBar value={v30} max={maxVal} color="bg-indigo-400" />
          </div>
        )}

        {hasPending && (
          <div className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Tổng đang chờ về</span>
              <span className="font-semibold text-gray-700">{formatVND(insight.cash_pending_total)}</span>
            </div>
            <ProgressBar value={vPending} max={maxVal} color="bg-gray-300" />
          </div>
        )}
      </div>

      <p className="text-xs text-gray-400">
        Dự báo dựa trên đơn đã giao thành công, chưa tính đơn hoàn.
      </p>
    </div>
  )
}
