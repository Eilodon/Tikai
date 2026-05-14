"use client"
import { useState } from "react"
import { SKUSummaryItem, SimulationResult, toolsApi, formatVND } from "@/lib/api"
import { getAuthToken } from "@/lib/supabase"

interface WhatIfPanelProps {
  sku: SKUSummaryItem
  snapshotId: string
  onClose: () => void
}

function pctDisplay(val: string | null | undefined) {
  if (!val) return "—"
  return `${(parseFloat(val) * 100).toFixed(1)}%`
}

export function WhatIfPanel({ sku, snapshotId, onClose }: WhatIfPanelProps) {
  const currentAffRate = 0.10  // default if not on snapshot
  const currentVoucherRate = 0.05

  const [affiliateRate, setAffiliateRate] = useState(currentAffRate)
  const [voucherRate, setVoucherRate] = useState(currentVoucherRate)
  const [priceChangePct, setPriceChangePct] = useState(0)
  const [result, setResult] = useState<SimulationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSimulate() {
    setLoading(true)
    setError(null)
    try {
      const token = await getAuthToken()
      if (!token) throw new Error("Not authenticated")
      const res = await toolsApi.simulate(token, {
        snapshot_id: snapshotId,
        sku_id: sku.sku_id,
        affiliate_rate: affiliateRate !== currentAffRate ? String(affiliateRate) : null,
        voucher_rate: voucherRate !== currentVoucherRate ? String(voucherRate) : null,
        price_change_pct: priceChangePct !== 0 ? String(priceChangePct) : null,
      })
      setResult(res)
    } catch (e: any) {
      setError(e?.message ?? "Tính toán thất bại.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b">
          <div>
            <h2 className="font-semibold text-sm">Thử thay đổi</h2>
            <p className="text-xs text-gray-500 truncate max-w-[260px]">{sku.sku_name}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-xl leading-none">×</button>
        </div>

        <div className="p-5 space-y-5">
          {/* Affiliate Rate */}
          <div>
            <div className="flex justify-between text-sm mb-1">
              <label className="font-medium text-gray-700">Affiliate rate</label>
              <span className="font-semibold text-blue-600">{(affiliateRate * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range" min="0" max="0.30" step="0.01"
              value={affiliateRate}
              onChange={(e) => setAffiliateRate(parseFloat(e.target.value))}
              className="w-full accent-blue-600"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-0.5">
              <span>0%</span><span>30%</span>
            </div>
          </div>

          {/* Voucher Rate */}
          <div>
            <div className="flex justify-between text-sm mb-1">
              <label className="font-medium text-gray-700">Voucher rate</label>
              <span className="font-semibold text-blue-600">{(voucherRate * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range" min="0" max="0.30" step="0.01"
              value={voucherRate}
              onChange={(e) => setVoucherRate(parseFloat(e.target.value))}
              className="w-full accent-blue-600"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-0.5">
              <span>0%</span><span>30%</span>
            </div>
          </div>

          {/* Price Change */}
          <div>
            <div className="flex justify-between text-sm mb-1">
              <label className="font-medium text-gray-700">Thay đổi giá bán</label>
              <span className={`font-semibold ${priceChangePct < 0 ? "text-red-600" : priceChangePct > 0 ? "text-green-600" : "text-gray-600"}`}>
                {priceChangePct >= 0 ? "+" : ""}{(priceChangePct * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range" min="-0.30" max="0.30" step="0.01"
              value={priceChangePct}
              onChange={(e) => setPriceChangePct(parseFloat(e.target.value))}
              className="w-full accent-blue-600"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-0.5">
              <span>-30%</span><span>+30%</span>
            </div>
          </div>

          <button
            onClick={handleSimulate}
            disabled={loading}
            className="w-full bg-blue-600 text-white py-2.5 rounded-xl font-medium text-sm
                       hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Đang tính..." : "Tính kết quả"}
          </button>

          {error && <p className="text-sm text-red-600 text-center">{error}</p>}

          {result && (
            <div className="border rounded-xl overflow-hidden">
              <div className="grid grid-cols-2">
                <div className="p-4 border-r border-b bg-gray-50">
                  <p className="text-xs text-gray-500 mb-1">Net Revenue hiện tại</p>
                  <p className="font-semibold text-sm">{formatVND(result.current_net_revenue)}</p>
                  {result.current_margin_pct && (
                    <p className="text-xs text-gray-500 mt-0.5">Margin: {pctDisplay(result.current_margin_pct)}</p>
                  )}
                </div>
                <div className="p-4 border-b">
                  <p className="text-xs text-gray-500 mb-1">Net Revenue mới</p>
                  <p className={`font-semibold text-sm ${
                    parseFloat(result.net_revenue_delta) >= 0 ? "text-green-700" : "text-red-600"
                  }`}>{formatVND(result.simulated_net_revenue)}</p>
                  {result.simulated_margin_pct && (
                    <p className="text-xs text-gray-500 mt-0.5">Margin: {pctDisplay(result.simulated_margin_pct)}</p>
                  )}
                </div>
              </div>
              <div className="p-4 bg-blue-50">
                <p className="text-sm font-medium text-blue-900">{result.verdict}</p>
                {result.breakeven_extra_orders && result.breakeven_extra_orders > 0 && (
                  <p className="text-xs text-blue-700 mt-1">
                    Cần bán thêm <strong>{result.breakeven_extra_orders.toLocaleString()} đơn</strong> để bù lại
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
