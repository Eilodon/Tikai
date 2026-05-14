"use client"
import { useState, useEffect } from "react"
import { publicToolsApi, FeeScheduleResponse, formatVND } from "@/lib/api"

function FeeCalculator({ fees }: { fees: FeeScheduleResponse }) {
  const [revenue, setRevenue] = useState("")
  const [orders, setOrders] = useState("10")
  const [affiliateRate, setAffiliateRate] = useState(0.10)
  const [voucherRate, setVoucherRate] = useState(0.05)
  const [result, setResult] = useState<ReturnType<typeof compute> | null>(null)

  function compute(rev: number, ord: number) {
    const platformFee = rev * parseFloat(fees.platform_commission_rate)
    const transactionFee = rev * parseFloat(fees.transaction_fee_rate)
    const orderFee = ord * parseFloat(fees.order_processing_fee_per_order)
    const affiliateFee = rev * affiliateRate
    const voucherFee = rev * voucherRate
    const totalFee = platformFee + transactionFee + orderFee + affiliateFee + voucherFee
    const netRevenue = rev - totalFee
    const feePct = rev > 0 ? totalFee / rev : 0
    return { platformFee, transactionFee, orderFee, affiliateFee, voucherFee, totalFee, netRevenue, feePct }
  }

  function handleCalculate(e: React.FormEvent) {
    e.preventDefault()
    const rev = parseFloat(revenue)
    const ord = parseInt(orders) || 1
    if (!rev || rev <= 0) return
    setResult(compute(rev, ord))
  }

  return (
    <div className="bg-white rounded-2xl border p-6 space-y-5">
      <form onSubmit={handleCalculate} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Doanh thu (GMV) <span className="text-red-500">*</span></label>
            <input type="number" required min="1" step="1000" value={revenue}
              onChange={(e) => setRevenue(e.target.value)}
              placeholder="VD: 100000000"
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 [appearance:textfield]" />
            <p className="text-xs text-gray-400 mt-0.5">Tổng doanh thu trước phí</p>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Số đơn</label>
            <input type="number" min="1" value={orders}
              onChange={(e) => setOrders(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 [appearance:textfield]" />
            <p className="text-xs text-gray-400 mt-0.5">Để tính phí xử lý đơn</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="flex justify-between text-sm mb-1">
              <label className="font-medium">Affiliate rate</label>
              <span className="text-blue-600 font-semibold">{(affiliateRate * 100).toFixed(0)}%</span>
            </div>
            <input type="range" min="0" max="0.30" step="0.01" value={affiliateRate}
              onChange={(e) => setAffiliateRate(parseFloat(e.target.value))}
              className="w-full accent-blue-600" />
          </div>
          <div>
            <div className="flex justify-between text-sm mb-1">
              <label className="font-medium">Voucher rate</label>
              <span className="text-blue-600 font-semibold">{(voucherRate * 100).toFixed(0)}%</span>
            </div>
            <input type="range" min="0" max="0.30" step="0.01" value={voucherRate}
              onChange={(e) => setVoucherRate(parseFloat(e.target.value))}
              className="w-full accent-blue-600" />
          </div>
        </div>

        <button type="submit"
          className="w-full bg-blue-600 text-white py-3 rounded-xl font-medium hover:bg-blue-700 transition-colors">
          Tính phí →
        </button>
      </form>

      {result && (
        <div className="border-t pt-5 space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-gray-50 rounded-xl p-4 text-center">
              <p className="text-xs text-gray-500 mb-1">Tổng phí</p>
              <p className="text-2xl font-bold text-red-600">{formatVND(String(result.totalFee))}</p>
              <p className="text-xs text-gray-400 mt-0.5">({(result.feePct * 100).toFixed(1)}% doanh thu)</p>
            </div>
            <div className="bg-green-50 rounded-xl p-4 text-center">
              <p className="text-xs text-gray-500 mb-1">Còn lại (Net Revenue)</p>
              <p className={`text-2xl font-bold ${result.netRevenue < 0 ? "text-red-700" : "text-green-700"}`}>
                {formatVND(String(result.netRevenue))}
              </p>
            </div>
          </div>

          <div className="border rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600">Loại phí</th>
                  <th className="text-right px-4 py-2.5 font-medium text-gray-600">Số tiền</th>
                  <th className="text-right px-4 py-2.5 font-medium text-gray-600">% doanh thu</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {[
                  ["Phí sàn TikTok", result.platformFee, parseFloat(fees.platform_commission_rate)],
                  ["Phí giao dịch (6%)", result.transactionFee, parseFloat(fees.transaction_fee_rate)],
                  [`Phí xử lý đơn (${formatVND(fees.order_processing_fee_per_order)}/đơn)`, result.orderFee, result.orderFee / parseFloat(revenue)],
                  ["Affiliate", result.affiliateFee, affiliateRate],
                  ["Voucher", result.voucherFee, voucherRate],
                ].map(([label, amount, pct]) => (
                  <tr key={label as string} className="hover:bg-gray-50">
                    <td className="px-4 py-2.5 text-gray-700">{label as string}</td>
                    <td className="px-4 py-2.5 text-right text-gray-900">{formatVND(String(amount as number))}</td>
                    <td className="px-4 py-2.5 text-right text-gray-400">{((pct as number) * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-gray-400 text-center">Cấu hình phí {fees.version} · TikTok Shop VN</p>
        </div>
      )}
    </div>
  )
}

export default function TinhPhiTikTokPage() {
  const [fees, setFees] = useState<FeeScheduleResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    publicToolsApi.getFeeSchedule()
      .then(setFees)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white px-6 py-4 flex items-center justify-between">
        <a href="/" className="font-bold text-lg">Tikai</a>
        <a href="/login" className="text-sm text-blue-600 hover:underline">Đăng nhập →</a>
      </header>

      <main className="max-w-lg mx-auto px-4 py-10">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold">TikTok Shop tính phí thế nào?</h1>
          <p className="text-gray-500 mt-2 text-sm">
            Tính toán chi tiết từng loại phí dựa trên doanh thu của bạn.
            Cập nhật phí giao dịch 6% từ 09/05/2026.
          </p>
        </div>

        {loading ? (
          <div className="animate-pulse bg-white rounded-2xl border h-64" />
        ) : fees ? (
          <FeeCalculator fees={fees} />
        ) : (
          <div className="text-center text-gray-500 text-sm py-8">Không tải được dữ liệu phí.</div>
        )}

        <div className="mt-8 bg-blue-50 rounded-xl p-5 text-center">
          <p className="font-medium text-sm">Muốn biết chính xác shop đang tốn bao nhiêu?</p>
          <p className="text-xs text-gray-500 mt-1">
            Upload file TikTok Shop — Tikai phân tích P&L thực tế miễn phí.
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
