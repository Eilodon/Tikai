"use client"
import { InsightSnapshotResponse, formatVND } from "@/lib/api"

const REASON_TEXT: Record<string, string> = {
  voucher_high: "chi phí voucher quá cao",
  affiliate_high: "hoa hồng affiliate ăn vào margin",
  cogs_missing: "chưa có giá vốn — margin đang bị ẩn",
  refund_spike: "tỷ lệ hoàn hàng cao bất thường",
  commission_exceeds_margin: "hoa hồng vượt margin thực",
}

function deriveInsight(insight: InsightSnapshotResponse): { key: string; action: string } | null {
  const topLeak = insight.top_leaks[0]
  const criticalSkus = insight.top_skus.filter((s) => s.health_status === "critical")
  const losingCreators = insight.top_creators.filter((c) => c.performance_label === "losing")
  const cogsPct = parseFloat(insight.cogs_coverage_pct)

  if (cogsPct < 0.3 && insight.is_net_revenue_mode) {
    return {
      key: `Chưa có giá vốn cho ${Math.round((1 - cogsPct) * 100)}% SKU — margin thực đang bị ẩn`,
      action: "Vào Cài đặt → nhập giá vốn để Tikai tính margin chính xác",
    }
  }
  if (topLeak && parseFloat(topLeak.estimated_loss) > 0) {
    return {
      key: `${topLeak.name} rò rỉ ${formatVND(topLeak.estimated_loss)}/kỳ do ${REASON_TEXT[topLeak.reason] ?? topLeak.reason}`,
      action: topLeak.can_act_now
        ? "Xem bảng SKU / Creator bên dưới để tối ưu ngay hôm nay"
        : "Nhập giá vốn để mở khóa chi tiết và cách tối ưu",
    }
  }
  if (criticalSkus.length > 0) {
    return {
      key: `${criticalSkus.length} SKU đang ở trạng thái critical cần xử lý`,
      action: `Mở rộng bảng SKU bên dưới để xem chi tiết ${criticalSkus[0].sku_name}`,
    }
  }
  if (losingCreators.length > 0) {
    return {
      key: `${losingCreators.length} creator đang tốn hơn doanh thu tạo ra`,
      action: "Xem bảng Creator bên dưới → điều chỉnh mức hoa hồng",
    }
  }
  return null
}

export function WowInsightBanner({ insight }: { insight: InsightSnapshotResponse }) {
  const insight_data = deriveInsight(insight)
  if (!insight_data) return null

  return (
    <div className="bg-gradient-to-r from-gray-900 to-gray-700 rounded-xl p-5 text-white">
      <p className="text-xs text-gray-400 uppercase tracking-wide mb-1.5">Tikai phân tích</p>
      <p className="font-medium leading-snug">{insight_data.key}</p>
      <div className="mt-3 bg-white/10 rounded-lg px-4 py-2.5">
        <p className="text-xs text-gray-300 mb-0.5">Làm ngay hôm nay</p>
        <p className="text-sm">{insight_data.action}</p>
      </div>
    </div>
  )
}
