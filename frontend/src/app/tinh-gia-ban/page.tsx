"use client"
import { useState } from "react"
import { publicToolsApi, PriceRecommendResponse, formatVND } from "@/lib/api"

const BREAKDOWN_LABELS: Record<string, string> = {
  cogs:                "Giá vốn",
  platform_commission: "Phí sàn (6%)",
  transaction_fee:     "Phí giao dịch",
  order_processing:    "Phí xử lý đơn",
  affiliate:           "Affiliate",
  voucher:             "Voucher",
  margin:              "Margin (lãi)",
}

function PriceCalculator() {
  const [cogs, setCogs] = useState("")
  const [targetMargin, setTargetMargin] = useState(0.20)
  const [affiliateRate, setAffiliateRate] = useState(0.10)
  const [voucherRate, setVoucherRate] = useState(0.05)
  const [result, setResult] = useState<PriceRecommendResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleCalculate(e: React.FormEvent) {
    e.preventDefault()
    if (!cogs || parseFloat(cogs) <= 0) { setError("Nhập giá vốn để tính."); return }
    setLoading(true); setError(null); setResult(null)
    try {
      const res = await publicToolsApi.priceRecommend({
        cogs_per_unit: cogs,
        target_margin_pct: String(targetMargin),
        affiliate_rate: String(affiliateRate),
        voucher_rate: String(voucherRate),
      })
      setResult(res)
    } catch (e: any) {
      setError(e?.message ?? "Không tính được. Thử lại sau.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-2xl border p-6 space-y-5">
      <form onSubmit={handleCalculate} className="space-y-4">
        <div>
          <label htmlFor="public-price-cogs" className="block text-sm font-medium mb-1">
            Giá vốn / đơn vị (VND) <span className="text-red-500">*</span>
          </label>
          <input
            id="public-price-cogs"
            type="number" required min="0" step="1000"
            value={cogs} onChange={(e) => setCogs(e.target.value)}
            placeholder="VD: 80000"
            className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 [appearance:textfield]"
          />
        </div>

        <div>
          <div className="flex justify-between text-sm mb-1">
            <label className="font-medium">Margin mục tiêu</label>
            <span className="font-semibold text-blue-600">{(targetMargin * 100).toFixed(0)}%</span>
          </div>
          <input type="range" min="0.05" max="0.50" step="0.01" value={targetMargin}
            onChange={(e) => setTargetMargin(parseFloat(e.target.value))}
            className="w-full accent-blue-600" />
          <div className="flex justify-between text-xs text-gray-400 mt-0.5">
            <span>5%</span><span>50%</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="flex justify-between text-sm mb-1">
              <label className="font-medium">Affiliate</label>
              <span className="text-blue-600 font-semibold">{(affiliateRate * 100).toFixed(0)}%</span>
            </div>
            <input type="range" min="0" max="0.30" step="0.01" value={affiliateRate}
              onChange={(e) => setAffiliateRate(parseFloat(e.target.value))}
              className="w-full accent-blue-600" />
          </div>
          <div>
            <div className="flex justify-between text-sm mb-1">
              <label className="font-medium">Voucher</label>
              <span className="text-blue-600 font-semibold">{(voucherRate * 100).toFixed(0)}%</span>
            </div>
            <input type="range" min="0" max="0.30" step="0.01" value={voucherRate}
              onChange={(e) => setVoucherRate(parseFloat(e.target.value))}
              className="w-full accent-blue-600" />
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button type="submit" disabled={loading}
          className="w-full bg-blue-600 text-white py-3 rounded-xl font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
          {loading ? "Đang tính..." : "Tính giá bán tối thiểu →"}
        </button>
      </form>

      {result && (
        <div className="border-t pt-5 space-y-4">
          <div className="bg-blue-50 rounded-xl p-5 text-center">
            <p className="text-sm text-gray-600 mb-1">Giá bán tối thiểu để đạt {(targetMargin * 100).toFixed(0)}% margin</p>
            <p className="text-4xl font-bold text-blue-700">{formatVND(result.min_price)}</p>
            {result.warning && (
              <p className="text-xs text-amber-600 mt-2">{result.warning}</p>
            )}
          </div>

          <div className="border rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600">Chi phí</th>
                  <th className="text-right px-4 py-2.5 font-medium text-gray-600">Số tiền</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {Object.entries(result.breakdown).map(([key, value]) => (
                  <tr key={key} className={key === "margin" ? "bg-green-50 font-medium" : ""}>
                    <td className="px-4 py-2.5 text-gray-700">{BREAKDOWN_LABELS[key] ?? key}</td>
                    <td className="px-4 py-2.5 text-right text-gray-900">{formatVND(value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-xs text-gray-400 text-center">
            Phí theo cấu hình {result.fee_config_version} · TikTok Shop VN
          </p>
        </div>
      )}
    </div>
  )
}

export default function TinhGiaBanPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white px-6 py-4 flex items-center justify-between">
        <a href="/" className="font-bold text-lg">Tikai</a>
        <a href="/login" className="text-sm text-blue-600 hover:underline">Đăng nhập →</a>
      </header>

      <main className="max-w-lg mx-auto px-4 py-10">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold">Bán giá bao nhiêu mới có lãi?</h1>
          <p className="text-gray-500 mt-2 text-sm">
            Tính giá bán tối thiểu sau khi trừ phí TikTok Shop, affiliate, voucher.
            Cập nhật fee tháng 5/2026.
          </p>
        </div>

        <PriceCalculator />

        <div className="mt-8 bg-blue-50 rounded-xl p-5 text-center">
          <p className="font-medium text-sm">Shop bạn đang lãi hay lỗ thực sự?</p>
          <p className="text-xs text-gray-500 mt-1">
            Upload file TikTok Shop hoặc Shopee — Tikai phân tích P&L toàn bộ miễn phí.
          </p>
          <a href="/login?redirect=/import"
            className="mt-3 inline-block bg-gray-900 text-white text-sm px-5 py-2 rounded-lg font-medium hover:bg-gray-700 transition-colors">
            Phân tích shop của tôi →
          </a>
        </div>
      </main>
    </div>
  )
}
