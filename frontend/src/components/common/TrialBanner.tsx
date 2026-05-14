"use client"
import { useShop } from "@/hooks/useApi"

export function TrialBanner() {
  const { data: shop } = useShop()

  if (!shop || shop.subscription_tier !== "pro_trial") return null

  const expiresAt = (shop as any).trial_expires_at
  if (!expiresAt) return null

  const daysLeft = Math.max(
    0,
    Math.ceil((new Date(expiresAt).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
  )

  if (daysLeft <= 0) return null

  const isUrgent = daysLeft <= 3

  return (
    <div className={`px-6 py-2 text-xs flex items-center justify-between ${
      isUrgent ? "bg-red-600 text-white" : "bg-blue-600 text-white"
    }`}>
      <span>
        {isUrgent ? "⚠ " : "🎉 "}
        Bạn đang dùng thử Pro — còn <strong>{daysLeft} ngày</strong>
      </span>
      <a
        href="mailto:hi@tikai.vn?subject=Nâng cấp Pro — 99k/tháng"
        className="underline font-medium hover:opacity-80"
      >
        Nâng cấp ngay →
      </a>
    </div>
  )
}
