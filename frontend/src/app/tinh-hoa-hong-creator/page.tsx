"use client"
import { useState } from "react"

const PLATFORM_FEE = 0.125

function fmt(n: number): string {
  return Math.round(n).toLocaleString("vi-VN") + " ₫"
}

function CommissionCalculator() {
  const [price, setPrice] = useState("")
  const [commissionRate, setCommissionRate] = useState(0.10)
  const [numOrders, setNumOrders] = useState("1")

  const p = parseFloat(price) || 0
  const orders = parseInt(numOrders) || 1

  const commissionPerOrder = p * commissionRate
  const netAfterCommission = p * (1 - commissionRate - PLATFORM_FEE)
  const totalCommission = commissionPerOrder * orders
  const refundLoss = totalCommission * 0.20

  const hasResult = p > 0

  return (
    <div className="bg-white rounded-2xl border p-6 space-y-5">
      <div className="space-y-4">
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
            className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 [appearance:textfield]"
          />
        </div>

        <div>
          <div className="flex justify-between text-sm mb-1">
            <label className="font-medium">Tỷ lệ hoa hồng creator</label>
            <span className="font-semibold text-teal-600">{(commissionRate * 100).toFixed(0)}%</span>
          </div>
          <input
            type="range"
            min="0.01"
            max="0.30"
            step="0.01"
            value={commissionRate}
            onChange={(e) => setCommissionRate(parseFloat(e.target.value))}
            className="w-full accent-teal-600"
          />
          <div className="flex justify-between text-xs text-gray-400 mt-0.5">
            <span>1%</span><span>30%</span>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-sm font-medium">Phí sàn TikTok Shop</label>
            <span className="text-sm font-semibold text-gray-500">12.5%</span>
          </div>
          <div className="bg-gray-50 border border-dashed rounded-lg px-3 py-2 text-xs text-gray-500">
            Phí sàn mới từ 3/2026 — cố định, không chỉnh được
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Số đơn hàng</label>
          <input
            type="number"
            min="1"
            step="1"
            value={numOrders}
            onChange={(e) => setNumOrders(e.target.value)}
            placeholder="VD: 100"
            className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 [appearance:textfield]"
          />
        </div>
      </div>

      {hasResult && (
        <div className="border-t pt-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-teal-50 rounded-xl p-4 text-center">
              <p className="text-xs text-gray-500 mb-1">Hoa hồng / đơn</p>
              <p className="text-xl font-bold text-teal-700">{fmt(commissionPerOrder)}</p>
            </div>
            <div className={`rounded-xl p-4 text-center ${netAfterCommission < 0 ? "bg-red-50" : "bg-green-50"}`}>
              <p className="text-xs text-gray-500 mb-1">Net sau phí + HH</p>
              <p className={`text-xl font-bold ${netAfterCommission < 0 ? "text-red-700" : "text-green-700"}`}>
                {fmt(netAfterCommission)}
              </p>
            </div>
          </div>

          <div className="border rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600">Khoản mục</th>
                  <th className="text-right px-4 py-2.5 font-medium text-gray-600">Giá trị</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                <tr>
                  <td className="px-4 py-2.5 text-gray-700">Hoa hồng / đơn</td>
                  <td className="px-4 py-2.5 text-right text-teal-700 font-medium">{fmt(commissionPerOrder)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 text-gray-700">Phí sàn / đơn (12.5%)</td>
                  <td className="px-4 py-2.5 text-right text-red-600">{fmt(p * PLATFORM_FEE)}</td>
                </tr>
                <tr>
                  <td className="px-4 py-2.5 text-gray-700">Net sau phí + hoa hồng</td>
                  <td className={`px-4 py-2.5 text-right font-semibold ${netAfterCommission < 0 ? "text-red-700" : "text-green-700"}`}>
                    {fmt(netAfterCommission)}
                  </td>
                </tr>
                <tr className="bg-teal-50">
                  <td className="px-4 py-2.5 text-gray-700 font-medium">Tổng hoa hồng ({orders.toLocaleString("vi-VN")} đơn)</td>
                  <td className="px-4 py-2.5 text-right font-bold text-teal-700">{fmt(totalCommission)}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
            <p className="text-sm font-medium text-amber-900 mb-1">Kịch bản hoàn hàng 20%</p>
            <p className="text-xs text-amber-700">
              Hoa hồng bị mất không thu hồi:{" "}
              <span className="font-semibold text-amber-900">{fmt(refundLoss)}</span>
            </p>
            <p className="text-xs text-amber-600 mt-1">
              TikTok Shop không thu hồi hoa hồng creator khi đơn hoàn trả.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

export default function TinhHoaHongCreatorPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white px-6 py-4 flex items-center justify-between">
        <a href="/" className="font-bold text-lg">Tikai</a>
        <a href="/login" className="text-sm text-teal-600 hover:underline">Đăng nhập →</a>
      </header>

      <main className="max-w-lg mx-auto px-4 py-10">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold">Tính Hoa Hồng Creator TikTok Shop</h1>
          <p className="text-gray-500 mt-2 text-sm">
            Tính chính xác hoa hồng affiliate creator — bao gồm kịch bản hoàn hàng
            và hoa hồng bị mất không thu hồi.
          </p>
        </div>

        <CommissionCalculator />

        <div className="mt-8 bg-teal-50 rounded-xl p-5 text-center">
          <p className="font-medium text-sm">Biết lãi thật từng SKU với creator nào?</p>
          <p className="text-xs text-gray-500 mt-1">
            Tikai phân tích hiệu quả từng creator dựa trên data thật — phát hiện
            creator đang đốt tiền shop.
          </p>
          <a
            href="/"
            className="mt-3 inline-block bg-gray-900 text-white text-sm px-5 py-2 rounded-lg font-medium hover:bg-gray-700 transition-colors"
          >
            Tính lãi thật từng SKU với Tikai →
          </a>
        </div>
      </main>
    </div>
  )
}
