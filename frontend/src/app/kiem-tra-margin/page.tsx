"use client"
import { useState } from "react"

const PLATFORM_FEE = 0.125
const REFUND_RATE = 0.15

function pct(n: number) {
  return (n * 100).toFixed(1) + "%"
}

function verdict(netMargin: number): { label: string; color: string } {
  if (netMargin > 0.2) return { label: "✅ Margin tốt — trên mức ngành", color: "text-green-700 bg-green-50 border-green-200" }
  if (netMargin >= 0.1) return { label: "⚠️ Margin ổn — cần theo dõi", color: "text-yellow-700 bg-yellow-50 border-yellow-200" }
  if (netMargin >= 0) return { label: "🔴 Margin mỏng — rủi ro cao khi có hoàn hàng", color: "text-orange-700 bg-orange-50 border-orange-200" }
  return { label: "🚨 Đang lỗ — cần điều chỉnh ngay", color: "text-red-700 bg-red-50 border-red-200" }
}

function MarginChecker() {
  const [price, setPrice] = useState("")
  const [cogs, setCogs] = useState("")
  const [commissionRate, setCommissionRate] = useState(0.10)
  const [voucherRate, setVoucherRate] = useState(0.05)

  const p = parseFloat(price) || 0
  const c = parseFloat(cogs) || 0
  const hasInput = p > 0 && c > 0

  const grossMargin = p > 0 ? (p - c) / p : 0
  const netMargin = p > 0
    ? (p - c - p * commissionRate - p * voucherRate - p * PLATFORM_FEE) / p
    : 0
  const refundAdjustedMargin = netMargin - commissionRate * REFUND_RATE
  const v = verdict(netMargin)

  return (
    <div className="bg-white rounded-2xl border p-6 space-y-5">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              Giá bán (VND) <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              min="1"
              step="1000"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="VD: 150000"
              className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 [appearance:textfield]"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              Giá vốn / đơn (VND) <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              min="1"
              step="1000"
              value={cogs}
              onChange={(e) => setCogs(e.target.value)}
              placeholder="VD: 70000"
              className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 [appearance:textfield]"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="flex justify-between text-sm mb-1">
              <label className="font-medium">Hoa hồng affiliate</label>
              <span className="font-semibold text-blue-600">{(commissionRate * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="0.30"
              step="0.01"
              value={commissionRate}
              onChange={(e) => setCommissionRate(parseFloat(e.target.value))}
              className="w-full accent-blue-600"
            />
          </div>
          <div>
            <div className="flex justify-between text-sm mb-1">
              <label className="font-medium">Voucher / chiết khấu</label>
              <span className="font-semibold text-blue-600">{(voucherRate * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="0.30"
              step="0.01"
              value={voucherRate}
              onChange={(e) => setVoucherRate(parseFloat(e.target.value))}
              className="w-full accent-blue-600"
            />
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-sm font-medium">Phí sàn TikTok Shop</label>
            <span className="text-sm font-semibold text-gray-500">12.5%</span>
          </div>
          <div className="bg-gray-50 border border-dashed rounded-lg px-3 py-2 text-xs text-gray-500">
            Phí sàn mới từ 3/2026 — cố định
          </div>
        </div>
      </div>

      {hasInput && (
        <div className="border-t pt-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gray-50 rounded-xl p-4 text-center">
              <p className="text-xs text-gray-500 mb-1">Gross Margin</p>
              <p className={`text-2xl font-bold ${grossMargin < 0 ? "text-red-700" : "text-gray-800"}`}>
                {pct(grossMargin)}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">Trước phí & hoa hồng</p>
            </div>
            <div className={`rounded-xl p-4 text-center ${netMargin < 0 ? "bg-red-50" : netMargin < 0.1 ? "bg-orange-50" : "bg-green-50"}`}>
              <p className="text-xs text-gray-500 mb-1">Net Margin</p>
              <p className={`text-2xl font-bold ${netMargin < 0 ? "text-red-700" : netMargin < 0.1 ? "text-orange-700" : "text-green-700"}`}>
                {pct(netMargin)}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">Sau tất cả phí</p>
            </div>
          </div>

          <div className={`border rounded-xl px-4 py-3 ${v.color}`}>
            <p className="text-sm font-semibold">{v.label}</p>
          </div>

          <div className="border rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600">Khoản mục</th>
                  <th className="text-right px-4 py-2.5 font-medium text-gray-600">% giá bán</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                <tr>
                  <td className="px-4 py-2.5 text-gray-700">Giá vốn (COGS)</td>
                  <td className="px-4 py-2.5 text-right text-gray-900">{pct(c / p)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 text-gray-700">Hoa hồng affiliate</td>
                  <td className="px-4 py-2.5 text-right text-gray-900">{pct(commissionRate)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 text-gray-700">Voucher / chiết khấu</td>
                  <td className="px-4 py-2.5 text-right text-gray-900">{pct(voucherRate)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 text-gray-700">Phí sàn TikTok</td>
                  <td className="px-4 py-2.5 text-right text-gray-900">{pct(PLATFORM_FEE)}</td>
                </tr>
                <tr className={`font-medium ${netMargin < 0 ? "bg-red-50" : "bg-green-50"}`}>
                  <td className="px-4 py-2.5">Net Margin</td>
                  <td className={`px-4 py-2.5 text-right font-bold ${netMargin < 0 ? "text-red-700" : "text-green-700"}`}>
                    {pct(netMargin)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
            <p className="text-sm font-medium text-amber-900 mb-1">
              Nếu refund rate 15% — margin thực:
            </p>
            <p className={`text-lg font-bold ${refundAdjustedMargin < 0 ? "text-red-700" : "text-amber-800"}`}>
              {pct(refundAdjustedMargin)}
            </p>
            <p className="text-xs text-amber-600 mt-1">
              Hoa hồng bị mất khi hoàn đơn không được thu hồi.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

export default function KiemTraMarginPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white px-6 py-4 flex items-center justify-between">
        <a href="/" className="font-bold text-lg">Tikai</a>
        <a href="/login" className="text-sm text-blue-600 hover:underline">Đăng nhập →</a>
      </header>

      <main className="max-w-lg mx-auto px-4 py-10">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold">Kiểm Tra Margin TikTok Shop</h1>
          <p className="text-gray-500 mt-2 text-sm">
            Tính margin thực sau phí sàn, hoa hồng, voucher. Biết ngay sản phẩm
            đang có lãi hay đang lỗ.
          </p>
        </div>

        <MarginChecker />

        <div className="mt-8 bg-blue-50 rounded-xl p-5 text-center">
          <p className="font-medium text-sm">Xem margin thật từng SKU của shop bạn</p>
          <p className="text-xs text-gray-500 mt-1">
            Upload file TikTok Shop — Tikai phân tích margin thực tế toàn bộ danh mục
            miễn phí.
          </p>
          <a
            href="/"
            className="mt-3 inline-block bg-gray-900 text-white text-sm px-5 py-2 rounded-lg font-medium hover:bg-gray-700 transition-colors"
          >
            Xem margin thật từng SKU với Tikai →
          </a>
        </div>
      </main>
    </div>
  )
}
