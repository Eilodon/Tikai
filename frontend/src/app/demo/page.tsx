"use client"
import { useState } from "react"
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

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-amber-50 border-b border-amber-200 px-6 py-3 flex items-center justify-between">
        <span className="text-sm text-amber-800">
          📊 Đây là shop demo — dữ liệu minh họa, không phải shop thật của bạn.
        </span>
        <a href="/login?redirect=/import"
          className="text-sm font-medium text-amber-900 bg-amber-200 hover:bg-amber-300 px-4 py-1.5 rounded-lg transition-colors">
          Dùng data thật của tôi →
        </a>
      </div>

      <main className="max-w-2xl mx-auto px-6 py-8 space-y-6">
        <h1 className="text-xl font-semibold">Ví dụ: Shop Mỹ Phẩm (Demo)</h1>

        {/* P&L Summary */}
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "GMV", value: "420.000.000 ₫" },
            { label: "Net Revenue", value: "28.350.000 ₫" },
            { label: "Margin", value: "6.7%" },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white border rounded-xl p-4 text-center">
              <p className="text-xs text-gray-500 mb-1">{label}</p>
              <p className="font-bold text-gray-900">{value}</p>
            </div>
          ))}
        </div>

        {/* Leaks */}
        <div className="bg-white border rounded-xl p-5 space-y-3">
          <h2 className="font-semibold text-sm">Phát hiện rò rỉ ({DEMO_INSIGHT.top_leaks.length} điểm)</h2>
          {DEMO_INSIGHT.top_leaks.map((leak) => (
            <div key={leak.id} className="flex items-center justify-between border-b last:border-0 pb-3 last:pb-0">
              <div>
                <p className="text-sm font-medium">{leak.name}</p>
                <p className="text-xs text-gray-500 mt-0.5 capitalize">{leak.reason.replace(/_/g, " ")}</p>
              </div>
              <p className="text-red-600 font-semibold text-sm">−{parseInt(leak.estimated_loss).toLocaleString("vi-VN")} ₫</p>
            </div>
          ))}
        </div>

        {/* CTA */}
        <div className="bg-gray-900 text-white rounded-2xl p-6 text-center space-y-3">
          <p className="font-semibold">Shop của bạn đang lãi hay lỗ thực sự?</p>
          <p className="text-sm text-gray-300">
            Upload file TikTok Shop hoặc Shopee — Tikai phân tích P&L toàn bộ miễn phí trong 60 giây.
          </p>
          <a href="/login?redirect=/import"
            className="inline-block bg-white text-gray-900 text-sm font-medium px-6 py-2.5 rounded-xl hover:bg-gray-100 transition-colors">
            Phân tích shop của tôi →
          </a>
        </div>
      </main>
    </div>
  )
}
