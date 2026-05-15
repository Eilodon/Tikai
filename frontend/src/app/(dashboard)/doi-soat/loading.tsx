import { SkeletonCard } from "@/components/common/MoneyDisplay"

export default function Loading() {
  return (
    <div className="space-y-6">
      <SkeletonCard lines={3} />
      <SkeletonCard lines={4} />
    </div>
  )
}
