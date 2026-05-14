"use client"
import { useState } from "react"
import { toolsApi, PriceRecommendResponse, formatVND } from "@/lib/api"
import { getAuthToken } from "@/lib/supabase"

const BREAKDOWN_LABELS: Record<string, string> = {
  cogs:                "Giá vốn",
  platform_commission: "Phí sàn",
  transaction_fee:     "Phí giao dịch",
  order_processing:    "Phí xử lý đơn",
  affiliate:           "Affiliate",
  voucher:             "Voucher",
  margin:              "Margin (lãi)",
}

export function PriceRecommender() {
  const [cogs, setCogs] = useState("")
  const [targetMargin, setTargetMargin] = useState(0.20)
  const [affiliateRate, setAffiliateRate] = useState(0.10)
  const [voucherRate, setVoucherRate] = useState(0.05)
  const [result, setResult] = useState<PriceRecommendResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleCalculate() {
    if (!cogs || parseFloat(cogs) <= 0) {
      setError("Nhập giá vốn để tính.")
      return
    }
    setLoading(true)
    setError(null)
    try {
      const token = await getAuthToken()
      if (!token) throw new Error("Not authenticated")
      const res = await toolsApi.priceRecommend(token, {
        cogs_per_unit: cogs,
        target_margin_pct: String(targetMargin),
        affiliate_rate: String(affiliateRate),
        voucher_rate: String(voucherRate),
      })
      setResult(res)
    } catch (e: any) {
      const msg = e?.message ?? "Tính toán thất bại."
      setError(msg.includes("≥ 100%") ? msg : `Lỗi: ${msg}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-5">
      {/* Inputs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Giá vốn / đơn vị (VND)</label>
          <input
            type="number" min="0" step="1000" placeholder="VD: 50000"
            value={cogs}
            onChange={(e) => setCogs(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500
                       [appearance:textfield]"
          />
        </div>

        <div>
          <div className="flex justify-between text-sm mb-1">
            <label className="font-medium text-gray-700">Margin mục tiêu</label>
            <span className="font-semibold text-blue-600">{(targetMargin * 100).toFixed(0)}%</span>
          </div>
          <input
            type="range" min="0.05" max="0.50" step="0.01"
            value={targetMargin}
            onChange={(e) => setTargetMargin(parseFloat(e.target.value))}
            className="w-full accent-blue-600 mt-1"
          />
          <div className="flex justify-between text-xs text-gray-400">
            <span>5%</span><span>50%</span>
          </div>
        </div>

        <div>
          <div className="flex justify-between text-sm mb-1">
            <label className="font-medium text-gray-700">Affiliate rate</label>
            <span className="text-gray-600">{(affiliateRate * 100).toFixed(0)}%</span>
          </div>
          <input
            type="range" min="0" max="0.30" step="0.01"
            value={affiliateRate}
            onChange={(e) => setAffiliateRate(parseFloat(e.target.value))}
            className="w-full accent-blue-600"
          />
        </div>

        <div>
          <div className="flex justify-between text-sm mb-1">
            <label className="font-medium text-gray-700">Voucher rate</label>
            <span className="text-gray-600">{(voucherRate * 100).toFixed(0)}%</span>
          </div>
          <input
            type="range" min="0" max="0.20" step="0.01"
            value={voucherRate}
            onChange={(e) => setVoucherRate(parseFloat(e.target.value))}
            className="w-full accent-blue-600"
          />
        </div>
      </div>

      <button
        onClick={handleCalculate}
        disabled={loading || !cogs}
        className="w-full bg-blue-600 text-white py-2.5 rounded-xl font-medium text-sm
                   hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        {loading ? "Đang tính..." : "Tính giá bán tối thiểu →"}
      </button>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-3">
          <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-4 text-center">
            <p className="text-sm text-blue-700 mb-1">Giá bán tối thiểu để đạt margin {(parseFloat(result.target_margin_pct) * 100).toFixed(0)}%</p>
            <p className="text-3xl font-bold text-blue-900">{formatVND(result.min_price)}</p>
          </div>

          <div className="border rounded-xl overflow-hidden">
            <div className="px-4 py-2 bg-gray-50 border-b">
              <p className="text-xs font-medium text-gray-600 uppercase tracking-wide">Chi tiết từng khoản</p>
            </div>
            <div className="divide-y">
              {Object.entries(result.breakdown).map(([key, val]) => (
                <div key={key} className="flex justify-between px-4 py-2.5 text-sm">
                  <span className={`text-gray-600 ${key === "margin" ? "font-medium text-green-700" : ""}`}>
                    {BREAKDOWN_LABELS[key] ?? key}
                  </span>
                  <span className={`font-medium ${key === "margin" ? "text-green-700" : ""}`}>
                    {formatVND(val)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
