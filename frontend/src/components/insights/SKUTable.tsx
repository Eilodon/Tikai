"use client"
import { useState, useRef } from "react"
import { InsightSnapshotResponse, SKUSummaryItem, formatVND, formatPct } from "@/lib/api"
import { WhatIfPanel } from "./WhatIfPanel"

const HEALTH_CONFIG = {
  healthy: { icon: "🟢", label: "Tốt" },
  warning: { icon: "🟡", label: "Cần tối ưu" },
  critical: { icon: "🔴", label: "Cần xử lý" },
}

function HealthCell({ sku }: { sku: SKUSummaryItem }) {
  const [open, setOpen] = useState(false)
  const cfg = HEALTH_CONFIG[sku.health_status] ?? HEALTH_CONFIG.healthy

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        title={cfg.label}
        className="text-base hover:scale-110 transition-transform cursor-pointer"
      >
        {cfg.icon}
      </button>
      {open && sku.health_reasons.length > 0 && (
        <div
          className="absolute left-0 top-full mt-1 z-20 bg-white border rounded-xl shadow-lg p-3 w-56 text-xs"
          onMouseLeave={() => setOpen(false)}
        >
          <p className="font-semibold mb-1.5 text-gray-800">{cfg.label}</p>
          <ul className="space-y-1">
            {sku.health_reasons.map((r, i) => (
              <li key={i} className="text-gray-600 flex items-start gap-1">
                <span className="mt-0.5 flex-shrink-0">•</span>{r}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// Inline COGS input shown in the Margin cell when margin_pct is null
function InlineCOGSInput({
  sku,
  onSave,
  saving,
}: {
  sku: SKUSummaryItem
  onSave: (skuId: string, skuName: string, cogs: string) => Promise<void>
  saving: boolean
}) {
  const [val, setVal] = useState("")
  const [saved, setSaved] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  async function commit() {
    const trimmed = val.trim()
    if (!trimmed || parseFloat(trimmed) <= 0) return
    await onSave(sku.sku_id, sku.sku_name, trimmed)
    setSaved(true)
  }

  if (saved) return <span className="text-xs text-green-600 font-medium">✓</span>
  if (saving) return <span className="text-xs text-gray-400">...</span>

  return (
    <input
      ref={inputRef}
      type="number"
      min="0"
      step="1000"
      placeholder="Giá vốn"
      value={val}
      onChange={(e) => setVal(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); commit() } }}
      className="w-24 text-right border border-dashed border-gray-300 rounded px-1.5 py-0.5
                 text-xs focus:outline-none focus:ring-1 focus:ring-blue-400 focus:border-blue-400
                 [appearance:textfield] bg-white placeholder:text-gray-300"
      title={`Nhập giá vốn cho ${sku.sku_name}`}
    />
  )
}

type FilterTab = "all" | "critical" | "warning"

export function SKUTable({
  insight,
  onSaveCogs,
  savingCogsId,
}: {
  insight: InsightSnapshotResponse
  onSaveCogs?: (skuId: string, skuName: string, cogs: string) => Promise<void>
  savingCogsId?: string
}) {
  const [filter, setFilter] = useState<FilterTab>("all")
  const [whatIfSku, setWhatIfSku] = useState<SKUSummaryItem | null>(null)

  if (!insight.top_skus || insight.top_skus.length === 0) return null

  const criticalCount = insight.top_skus.filter((s) => s.health_status === "critical").length
  const warningCount = insight.top_skus.filter((s) => s.health_status === "warning").length

  const filtered = insight.top_skus.slice(0, 10).filter((s) => {
    if (filter === "critical") return s.health_status === "critical"
    if (filter === "warning")  return s.health_status === "warning"
    return true
  })

  return (
    <>
      <div className="bg-white rounded-xl border overflow-hidden">
        <div className="px-5 py-4 border-b flex items-center justify-between gap-3 flex-wrap">
          <h2 className="font-semibold text-sm">Top SKUs theo GMV</h2>
          <div className="flex gap-1.5 text-xs">
            <button
              onClick={() => setFilter("all")}
              className={`px-2.5 py-1 rounded-full border transition-colors ${
                filter === "all" ? "bg-gray-900 text-white border-gray-900" : "border-gray-200 text-gray-600 hover:bg-gray-50"
              }`}
            >
              Tất cả
            </button>
            {criticalCount > 0 && (
              <button
                onClick={() => setFilter("critical")}
                className={`px-2.5 py-1 rounded-full border transition-colors ${
                  filter === "critical" ? "bg-red-600 text-white border-red-600" : "border-red-200 text-red-600 hover:bg-red-50"
                }`}
              >
                🔴 Cần xử lý ({criticalCount})
              </button>
            )}
            {warningCount > 0 && (
              <button
                onClick={() => setFilter("warning")}
                className={`px-2.5 py-1 rounded-full border transition-colors ${
                  filter === "warning" ? "bg-amber-500 text-white border-amber-500" : "border-amber-200 text-amber-600 hover:bg-amber-50"
                }`}
              >
                🟡 Cần tối ưu ({warningCount})
              </button>
            )}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
                <th className="text-center px-3 py-3 font-medium w-10"></th>
                <th className="text-left px-3 py-3 font-medium">#</th>
                <th className="text-left px-3 py-3 font-medium">SKU</th>
                <th className="text-right px-3 py-3 font-medium">GMV</th>
                <th className="text-right px-3 py-3 font-medium">Net Revenue</th>
                <th className="text-right px-3 py-3 font-medium">Margin</th>
                <th className="text-right px-3 py-3 font-medium">Hoàn</th>
                <th className="text-right px-3 py-3 font-medium w-20"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((sku) => (
                <tr key={sku.sku_id} className="border-t hover:bg-gray-50 transition-colors">
                  <td className="px-3 py-3 text-center">
                    <HealthCell sku={sku} />
                  </td>
                  <td className="px-3 py-3 text-gray-400 text-xs">{sku.gmv_rank}</td>
                  <td className="px-3 py-3">
                    <p className="font-medium text-sm truncate max-w-[140px]">{sku.sku_name}</p>
                    <p className="text-xs text-gray-400">{sku.sku_id}</p>
                  </td>
                  <td className="px-3 py-3 text-right">{formatVND(sku.gmv)}</td>
                  <td className="px-3 py-3 text-right">{formatVND(sku.net_revenue)}</td>
                  <td className="px-3 py-3 text-right">
                    {sku.margin_pct ? (
                      <span className={parseFloat(sku.margin_pct) < 0 ? "text-red-600 font-medium" : "text-green-700"}>
                        {formatPct(sku.margin_pct)}
                      </span>
                    ) : onSaveCogs ? (
                      <InlineCOGSInput
                        sku={sku}
                        onSave={onSaveCogs}
                        saving={savingCogsId === sku.sku_id}
                      />
                    ) : (
                      <span className="text-gray-300 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-3 py-3 text-right">
                    <span className={parseFloat(sku.refund_rate) > 0.1 ? "text-red-600" : "text-gray-600"}>
                      {formatPct(sku.refund_rate)}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-right">
                    <button
                      onClick={() => setWhatIfSku(sku)}
                      className="text-xs text-blue-600 hover:underline whitespace-nowrap"
                    >
                      Thử thay đổi
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-5 py-6 text-center text-sm text-gray-400">
                    Không có SKU nào trong bộ lọc này.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {whatIfSku && (
        <WhatIfPanel
          sku={whatIfSku}
          snapshotId={insight.id}
          onClose={() => setWhatIfSku(null)}
        />
      )}
    </>
  )
}
