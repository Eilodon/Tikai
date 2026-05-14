import { InsightSnapshotResponse, formatVND, formatPct } from "@/lib/api"

export function PLSummary({ insight }: { insight: InsightSnapshotResponse }) {
  return (
    <div className="bg-white rounded-xl border p-5">
      {insight.is_net_revenue_mode && (
        <div className="mb-4 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-800">
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
    </div>
  )
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
