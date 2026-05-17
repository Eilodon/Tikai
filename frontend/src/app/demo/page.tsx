"use client"
import { useState, useEffect, useRef } from "react"
import { WowScreen } from "@/components/insights/WowScreen"
import { InsightSnapshotResponse } from "@/lib/api"

const DEMO_INSIGHT: InsightSnapshotResponse = {
  id: "00000000-0000-0000-0000-000000000001",
  shop_id: "00000000-0000-0000-0000-000000000002",
  period_start: "2026-05-01",
  period_end: "2026-05-14",
  gmv_total: "420000000",
  net_revenue: "28350000",
  total_orders: 1247,
  total_refunds: 52,
  refund_rate: "0.0417",
  cash_in_14d: "38200000",
  cash_in_30d: "71400000",
  cash_pending_total: "14500000",
  top_leaks: [
    {
      type: "sku",
      id: "sku-001",
      name: "Kem dưỡng ẩm 50ml",
      estimated_loss: "12600000",
      reason: "affiliate_high",
      confidence: "high",
      can_act_now: true,
    },
    {
      type: "creator",
      id: "creator-001",
      name: "KOC Nguyễn Minh A",
      estimated_loss: "8400000",
      reason: "commission_exceeds_margin",
      confidence: "high",
      can_act_now: true,
    },
    {
      type: "sku",
      id: "sku-002",
      name: "Serum Vitamin C 30ml",
      estimated_loss: "5200000",
      reason: "voucher_high",
      confidence: "medium",
      can_act_now: true,
    },
  ],
  top_skus: [
    {
      sku_id: "sku-001",
      sku_name: "Kem dưỡng ẩm 50ml",
      gmv: "186000000",
      net_revenue: "8370000",
      order_count: 620,
      refund_rate: "0.032",
      margin_pct: "-0.042",
      margin: "-7812000",
      gmv_rank: 1,
      affiliate_commission: "37200000",
      voucher_cost: "9300000",
      health_status: "critical",
      health_reasons: ["margin âm", "affiliate rate 20%"],
    },
    {
      sku_id: "sku-002",
      sku_name: "Serum Vitamin C 30ml",
      gmv: "126000000",
      net_revenue: "12600000",
      order_count: 420,
      refund_rate: "0.048",
      margin_pct: "0.051",
      margin: "6426000",
      gmv_rank: 2,
      affiliate_commission: "12600000",
      voucher_cost: "18900000",
      health_status: "warning",
      health_reasons: ["voucher rate cao 15%"],
    },
    {
      sku_id: "sku-003",
      sku_name: "Tẩy trang micellar 200ml",
      gmv: "108000000",
      net_revenue: "18360000",
      order_count: 360,
      refund_rate: "0.028",
      margin_pct: "0.142",
      margin: "15336000",
      gmv_rank: 3,
      affiliate_commission: "5400000",
      voucher_cost: "3240000",
      health_status: "healthy",
      health_reasons: [],
    },
  ],
  top_creators: [
    {
      creator_id: "c-001",
      creator_name: "KOC Nguyễn Minh A",
      attributed_gmv: "84000000",
      attributed_net_revenue: "5460000",
      total_commission: "16800000",
      order_count: 280,
      revenue_efficiency: "0.325",
      performance_label: "losing",
      suggested_max_commission_rate: "0.065",
    },
    {
      creator_id: "c-002",
      creator_name: "Beauty Reviewer B",
      attributed_gmv: "63000000",
      attributed_net_revenue: "14490000",
      total_commission: "6300000",
      order_count: 210,
      revenue_efficiency: "2.3",
      performance_label: "star",
      suggested_max_commission_rate: null,
    },
  ],
  is_net_revenue_mode: false,
  cogs_coverage_pct: "0.67",
  rule_engine_version: "v2.1.0",
  fee_config_version: "2026-VN-v3",
  days_in_period: 14,
  is_partial_period: true,
  is_first_import: false,
  created_at: "2026-05-14T08:00:00Z",
}

type Tab = "overview" | "skus" | "creators" | "actions"

const SAMPLE_ACTIONS = [
  {
    id: "a1",
    title: "Giảm affiliate rate Kem dưỡng ẩm 50ml",
    desc: "Affiliate 20% đang ăn vào margin. Đề xuất giảm xuống 8-10%.",
    impact: "Tiết kiệm ~12.6tr/kỳ",
    priority: "high",
  },
  {
    id: "a2",
    title: "Xem lại hợp đồng KOC Nguyễn Minh A",
    desc: "Commission vượt margin thực. Tái đàm phán hoặc chuyển sang revenue share.",
    impact: "Tiết kiệm ~8.4tr/kỳ",
    priority: "high",
  },
  {
    id: "a3",
    title: "Giảm voucher Serum Vitamin C",
    desc: "Voucher 15% quá cao so với ngành (~5-8%). Thử A/B với 8%.",
    impact: "Tiết kiệm ~5.2tr/kỳ",
    priority: "medium",
  },
]

function fmtVnd(n: number) {
  return Math.round(n).toLocaleString("vi-VN") + " ₫"
}

function SKURow({ sku }: { sku: (typeof DEMO_INSIGHT.top_skus)[0] }) {
  const [hovered, setHovered] = useState(false)
  const marginPct = parseFloat(sku.margin_pct ?? "0")
  const isNegative = marginPct < 0

  const statusColors: Record<string, string> = {
    critical: "bg-red-100 text-red-700",
    warning: "bg-yellow-100 text-yellow-700",
    healthy: "bg-green-100 text-green-700",
  }

  return (
    <tr
      className="hover:bg-blue-50 transition-colors cursor-pointer relative"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <td className="px-4 py-3 text-sm text-gray-900 font-medium relative">
        {sku.sku_name}
        {hovered && (
          <div className="absolute left-0 top-full z-10 bg-gray-900 text-white text-xs rounded-lg px-3 py-2 mt-1 w-52 shadow-lg pointer-events-none">
            Thử thay đổi affiliate rate để xem impact
          </div>
        )}
      </td>
      <td className="px-4 py-3 text-sm text-right">
        {fmtVnd(parseFloat(sku.gmv))}
      </td>
      <td className="px-4 py-3 text-sm text-right">
        {sku.order_count.toLocaleString("vi-VN")}
      </td>
      <td className="px-4 py-3 text-sm text-right">
        <span className={isNegative ? "text-red-600 font-semibold" : "text-green-600"}>
          {(marginPct * 100).toFixed(1)}%
        </span>
      </td>
      <td className="px-4 py-3 text-sm text-right">
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusColors[sku.health_status]}`}>
          {sku.health_status === "critical" ? "Nguy hiểm" : sku.health_status === "warning" ? "Cảnh báo" : "Tốt"}
        </span>
      </td>
    </tr>
  )
}

function OverviewTab() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "GMV", value: "420.000.000 ₫", sub: "14 ngày" },
          { label: "Net Revenue", value: "28.350.000 ₫", sub: "6.75% margin" },
          { label: "Hoàn hàng", value: "4.17%", sub: "52 đơn hoàn" },
        ].map(({ label, value, sub }) => (
          <div key={label} className="bg-white border rounded-xl p-4 text-center">
            <p className="text-xs text-gray-500 mb-1">{label}</p>
            <p className="font-bold text-gray-900 text-sm">{value}</p>
            <p className="text-xs text-gray-400 mt-0.5">{sub}</p>
          </div>
        ))}
      </div>

      <div className="bg-white border rounded-xl p-5 space-y-3">
        <h2 className="font-semibold text-sm">Phát hiện rò rỉ ({DEMO_INSIGHT.top_leaks.length} điểm)</h2>
        {DEMO_INSIGHT.top_leaks.map((leak) => (
          <div key={leak.id} className="flex items-center justify-between border-b last:border-0 pb-3 last:pb-0">
            <div>
              <p className="text-sm font-medium">{leak.name}</p>
              <p className="text-xs text-gray-500 mt-0.5 capitalize">{leak.reason.replace(/_/g, " ")}</p>
            </div>
            <p className="text-red-600 font-semibold text-sm">
              −{parseInt(leak.estimated_loss).toLocaleString("vi-VN")} ₫
            </p>
          </div>
        ))}
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
        <p className="text-sm font-medium text-blue-900">Dòng tiền 14 ngày tới</p>
        <p className="text-2xl font-bold text-blue-700 mt-1">38.200.000 ₫</p>
        <p className="text-xs text-gray-500 mt-0.5">Đang chờ thanh toán: 14.500.000 ₫</p>
      </div>
    </div>
  )
}

function SKUsTab() {
  return (
    <div className="bg-white border rounded-xl overflow-hidden">
      <div className="px-5 py-3 border-b bg-gray-50">
        <p className="text-xs text-gray-500 italic">Hover vào dòng để xem gợi ý tối ưu</p>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b">
          <tr>
            <th className="text-left px-4 py-2.5 font-medium text-gray-600">SKU</th>
            <th className="text-right px-4 py-2.5 font-medium text-gray-600">GMV</th>
            <th className="text-right px-4 py-2.5 font-medium text-gray-600">Đơn</th>
            <th className="text-right px-4 py-2.5 font-medium text-gray-600">Margin</th>
            <th className="text-right px-4 py-2.5 font-medium text-gray-600">Tình trạng</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {DEMO_INSIGHT.top_skus.map((sku) => (
            <SKURow key={sku.sku_id} sku={sku} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CreatorsTab() {
  const perfLabels: Record<string, { label: string; color: string }> = {
    star: { label: "⭐ Hiệu quả", color: "bg-green-100 text-green-700" },
    losing: { label: "📉 Đang lỗ", color: "bg-red-100 text-red-700" },
    neutral: { label: "Trung bình", color: "bg-gray-100 text-gray-700" },
  }

  return (
    <div className="bg-white border rounded-xl overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b">
          <tr>
            <th className="text-left px-4 py-2.5 font-medium text-gray-600">Creator</th>
            <th className="text-right px-4 py-2.5 font-medium text-gray-600">GMV</th>
            <th className="text-right px-4 py-2.5 font-medium text-gray-600">Hoa hồng</th>
            <th className="text-right px-4 py-2.5 font-medium text-gray-600">Đơn</th>
            <th className="text-right px-4 py-2.5 font-medium text-gray-600">Hiệu quả</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {DEMO_INSIGHT.top_creators.map((c) => {
            const perf = perfLabels[c.performance_label] ?? perfLabels.neutral
            return (
              <tr key={c.creator_id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 text-sm font-medium text-gray-900">{c.creator_name}</td>
                <td className="px-4 py-3 text-sm text-right">
                  {fmtVnd(parseFloat(c.attributed_gmv))}
                </td>
                <td className="px-4 py-3 text-sm text-right text-red-600">
                  {fmtVnd(parseFloat(c.total_commission))}
                </td>
                <td className="px-4 py-3 text-sm text-right">{c.order_count.toLocaleString("vi-VN")}</td>
                <td className="px-4 py-3 text-sm text-right">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${perf.color}`}>
                    {perf.label}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {DEMO_INSIGHT.top_creators.some(c => c.performance_label === "losing") && (
        <div className="bg-red-50 border-t px-5 py-3">
          <p className="text-xs text-red-700">
            💡 KOC Nguyễn Minh A đang lỗ — hoa hồng 20% vượt quá margin thực tế.
            Đề xuất: giảm xuống 6.5% hoặc đàm phán lại.
          </p>
        </div>
      )}
    </div>
  )
}

function ActionsTab() {
  const [done, setDone] = useState<Set<string>>(new Set())
  const priorityColors: Record<string, string> = {
    high: "bg-red-100 text-red-700",
    medium: "bg-yellow-100 text-yellow-700",
  }

  return (
    <div className="space-y-3">
      {SAMPLE_ACTIONS.map((action) => (
        <div
          key={action.id}
          className={`bg-white border rounded-xl p-4 transition-opacity ${done.has(action.id) ? "opacity-50" : ""}`}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${priorityColors[action.priority]}`}>
                  {action.priority === "high" ? "Ưu tiên cao" : "Ưu tiên TB"}
                </span>
                <span className="text-xs text-green-700 bg-green-50 px-2 py-0.5 rounded-full font-medium">
                  {action.impact}
                </span>
              </div>
              <p className="text-sm font-semibold text-gray-900">{action.title}</p>
              <p className="text-xs text-gray-500">{action.desc}</p>
            </div>
            <button
              onClick={() => setDone((prev) => new Set([...prev, action.id]))}
              disabled={done.has(action.id)}
              className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-50 whitespace-nowrap transition-colors"
            >
              {done.has(action.id) ? "✅ Xong" : "Đánh dấu"}
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Tổng quan" },
  { id: "skus", label: "SKUs" },
  { id: "creators", label: "Creators" },
  { id: "actions", label: "Hành động" },
]

function DemoDetails() {
  const [activeTab, setActiveTab] = useState<Tab>("overview")
  const [showWowBanner, setShowWowBanner] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    // Show wow banner after 20 seconds if not already shown this session
    if (typeof window !== "undefined") {
      const alreadyShown = sessionStorage.getItem("tikai_demo_wow_shown")
      if (!alreadyShown) {
        timerRef.current = setTimeout(() => {
          setShowWowBanner(true)
          sessionStorage.setItem("tikai_demo_wow_shown", "1")
        }, 20000)
      }
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Demo banner */}
      <div className="bg-amber-50 border-b border-amber-200 px-6 py-3 flex items-center justify-between">
        <span className="text-sm text-amber-800">
          📊 Đây là shop demo — dữ liệu minh họa, không phải shop thật của bạn.
        </span>
        <a
          href="/login?redirect=/import"
          className="text-sm font-medium text-amber-900 bg-amber-200 hover:bg-amber-300 px-4 py-1.5 rounded-lg transition-colors"
        >
          Dùng data thật của tôi →
        </a>
      </div>

      {/* WowScreen banner — shown after 20 seconds, sessionStorage-gated */}
      {showWowBanner && (
        <div className="bg-gray-900 text-white px-6 py-4 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold">Đây là data mẫu. Nhập data shop thật của bạn để thấy insight thật.</p>
            <p className="text-xs text-gray-400 mt-0.5">Tikai phân tích trong 60 giây — miễn phí.</p>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            <a
              href="/"
              className="bg-white text-gray-900 text-sm font-medium px-4 py-2 rounded-lg hover:bg-gray-100 transition-colors whitespace-nowrap"
            >
              Bắt đầu miễn phí →
            </a>
            <button
              onClick={() => setShowWowBanner(false)}
              className="text-gray-400 hover:text-white text-sm transition-colors"
              aria-label="Đóng"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      <main className="max-w-2xl mx-auto px-6 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">Ví dụ: Shop Mỹ Phẩm (Demo)</h1>
          <span className="text-xs text-gray-400 bg-gray-100 px-3 py-1 rounded-full">
            01/05 – 14/05/2026
          </span>
        </div>

        {/* Tab navigation */}
        <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 text-sm font-medium py-2 rounded-lg transition-colors ${
                activeTab === tab.id
                  ? "bg-white shadow-sm text-gray-900"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === "overview" && <OverviewTab />}
        {activeTab === "skus" && <SKUsTab />}
        {activeTab === "creators" && <CreatorsTab />}
        {activeTab === "actions" && <ActionsTab />}

        {/* CTA */}
        <div className="bg-gray-900 text-white rounded-2xl p-6 text-center space-y-3">
          <p className="font-semibold">Shop của bạn đang lãi hay lỗ thực sự?</p>
          <p className="text-sm text-gray-300">
            Upload file TikTok Shop hoặc Shopee — Tikai phân tích P&L toàn bộ miễn phí trong 60 giây.
          </p>
          <a
            href="/login?redirect=/import"
            className="inline-block bg-white text-gray-900 text-sm font-medium px-6 py-2.5 rounded-xl hover:bg-gray-100 transition-colors"
          >
            Phân tích shop của tôi →
          </a>
        </div>
      </main>
    </div>
  )
}

export default function DemoPage() {
  const [showDetails, setShowDetails] = useState(false)

  if (!showDetails) {
    return (
      <WowScreen
        insight={DEMO_INSIGHT}
        isDemo={true}
        onContinue={() => setShowDetails(true)}
      />
    )
  }

  return <DemoDetails />
}
