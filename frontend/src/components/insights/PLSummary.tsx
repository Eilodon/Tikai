import { InsightSnapshotResponse, formatVND, formatPct } from "@/lib/api"

interface FeeConfigInfo {
  version: string
  verified_date: string
  effective_to: string | null
  is_stale: boolean
}

export function PLSummary({
  insight,
  feeConfig,
}: {
  insight: InsightSnapshotResponse
  feeConfig?: FeeConfigInfo | null
}) {
  const cogsPct = parseFloat(insight.cogs_coverage_pct)
  const discrepancyCount = insight.fee_discrepancy_notes?.length ?? 0
  const feeEstimationPct = insight.total_orders > 0
    ? Math.max(0, 1 - discrepancyCount / insight.total_orders)
    : 1

  // confidence = cogs_coverage * 0.5 + import_success(1.0) * 0.3 + fee_accuracy * 0.2
  const confidenceScore = Math.round((cogsPct * 0.5 + 1.0 * 0.3 + feeEstimationPct * 0.2) * 100)
  const needsVerify = discrepancyCount

  return (
    <div className="bg-white rounded-xl border p-5 space-y-4">
      {insight.is_net_revenue_mode && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-800">
          ⚠️ Chưa có giá vốn — đang hiển thị Net Revenue.{" "}
          <a href="/settings" className="underline font-medium">Nhập giá vốn →</a>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <Stat label="GMV" value={formatVND(insight.gmv_total)} />
        <Stat
          label="Net Revenue"
          value={formatVND(insight.net_revenue)}
          valueClass="text-green-700"
        />
        <Stat label="Đơn hàng" value={insight.total_orders.toLocaleString("vi-VN")} />
        <Stat
          label="Tỉ lệ hoàn"
          value={formatPct(insight.refund_rate)}
          valueClass={parseFloat(insight.refund_rate) > 0.1 ? "text-red-600" : ""}
        />
        {insight.cash_in_14d && (
          <Stat
            label="Tiền về 14 ngày"
            value={formatVND(insight.cash_in_14d)}
            valueClass="text-blue-700"
          />
        )}
      </div>

      {/* Gap #4: Confidence score badge */}
      <div className="flex flex-wrap gap-2 pt-1 border-t border-gray-100">
        <span
          className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full font-medium ${
            confidenceScore >= 80
              ? "bg-green-100 text-green-700"
              : confidenceScore >= 60
              ? "bg-amber-100 text-amber-700"
              : "bg-red-100 text-red-600"
          }`}
          title={
            needsVerify > 0
              ? `${needsVerify} đơn có phí ước tính (không parse được từ CSV)`
              : "Tất cả phí đã được xác nhận từ dữ liệu CSV"
          }
        >
          🎯 Độ tin cậy: {confidenceScore}%
          {needsVerify > 0 && ` · ${needsVerify} đơn cần verify`}
        </span>

        {/* Gap #1: Fee policy version badge */}
        {feeConfig && (
          <span
            className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full font-medium ${
              feeConfig.is_stale
                ? "bg-amber-100 text-amber-700"
                : "bg-gray-100 text-gray-600"
            }`}
            title={
              feeConfig.is_stale
                ? `Fee policy hết hiệu lực từ ${feeConfig.effective_to}. Cần cập nhật.`
                : `Xác minh ngày ${feeConfig.verified_date}`
            }
          >
            📋 Phí: {feeConfig.version}
            {feeConfig.is_stale ? " ⚠ Cần cập nhật" : ` · Xác minh ${formatDate(feeConfig.verified_date)}`}
          </span>
        )}
      </div>
    </div>
  )
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso)
    return `${d.getDate().toString().padStart(2, "0")}/${(d.getMonth() + 1).toString().padStart(2, "0")}`
  } catch {
    return iso
  }
}

function Stat({
  label,
  value,
  valueClass = "",
}: {
  label: string
  value: string
  valueClass?: string
}) {
  return (
    <div>
      <p className="text-xs text-gray-500 mb-0.5">{label}</p>
      <p className={`text-xl font-semibold ${valueClass}`}>{value}</p>
    </div>
  )
}
