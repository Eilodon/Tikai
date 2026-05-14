"use client"
import { InsightSnapshotResponse, CreatorSummaryItem, formatVND, formatROI } from "@/lib/api"

const PERF_CONFIG = {
  star:        { icon: "🌟", label: "Đang sinh lãi tốt", bg: "bg-green-50",  border: "border-green-200", badge: "bg-green-100 text-green-700" },
  break_even:  { icon: "⚖️",  label: "Hoà vốn",          bg: "bg-gray-50",   border: "border-gray-200",  badge: "bg-gray-100 text-gray-600"   },
  losing:      { icon: "🔴", label: "Đang lỗ",           bg: "bg-red-50",    border: "border-red-200",   badge: "bg-red-100 text-red-700"     },
}

function CreatorCard({ creator }: { creator: CreatorSummaryItem }) {
  const cfg = PERF_CONFIG[creator.performance_label] ?? PERF_CONFIG.break_even
  const eff = creator.revenue_efficiency ? parseFloat(creator.revenue_efficiency) : null
  const isLosing = creator.performance_label === "losing"

  return (
    <div className={`rounded-xl border p-4 ${cfg.bg} ${cfg.border}`}>
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-lg flex-shrink-0">{cfg.icon}</span>
          <div className="min-w-0">
            <p className="font-semibold text-sm truncate">{creator.creator_name}</p>
            <p className="text-xs text-gray-400 font-mono truncate">{creator.creator_id}</p>
          </div>
        </div>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap flex-shrink-0 ${cfg.badge}`}>
          {cfg.label}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm mb-3">
        <div>
          <p className="text-xs text-gray-500">GMV</p>
          <p className="font-medium">{formatVND(creator.attributed_gmv)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Hoa hồng</p>
          <p className="font-medium">{formatVND(creator.total_commission)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Net Revenue</p>
          <p className={`font-medium ${isLosing ? "text-red-600" : "text-green-700"}`}>
            {formatVND(creator.attributed_net_revenue)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Hiệu quả</p>
          <p className={`font-medium ${eff !== null && eff < 1 ? "text-red-600" : ""}`}>
            {eff !== null ? formatROI(creator.revenue_efficiency) : "—"}
          </p>
        </div>
      </div>

      {isLosing && creator.suggested_max_commission_rate && (
        <div className="text-xs bg-red-100 text-red-800 rounded-lg px-3 py-2">
          Hoa hồng tối đa đề xuất:{" "}
          <strong>{(parseFloat(creator.suggested_max_commission_rate) * 100).toFixed(1)}%</strong>
          {" "}để vẫn có lãi
        </div>
      )}
      {creator.performance_label === "star" && (
        <div className="text-xs bg-green-100 text-green-800 rounded-lg px-3 py-2">
          Creator này đang tạo ra{" "}
          <strong>{eff ? formatROI(creator.revenue_efficiency) : "—"}</strong>
          {" "}net revenue so với chi phí hoa hồng
        </div>
      )}
    </div>
  )
}

export function CreatorTable({ insight }: { insight: InsightSnapshotResponse }) {
  if (!insight.top_creators || insight.top_creators.length === 0) return null

  const creators = insight.top_creators.slice(0, 8)
  const starCount = creators.filter((c) => c.performance_label === "star").length
  const losingCount = creators.filter((c) => c.performance_label === "losing").length

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-sm">Creators ({creators.length})</h2>
        <div className="flex gap-2 text-xs text-gray-500">
          {starCount > 0 && <span className="text-green-600">🌟 {starCount} tốt</span>}
          {losingCount > 0 && <span className="text-red-600">🔴 {losingCount} lỗ</span>}
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {creators.map((c) => (
          <CreatorCard key={c.creator_id} creator={c} />
        ))}
      </div>
    </div>
  )
}
