"use client"
import { useState } from "react"
import { useCreators, useSyncCreators, useUpdateCreator } from "@/hooks/useApi"
import { formatVND, type CreatorProfileResponse } from "@/lib/api"

const PERFORMANCE_LABELS: Record<string, { label: string; color: string }> = {
  star:       { label: "⭐ Star",      color: "bg-yellow-100 text-yellow-800" },
  break_even: { label: "Hòa vốn",      color: "bg-gray-100 text-gray-700" },
  losing:     { label: "Đang lỗ",      color: "bg-red-100 text-red-700" },
}

const STATUS_LABELS: Record<string, string> = {
  active:      "Đang hợp tác",
  paused:      "Tạm dừng",
  blacklisted: "Blacklist",
  vip:         "VIP",
}

export default function CreatorsPage() {
  const [filter, setFilter] = useState<{ performance_label?: string; status?: string }>({})
  const { data: creators, isLoading, error } = useCreators(filter)
  const sync = useSyncCreators()

  if (error && (error as any).status === 402) {
    return (
      <div className="text-center py-16 max-w-md mx-auto">
        <p className="text-4xl mb-3">🔒</p>
        <h2 className="text-lg font-semibold">Creator CRM cần gói Pro</h2>
        <p className="text-sm text-gray-500 mt-2">{(error as any).message}</p>
        <a href="/settings/billing"
          className="inline-block mt-4 bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700">
          Nâng cấp Pro →
        </a>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Creators</h1>
          <p className="text-sm text-gray-500 mt-1">
            Hiệu suất và ROI từng creator dựa trên data import gần nhất
          </p>
        </div>
        <button
          onClick={() => sync.mutate()}
          disabled={sync.isPending}
          className="text-xs text-blue-600 hover:underline disabled:opacity-50"
        >
          {sync.isPending ? "Đang đồng bộ..." : "↻ Đồng bộ từ snapshot mới nhất"}
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {["all", "star", "break_even", "losing"].map((label) => (
          <button
            key={label}
            onClick={() => setFilter(label === "all"
              ? {}
              : { ...filter, performance_label: label })}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              (label === "all" && !filter.performance_label) || filter.performance_label === label
                ? "bg-gray-900 text-white border-gray-900"
                : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
            }`}
          >
            {label === "all" ? "Tất cả" : PERFORMANCE_LABELS[label]?.label ?? label}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="space-y-3">{[1, 2, 3].map(i => <div key={i} className="h-20 bg-gray-100 rounded-xl animate-pulse" />)}</div>
      )}

      {!isLoading && (!creators || creators.length === 0) && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-4xl mb-3">📊</p>
          <p className="text-sm">Chưa có creator data.</p>
          <p className="text-xs mt-1">Import file order có creator info, hoặc bấm "Đồng bộ" để pull từ snapshot.</p>
        </div>
      )}

      <div className="space-y-2">
        {creators?.map((c) => <CreatorRow key={c.id} creator={c} />)}
      </div>
    </div>
  )
}

function CreatorRow({ creator }: { creator: CreatorProfileResponse }) {
  const [open, setOpen] = useState(false)
  const perf = PERFORMANCE_LABELS[creator.performance_label]
  const efficiency = creator.revenue_efficiency_30d ? parseFloat(creator.revenue_efficiency_30d) : null

  return (
    <div className="bg-white border rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors text-left"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <p className="font-medium text-sm truncate">{creator.creator_name}</p>
            <span className={`text-xs px-2 py-0.5 rounded-full ${perf?.color ?? "bg-gray-100"}`}>
              {perf?.label ?? creator.performance_label}
            </span>
            {creator.status !== "active" && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                {STATUS_LABELS[creator.status] ?? creator.status}
              </span>
            )}
          </div>
          <div className="flex gap-4 text-xs text-gray-500">
            <span>GMV: <strong className="text-gray-900">{formatVND(creator.gmv_30d)}</strong></span>
            <span>Hoa hồng: <strong className="text-gray-900">{formatVND(creator.total_commission_paid)}</strong></span>
            {efficiency !== null && (
              <span>Hiệu suất: <strong className={efficiency < 1 ? "text-red-600" : "text-gray-900"}>{efficiency.toFixed(2)}x</strong></span>
            )}
          </div>
        </div>
        <span className="text-gray-400 text-xs ml-2">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <CreatorDetail creator={creator} />
      )}
    </div>
  )
}

function CreatorDetail({ creator }: { creator: CreatorProfileResponse }) {
  const update = useUpdateCreator()
  const [note, setNote] = useState(creator.internal_note ?? "")
  const [zalo, setZalo] = useState(creator.contact_zalo ?? "")
  const [status, setStatus] = useState(creator.status)
  const wastedComm = parseFloat(creator.commission_on_refunded_orders)

  async function handleSave() {
    await update.mutateAsync({
      profileId: creator.id,
      data: {
        internal_note: note,
        contact_zalo: zalo,
        status,
      },
    })
  }

  return (
    <div className="border-t bg-gray-50 px-4 py-4 space-y-4">
      {wastedComm > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-xs">
          <p className="text-red-700">
            <strong>{formatVND(creator.commission_on_refunded_orders)}</strong> hoa hồng đã trả cho creator này
            nhưng đơn bị hoàn sau đó — TikTok không thu hồi.
          </p>
        </div>
      )}

      {creator.suggested_max_commission && (
        <p className="text-xs text-gray-600">
          Hoa hồng tối đa gợi ý: <strong className="text-gray-900">{(parseFloat(creator.suggested_max_commission) * 100).toFixed(1)}%</strong>
        </p>
      )}

      <div className="space-y-2">
        <div>
          <label className="text-xs font-medium text-gray-700 block mb-1">Trạng thái</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as any)}
            className="text-sm border rounded-lg px-2.5 py-1.5"
          >
            <option value="active">Đang hợp tác</option>
            <option value="paused">Tạm dừng</option>
            <option value="blacklisted">Blacklist</option>
            <option value="vip">VIP</option>
          </select>
        </div>
        <div>
          <label className="text-xs font-medium text-gray-700 block mb-1">Zalo</label>
          <input
            type="text"
            value={zalo}
            onChange={(e) => setZalo(e.target.value)}
            placeholder="0901234567"
            className="text-sm border rounded-lg px-2.5 py-1.5 w-full max-w-xs"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-gray-700 block mb-1">Ghi chú</label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            maxLength={1000}
            className="text-sm border rounded-lg px-2.5 py-1.5 w-full"
            placeholder="Ghi chú nội bộ về creator này..."
          />
        </div>
        <button
          onClick={handleSave}
          disabled={update.isPending}
          className="bg-blue-600 text-white text-xs px-3 py-1.5 rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {update.isPending ? "Đang lưu..." : "Lưu"}
        </button>
      </div>
    </div>
  )
}
