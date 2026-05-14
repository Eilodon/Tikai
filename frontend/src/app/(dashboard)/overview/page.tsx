"use client"
import { useState } from "react"
import {
  useLatestInsight,
  useActions,
  useCompleteAction,
  useDismissAction,
  useInsightHistory,
  useRecomputeInsight,
  useShop,
} from "@/hooks/useApi"
import { PLSummary } from "@/components/insights/PLSummary"
import { LeakList } from "@/components/insights/LeakList"
import { SKUTable } from "@/components/insights/SKUTable"
import { CreatorTable } from "@/components/insights/CreatorTable"
import { CashFlowTimeline } from "@/components/insights/CashFlowTimeline"
import { IndustryBenchmark } from "@/components/insights/IndustryBenchmark"
import { ActionCard } from "@/components/actions/ActionCard"
import { WeeklyReceipt } from "@/components/receipt/WeeklyReceipt"
import { SkeletonCard } from "@/components/common/MoneyDisplay"

export default function OverviewPage() {
  const { data: insight, isLoading: insightLoading, error: insightError } = useLatestInsight()
  const { data: history } = useInsightHistory(4)
  const { data: actionsData, isLoading: actionsLoading } = useActions()
  const { data: shop } = useShop()
  const complete = useCompleteAction()
  const dismiss  = useDismissAction()
  const recompute = useRecomputeInsight()
  const [recomputeError, setRecomputeError] = useState<string | null>(null)

  if (insightLoading) return <PageSkeleton />

  if (insightError || !insight) {
    return (
      <div className="text-center py-16">
        <p className="text-gray-500 mb-2 text-sm">Chưa có dữ liệu.</p>
        <a href="/import" className="text-blue-600 text-sm hover:underline">
          Import file từ TikTok Shop →
        </a>
      </div>
    )
  }

  const pendingActions = actionsData?.items?.filter((a) => a.status === "pending") ?? []

  // Week-over-week deltas
  const prevInsight = history && history.length >= 2 ? history[history.length - 2] : null
  const wowGmv = prevInsight ? calcWoW(insight.gmv_total, prevInsight.gmv_total) : null
  const wowNR = prevInsight ? calcWoW(insight.net_revenue, prevInsight.net_revenue) : null

  // FIX HIGH-V2-6: only show recompute button for Pro+ tiers
  const isPro = shop?.subscription_tier === "pro" || shop?.subscription_tier === "business"

  const handleRecompute = async () => {
    setRecomputeError(null)
    try {
      await recompute.mutateAsync(undefined)
    } catch (err: any) {
      // FIX MED-V2-9: handle 402/409 from feature gate / lock gracefully
      if (err?.status === 402) {
        setRecomputeError(err?.message ?? "Tính năng này cần gói Pro.")
      } else if (err?.status === 409) {
        setRecomputeError("Đang có một tính toán khác. Vui lòng thử lại sau 5 giây.")
      } else {
        setRecomputeError(err?.message ?? "Có lỗi xảy ra. Vui lòng thử lại.")
      }
    }
  }

  return (
    <div className="space-y-6">
      {/* COGS Nudge Banner — show when fewer than 50% SKUs have COGS */}
      {insight?.is_net_revenue_mode && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-4 flex items-start gap-3">
          <span className="text-lg mt-0.5">💡</span>
          <div className="flex-1">
            <p className="text-sm font-medium text-amber-900">
              Đang hiển thị Net Revenue — chưa có Margin
            </p>
            <p className="text-xs text-amber-700 mt-0.5">
              Nhập giá vốn (COGS) để Tikai tính được margin chính xác và phát hiện SKU lỗ.
              {insight.cogs_coverage_pct && parseFloat(insight.cogs_coverage_pct) > 0
                ? ` (${Math.round(parseFloat(insight.cogs_coverage_pct) * 100)}% SKU đã có giá vốn)`
                : ""}
            </p>
          </div>
          <a href="/settings"
            className="text-xs font-medium text-amber-800 border border-amber-300
                       rounded-lg px-3 py-1.5 hover:bg-amber-100 whitespace-nowrap transition-colors">
            Nhập giá vốn →
          </a>
        </div>
      )}

      {insight.is_partial_period && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm">
          📅 Bạn đang xem <strong>{insight.days_in_period} ngày</strong> (không phải full tuần).
          {" "}Import lại vào cuối tuần để xem performance đầy đủ.
        </div>
      )}

      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          {insight.period_start} — {insight.period_end}
        </p>
        {(wowGmv !== null || wowNR !== null) && (
          <div className="flex gap-3 text-xs">
            {wowGmv !== null && (
              <span className={wowGmv >= 0 ? "text-green-600" : "text-red-600"}>
                GMV {wowGmv >= 0 ? "▲" : "▼"} {Math.abs(wowGmv).toFixed(1)}% WoW
              </span>
            )}
            {wowNR !== null && (
              <span className={wowNR >= 0 ? "text-green-600" : "text-red-600"}>
                NR {wowNR >= 0 ? "▲" : "▼"} {Math.abs(wowNR).toFixed(1)}% WoW
              </span>
            )}
          </div>
        )}
      </div>

      <PLSummary insight={insight} />
      <LeakList leaks={insight.top_leaks} />

      {!actionsLoading && pendingActions.length > 0 && (
        <div>
          <h2 className="font-semibold text-sm mb-3">
            Hành động hôm nay ({pendingActions.length})
          </h2>
          <div className="space-y-3">
            {pendingActions.slice(0, 3).map((action) => (
              <ActionCard
                key={action.id}
                action={action}
                onComplete={() => complete.mutate(action.id.toString())}
                onDismiss={() => dismiss.mutate(action.id.toString())}
                completing={complete.isPending && complete.variables === action.id.toString()}
              />
            ))}
          </div>
        </div>
      )}

      <SKUTable insight={insight} />

      <CreatorTable insight={insight} />

      <CashFlowTimeline insight={insight} />

      <IndustryBenchmark snapshotId={insight.id} />

      {/* Re-analysis — Pro+ only */}
      {isPro ? (
        <div className="flex flex-col items-center gap-2">
          <button
            onClick={handleRecompute}
            disabled={recompute.isPending}
            className="text-xs text-blue-600 hover:underline disabled:opacity-50"
          >
            {recompute.isPending ? "Đang tính lại..." : "🔄 Tính lại với COGS mới nhất"}
          </button>
          {recomputeError && <p className="text-xs text-red-600">{recomputeError}</p>}
        </div>
      ) : (
        <div className="flex justify-center">
          <a href="/settings/billing" className="text-xs text-gray-400 hover:text-blue-600 hover:underline">
            🔒 Tính lại với COGS mới — nâng cấp Pro
          </a>
        </div>
      )}

      <WeeklyReceipt />
    </div>
  )
}

function calcWoW(current: string, prev: string): number {
  const c = parseFloat(current)
  const p = parseFloat(prev)
  if (!p || p === 0) return 0
  return ((c - p) / p) * 100
}

function PageSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-4 bg-gray-200 rounded w-40 animate-pulse" />
      <SkeletonCard lines={4} />
      <SkeletonCard lines={3} />
    </div>
  )
}
