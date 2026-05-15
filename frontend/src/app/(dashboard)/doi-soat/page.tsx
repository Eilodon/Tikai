"use client"
import { useCallback, useState, useEffect } from "react"
import { useLatestInsight, useReconcile } from "@/hooks/useApi"
import { formatVND, type ReconcileResponse } from "@/lib/api"

function HiddenCostCards({ result }: { result: ReconcileResponse }) {
  const cards = [
    { label: "Phí điều chỉnh vận chuyển", value: result.shipping_adjustments_total, icon: "⚖️" },
    { label: "Phí quản lý hoàn hàng",     value: result.refund_admin_fees_total,    icon: "📦" },
    { label: "Hoa hồng creator mất do hoàn", value: result.non_clawback_commissions, icon: "💸" },
    { label: "TikTok đang giữ (reserve)", value: result.reserve_held,               icon: "🔒" },
  ]
  return (
    <div className="grid grid-cols-2 gap-3">
      {cards.map((c) => (
        <div key={c.label} className="bg-white border rounded-xl p-4">
          <div className="text-xl">{c.icon}</div>
          <p className="text-xs text-gray-500 mt-1">{c.label}</p>
          <p className="font-semibold text-gray-900 mt-1">{formatVND(c.value)}</p>
        </div>
      ))}
    </div>
  )
}

const VERDICT_CONFIG: Record<ReconcileResponse["verdict"], { label: string; color: string; bg: string }> = {
  matched:     { label: "Khớp",            color: "text-green-700",  bg: "bg-green-50 border-green-200" },
  minor_gap:   { label: "Lệch nhẹ",        color: "text-blue-700",   bg: "bg-blue-50 border-blue-200" },
  major_gap:   { label: "Lệch lớn",        color: "text-amber-700",  bg: "bg-amber-50 border-amber-200" },
  investigate: { label: "Cần điều tra",    color: "text-red-700",    bg: "bg-red-50 border-red-200" },
}

function ReconcileResultPanel({ result }: { result: ReconcileResponse }) {
  const v = VERDICT_CONFIG[result.verdict]
  const gapNum = parseFloat(result.gap)
  const isShortfall = gapNum < 0
  const gapPctNum = parseFloat(result.gap_pct)

  return (
    <div className="space-y-5">
      <div className={`rounded-xl p-5 border ${v.bg}`}>
        <div className="flex items-baseline justify-between">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Kết quả đối soát</p>
          <span className={`text-xs font-semibold px-2 py-1 rounded-full ${v.color} bg-white`}>
            {v.label}
          </span>
        </div>
        <div className="grid grid-cols-3 gap-4 mt-4">
          <div>
            <p className="text-xs text-gray-500">Settlement nhận</p>
            <p className="font-bold text-gray-900">{formatVND(result.total_payout)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Theo P&L Tikai</p>
            <p className="font-bold text-gray-900">{formatVND(result.expected_payout)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">{isShortfall ? "Thiếu" : "Thừa"}</p>
            <p className={`font-bold ${isShortfall ? "text-red-700" : "text-green-700"}`}>
              {formatVND(Math.abs(gapNum).toString())}
              <span className="ml-1 text-xs font-normal">({(gapPctNum * 100).toFixed(1)}%)</span>
            </p>
          </div>
        </div>
      </div>

      <div>
        <h2 className="font-semibold text-sm mb-3">Phân loại khoản trừ</h2>
        <HiddenCostCards result={result} />
      </div>

      {result.action_items_vi.length > 0 && (
        <div className="bg-gray-900 text-white rounded-xl p-5 space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
            Cần làm
          </p>
          <ol className="space-y-2">
            {result.action_items_vi.map((item, i) => (
              <li key={i} className="text-sm leading-relaxed flex gap-3">
                <span className="text-gray-400 shrink-0">{i + 1}.</span>
                <span>{item}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {result.high_shipping_adj_skus.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">
            SKU bị điều chỉnh phí vận chuyển nhiều
          </p>
          <p className="text-sm text-amber-900 mt-2">
            {result.high_shipping_adj_skus.slice(0, 5).join(", ")}
            {result.high_shipping_adj_skus.length > 5 && ` +${result.high_shipping_adj_skus.length - 5} SKU khác`}
          </p>
          <p className="text-xs text-amber-700 mt-2">
            Cập nhật cân nặng listing để tránh khấu trừ tự động.
          </p>
        </div>
      )}

      <p className="text-xs text-gray-400 text-center">
        Đã đối soát {result.settlement_rows_parsed} dòng settlement
      </p>
    </div>
  )
}

export default function DoiSoatPage() {
  const { data: insight, isLoading: insightLoading } = useLatestInsight()
  const reconcile = useReconcile()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (reconcile.data) {
      try { localStorage.setItem("tikai_reconciled_settlement", "1") } catch {}
    }
  }, [reconcile.data])

  const handleFile = useCallback(async (file: File) => {
    setError(null)
    if (!insight) return
    try {
      await reconcile.mutateAsync({ file, snapshotId: insight.id })
    } catch (err: any) {
      const code = err?.code
      if (code === "FEATURE_LOCKED") {
        setError("Đối soát settlement cần gói Pro (99k/tháng). Nâng cấp tại /settings/billing.")
      } else if (code === "FILE_TOO_LARGE") {
        setError("File lớn hơn 20MB. Xuất theo từng tháng để nhẹ hơn.")
      } else if (code === "INVALID_FILE_TYPE") {
        setError("Chỉ chấp nhận file CSV hoặc Excel từ TikTok Shop.")
      } else if (code === "EMPTY_SETTLEMENT") {
        setError("Không đọc được dữ liệu. Kiểm tra file có đúng định dạng Settlement Export.")
      } else {
        setError(err?.message ?? "Có lỗi xảy ra. Vui lòng thử lại.")
      }
    }
  }, [insight, reconcile])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  if (insightLoading) {
    return <div className="h-32 bg-gray-100 rounded-xl animate-pulse" />
  }

  if (!insight) {
    return (
      <div className="text-center py-16">
        <p className="text-gray-500 text-sm mb-2">Cần có dữ liệu Order đã import trước.</p>
        <a href="/import" className="text-blue-600 text-sm hover:underline">
          Import order file →
        </a>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold">Đối soát Settlement</h1>
        <p className="text-sm text-gray-500 mt-1">
          Upload file Settlement Export để Tikai so sánh với P&L computed và giải thích từng khoản trừ.
        </p>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-blue-700 mb-1">
          Tikai sẽ đối chiếu với
        </p>
        <p className="text-blue-900">
          P&L kỳ <strong>{insight.period_start} → {insight.period_end}</strong>
          {" — Expected payout "}<strong>{formatVND(insight.net_revenue)}</strong>
        </p>
      </div>

      {!reconcile.data && (
        <label
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          className="block border-2 border-dashed border-gray-300 rounded-xl p-10 text-center cursor-pointer hover:border-blue-400 transition-colors"
        >
          <input
            type="file"
            accept=".csv,.xlsx,.xls"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
          {reconcile.isPending ? (
            <p className="text-gray-500">Đang đối soát...</p>
          ) : (
            <>
              <p className="font-medium">Kéo thả file Settlement vào đây</p>
              <p className="text-sm text-gray-400 mt-1">
                Settlement Export từ TikTok Seller Center · .csv hoặc .xlsx · tối đa 20MB
              </p>
            </>
          )}
        </label>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {reconcile.data && <ReconcileResultPanel result={reconcile.data} />}

      {reconcile.data && (
        <button
          onClick={() => reconcile.reset()}
          className="text-xs text-blue-600 hover:underline"
        >
          ↻ Upload file khác
        </button>
      )}
    </div>
  )
}
