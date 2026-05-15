import { SkeletonCard } from "@/components/common/MoneyDisplay"

export default function Loading() {
  return (
    <div className="space-y-3">
      {[1, 2, 3, 4].map(i => <SkeletonCard key={i} lines={2} />)}
    </div>
  )
}
