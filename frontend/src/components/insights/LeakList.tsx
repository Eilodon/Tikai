import { LeakItem, formatVND } from "@/lib/api"
import { ConfidenceBadge } from "../actions/ConfidenceBadge"

const REASON_LABEL: Record<string, string> = {
  voucher_high:               "Voucher + phí cao hơn margin",
  affiliate_high:             "Hoa hồng affiliate quá cao",
  cogs_missing:               "Chưa có giá vốn",
  refund_spike:               "Tỉ lệ hoàn cao bất thường",
  commission_exceeds_margin:  "Hoa hồng creator > contribution",
}

export function LeakList({ leaks }: { leaks: LeakItem[] }) {
  if (leaks.length === 0) return null

  return (
    <div className="bg-white rounded-xl border p-5">
      <h2 className="font-semibold mb-3 text-sm">Vấn đề cần xử lý</h2>
      <div className="space-y-0">
        {leaks.map((leak, i) => (
          <div
            key={leak.id}
            className="flex items-center justify-between py-3 border-b last:border-0"
          >
            <div className="flex items-start gap-3">
              <span className="text-xs text-gray-400 w-4 flex-shrink-0 mt-0.5">{i + 1}.</span>
              <div>
                <p className="font-medium text-sm">{leak.name}</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {REASON_LABEL[leak.reason] ?? leak.reason}
                </p>
              </div>
            </div>
            <div className="text-right flex-shrink-0 ml-4">
              <p className="text-sm font-semibold text-red-600">
                {leak.estimated_loss !== "0.0000" && leak.estimated_loss !== "0"
                  ? `~${formatVND(leak.estimated_loss)}`
                  : "?"}
              </p>
              <ConfidenceBadge confidence={leak.confidence} className="mt-1" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
