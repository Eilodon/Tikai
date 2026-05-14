"use client"
import { useState } from "react"
import { useLatestInsight } from "@/hooks/useApi"
import { toolsApi, CampaignSKUInput, CampaignSimulateResponse, formatVND, formatPct } from "@/lib/api"
import { getAuthToken } from "@/lib/supabase"

export default function CampaignCheckPage() {
  const { data: insight, isLoading } = useLatestInsight()
  const [selectedSkus, setSelectedSkus] = useState<Record<string, CampaignSKUInput>>({})
  const [result, setResult] = useState<CampaignSimulateResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (isLoading) return <div className="animate-pulse space-y-3"><div className="h-32 bg-gray-100 rounded-xl" /></div>
  if (!insight) return (
    <div className="text-center py-16 text-gray-500 text-sm">
      Chưa có dữ liệu. <a href="/import" className="text-blue-600 underline">Import trước →</a>
    </div>
  )

  const topSkus = insight.top_skus.slice(0, 20)

  function toggle(skuId: string, skuName: string) {
    setSelectedSkus((prev) => {
      if (prev[skuId]) {
        const next = { ...prev }
        delete next[skuId]
        return next
      }
      return { ...prev, [skuId]: { sku_id: skuId, planned_units: 100 } }
    })
    setResult(null)
  }

  function updateEntry(skuId: string, field: keyof CampaignSKUInput, value: string | number) {
    setSelectedSkus((prev) => ({
      ...prev,
      [skuId]: { ...prev[skuId], [field]: value },
    }))
    setResult(null)
  }

  async function handleSimulate() {
    const skus = Object.values(selectedSkus)
    if (skus.length === 0) { setError("Chọn ít nhất 1 SKU."); return }
    setLoading(true); setError(null)
    try {
      const token = await getAuthToken()
      if (!token) throw new Error("Chưa đăng nhập.")
      const res = await toolsApi.simulateCampaign(token, {
        snapshot_id: insight.id,
        skus,
      })
      setResult(res)
    } catch (e: any) {
      setError(e?.message ?? "Tính toán thất bại.")
    } finally {
      setLoading(false)
    }
  }

  const selectedCount = Object.keys(selectedSkus).length

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold">Kiểm tra chiến dịch</h1>
        <p className="text-sm text-gray-500 mt-1">
          Chọn SKU + nhập số lượng dự kiến → Tikai tính P&L trước khi chiến dịch go live.
        </p>
      </div>

      {/* SKU selector */}
      <div className="bg-white border rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b bg-gray-50 text-sm font-medium text-gray-700">
          Chọn SKU ({selectedCount} đã chọn)
        </div>
        <div className="divide-y max-h-80 overflow-y-auto">
          {topSkus.map((sku) => {
            const sel = selectedSkus[sku.sku_id]
            return (
              <div key={sku.sku_id} className={`px-5 py-3 ${sel ? "bg-blue-50" : "hover:bg-gray-50"}`}>
                <div className="flex items-center gap-3">
                  <input type="checkbox" checked={!!sel}
                    onChange={() => toggle(sku.sku_id, sku.sku_name)}
                    className="w-4 h-4 accent-blue-600" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{sku.sku_name}</p>
                    <p className="text-xs text-gray-400">GMV: {formatVND(sku.gmv)}</p>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    sku.health_status === "critical" ? "bg-red-100 text-red-700" :
                    sku.health_status === "warning" ? "bg-amber-100 text-amber-700" :
                    "bg-green-100 text-green-700"
                  }`}>{sku.health_status}</span>
                </div>

                {sel && (
                  <div className="mt-3 grid grid-cols-2 gap-3 pl-7">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Số lượng dự kiến</label>
                      <input type="number" min="1" value={sel.planned_units}
                        onChange={(e) => updateEntry(sku.sku_id, "planned_units", parseInt(e.target.value) || 1)}
                        className="w-full border rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 [appearance:textfield]" />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Thay đổi giá (%)</label>
                      <input type="number" step="1" placeholder="0" value={sel.price_change_pct ?? ""}
                        onChange={(e) => updateEntry(sku.sku_id, "price_change_pct", e.target.value ? String(parseFloat(e.target.value) / 100) : null as any)}
                        className="w-full border rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 [appearance:textfield]" />
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <button onClick={handleSimulate} disabled={loading || selectedCount === 0}
        className="bg-blue-600 text-white px-5 py-2.5 rounded-xl font-medium text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors">
        {loading ? "Đang tính..." : `Tính P&L cho ${selectedCount} SKU →`}
      </button>

      {result && (
        <div className="space-y-4">
          {/* Portfolio summary */}
          <div className="bg-white border rounded-xl p-5">
            <h2 className="font-semibold text-sm mb-3">Tổng portfolio</h2>
            <div className="grid grid-cols-3 gap-4 text-sm">
              {[
                ["Net Revenue hiện tại", result.portfolio.total_current_net_revenue],
                ["Net Revenue ước tính", result.portfolio.total_simulated_net_revenue],
                ["Delta", result.portfolio.total_net_revenue_delta],
              ].map(([label, val]) => (
                <div key={label}>
                  <p className="text-xs text-gray-500">{label}</p>
                  <p className={`font-semibold mt-0.5 ${
                    label === "Delta" && parseFloat(val) < 0 ? "text-red-600" :
                    label === "Delta" ? "text-green-700" : "text-gray-900"
                  }`}>{formatVND(val)}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Per-SKU */}
          <div className="border rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600">SKU</th>
                  <th className="text-right px-4 py-2.5 font-medium text-gray-600">NR hiện tại</th>
                  <th className="text-right px-4 py-2.5 font-medium text-gray-600">NR ước tính</th>
                  <th className="text-right px-4 py-2.5 font-medium text-gray-600">Margin</th>
                  <th className="px-4 py-2.5 font-medium text-gray-600">Nhận xét</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {result.skus.map((s) => (
                  <tr key={s.sku_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <p className="font-medium text-gray-900 truncate max-w-[180px]" title={s.sku_name}>{s.sku_name}</p>
                      <p className="text-xs text-gray-400">{s.planned_units.toLocaleString()} đơn vị</p>
                    </td>
                    <td className="px-4 py-3 text-right text-gray-600">{formatVND(s.current_net_revenue)}</td>
                    <td className={`px-4 py-3 text-right font-medium ${
                      parseFloat(s.net_revenue_delta) >= 0 ? "text-green-700" : "text-red-600"
                    }`}>{formatVND(s.simulated_net_revenue)}</td>
                    <td className="px-4 py-3 text-right text-gray-600">
                      {s.simulated_margin_pct ? formatPct(s.simulated_margin_pct) : "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-600 max-w-[160px]">{s.verdict}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-xs text-gray-400 text-center">
            Fee config: {result.fee_config_version}
          </p>
        </div>
      )}
    </div>
  )
}
