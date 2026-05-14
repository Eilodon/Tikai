"use client"
import { useState, useEffect } from "react"
import { toolsApi, BenchmarkComparison } from "@/lib/api"
import { getAuthToken } from "@/lib/supabase"

const CATEGORIES = [
  { value: "fashion",     label: "Thời trang" },
  { value: "beauty",      label: "Làm đẹp" },
  { value: "food",        label: "Thực phẩm" },
  { value: "electronics", label: "Điện tử" },
  { value: "home",        label: "Nhà cửa" },
  { value: "baby",        label: "Mẹ & Bé" },
  { value: "other",       label: "Khác" },
]

function VerdictIcon({ verdict }: { verdict: BenchmarkComparison["verdict"] }) {
  if (verdict === "better") return <span className="text-green-600 font-bold text-base">↑ Tốt hơn</span>
  if (verdict === "worse")  return <span className="text-red-600 font-bold text-base">↓ Kém hơn</span>
  return <span className="text-gray-500 text-sm">→ Tương đương</span>
}

function pctDisplay(val: string) {
  return `${(parseFloat(val) * 100).toFixed(1)}%`
}

export function IndustryBenchmark({ snapshotId }: { snapshotId: string }) {
  const [category, setCategory] = useState("other")
  const [data, setData] = useState<BenchmarkComparison[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getAuthToken().then((token) => {
      if (!token) return
      return toolsApi.getBenchmark(token, snapshotId, category)
    }).then((res) => {
      if (!cancelled && res) setData(res.comparisons)
    }).catch(() => {
      if (!cancelled) setError("Không tải được benchmark.")
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [snapshotId, category])

  return (
    <div className="bg-white rounded-xl border p-5 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="font-semibold text-sm">So sánh với ngành</h2>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="text-xs border rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
      </div>

      {loading && (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && data && data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-500 border-b">
                <th className="text-left py-2 pr-4 font-medium">Chỉ số</th>
                <th className="text-right py-2 pr-4 font-medium">Bạn</th>
                <th className="text-right py-2 pr-4 font-medium">Ngành</th>
                <th className="text-right py-2 font-medium">Đánh giá</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.map((row) => (
                <tr key={row.metric} className="hover:bg-gray-50">
                  <td className="py-2.5 pr-4 text-gray-700">{row.metric_label}</td>
                  <td className="py-2.5 pr-4 text-right font-medium">
                    {pctDisplay(row.shop_value)}
                  </td>
                  <td className="py-2.5 pr-4 text-right text-gray-500">
                    {pctDisplay(row.industry_value)}
                  </td>
                  <td className="py-2.5 text-right">
                    <VerdictIcon verdict={row.verdict} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && data && (
        <p className="text-xs text-gray-400">
          Nguồn: {data[0]?.source ?? "Metric.vn / YouNet ECI 2025"}
        </p>
      )}
    </div>
  )
}
