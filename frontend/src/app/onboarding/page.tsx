"use client"
import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { shopsApi } from "@/lib/api"
import { getAuthToken } from "@/lib/supabase"

export default function OnboardingPage() {
  const router = useRouter()
  const [shopName, setShopName] = useState("")

  useEffect(() => {
    getAuthToken().then(async (token) => {
      if (!token) return
      try {
        await shopsApi.getMe(token)
        router.replace("/overview")
      } catch {
        // No shop yet — stay on onboarding
      }
    })
  }, [])
  const [tiktokShopId, setTiktokShopId] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const token = await getAuthToken()
      if (!token) throw new Error("Vui lòng đăng nhập lại.")

      const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
      const res = await fetch(`${API_BASE}/v1/shops/onboarding`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          shop_name: shopName,
          tiktok_shop_id: tiktokShopId || undefined,
        }),
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data?.error?.message ?? "Không thể tạo shop.")
      }

      router.push("/import")
    } catch (err: any) {
      setError(err?.message ?? "Đã xảy ra lỗi.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md bg-white rounded-2xl border shadow-sm p-8">
        <div className="mb-8">
          <div className="text-3xl mb-2">👋</div>
          <h1 className="text-2xl font-bold">Chào mừng đến với Tikai</h1>
          <p className="text-sm text-gray-500 mt-1">
            Thiết lập shop của bạn để bắt đầu phân tích dữ liệu TikTok Shop.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium mb-1">
              Tên shop <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              required
              value={shopName}
              onChange={(e) => setShopName(e.target.value)}
              placeholder="VD: Shop Mỹ Phẩm ABC"
              className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              TikTok Shop ID{" "}
              <span className="text-gray-400 font-normal">(tuỳ chọn)</span>
            </label>
            <input
              type="text"
              value={tiktokShopId}
              onChange={(e) => setTiktokShopId(e.target.value)}
              placeholder="VD: 7123456789012345678"
              className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-400 mt-1">
              Tìm trong TikTok Seller Center → Cài đặt shop.
            </p>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !shopName.trim()}
            className="w-full bg-gray-900 text-white rounded-lg py-3 text-sm font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Đang thiết lập..." : "Bắt đầu sử dụng →"}
          </button>
        </form>

        <div className="mt-6 bg-blue-50 rounded-lg p-4 text-xs text-blue-800">
          <p className="font-medium mb-1">Bước tiếp theo sau khi thiết lập:</p>
          <ol className="list-decimal list-inside space-y-1">
            <li>Import file Order Export từ TikTok Shop</li>
            <li>Tikai phân tích P&L và phát hiện leak</li>
            <li>Nhận action gợi ý để cải thiện margin</li>
          </ol>
        </div>
      </div>
    </div>
  )
}
