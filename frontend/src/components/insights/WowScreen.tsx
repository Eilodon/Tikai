"use client"
import { useRouter } from "next/navigation"
import { InsightSnapshotResponse, formatVND, formatPct } from "@/lib/api"

const LEAK_REASON_VI: Record<string, string> = {
  voucher_high: "Chi phí voucher quá cao so với doanh thu",
  affiliate_high: "Hoa hồng affiliate ăn vào margin",
  cogs_missing: "Chưa có giá vốn — không tính được margin",
  refund_spike: "Tỷ lệ hoàn hàng bất thường",
  commission_exceeds_margin: "Hoa hồng vượt quá margin thực",
}

interface WowScreenProps {
  insight: InsightSnapshotResponse
  isDemo?: boolean
  onContinue?: () => void
}

export function WowScreen({ insight, isDemo = false, onContinue }: WowScreenProps) {
  const router = useRouter()
  const topLeak = insight.top_leaks[0]
  const gmv = parseFloat(insight.gmv_total)
  const nr = parseFloat(insight.net_revenue)
  const marginRatio = gmv > 0 ? nr / gmv : 0
  const isLowMargin = marginRatio < 0.10

  function handleContinue() {
    if (onContinue) {
      onContinue()
    } else {
      router.push("/overview")
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl border shadow-sm max-w-sm w-full p-8 space-y-6">
        {isDemo && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-700 text-center">
            📊 Shop demo — dữ liệu minh họa
          </div>
        )}

        <div className="text-center space-y-1">
          <p className="text-sm text-gray-500">
            {insight.period_start} — {insight.period_end}
          </p>
          <p className="text-sm text-gray-500 mt-1">Kỳ này bạn bán được</p>
          <p className="text-3xl font-bold">{formatVND(insight.gmv_total)}</p>
          <p className="text-sm text-gray-400">{insight.total_orders.toLocaleString()} đơn hàng</p>
        </div>

        <div className={`rounded-xl p-5 text-center ${
          isLowMargin
            ? "bg-red-50 border border-red-200"
            : "bg-green-50 border border-green-200"
        }`}>
          <p className="text-sm font-medium text-gray-600 mb-1">Lãi thực sau tất cả phí</p>
          <p className={`text-4xl font-bold ${isLowMargin ? "text-red-700" : "text-green-700"}`}>
            {formatVND(insight.net_revenue)}
          </p>
          <p className="text-sm text-gray-500 mt-1">
            ({formatPct(String(marginRatio))} margin)
          </p>
          {isLowMargin && (
            <p className="text-xs text-red-600 mt-2 font-medium">
              ⚠ Margin thấp — có {insight.top_leaks.length} điểm rò rỉ cần xử lý
            </p>
          )}
        </div>

        {topLeak && parseFloat(topLeak.estimated_loss) > 0 && (
          <div className="bg-gray-50 rounded-xl p-4 space-y-1">
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">
              Đang rò rỉ lớn nhất
            </p>
            <p className="font-semibold text-sm truncate">{topLeak.name}</p>
            <p className="text-red-600 font-bold text-lg">
              −{formatVND(topLeak.estimated_loss)}
            </p>
            <p className="text-xs text-gray-500">
              {LEAK_REASON_VI[topLeak.reason] ?? topLeak.reason}
            </p>
          </div>
        )}

        <button
          onClick={handleContinue}
          className="w-full bg-gray-900 text-white py-3 rounded-xl font-medium hover:bg-gray-700 transition-colors"
        >
          Xem chi tiết & cách fix →
        </button>
      </div>
    </div>
  )
}
