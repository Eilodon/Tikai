"use client"
import { useState } from "react"
import { useLiveStreams, useCreateLiveStream, useUpdateLiveStreamResults } from "@/hooks/useApi"
import { formatVND, formatROI, type LiveStreamResponse, type LiveStreamCreateRequest } from "@/lib/api"

export default function LiveStreamPage() {
  const { data: streams, isLoading } = useLiveStreams()
  const createMutation = useCreateLiveStream()
  const [showForm, setShowForm] = useState(false)

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Live Stream ROI</h1>
          <p className="text-sm text-gray-500 mt-1">
            Tính toán chi phí và hiệu quả mỗi buổi live
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          + Thêm live
        </button>
      </div>

      {showForm && (
        <LiveStreamForm
          onSubmit={async (data) => {
            await createMutation.mutateAsync(data)
            setShowForm(false)
          }}
          onCancel={() => setShowForm(false)}
          loading={createMutation.isPending}
        />
      )}

      {isLoading && (
        <div className="space-y-3">
          {[1, 2].map(i => (
            <div key={i} className="h-24 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      )}

      {!isLoading && streams?.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-4xl mb-3">📡</p>
          <p className="text-sm">Chưa có dữ liệu live stream.</p>
          <p className="text-xs mt-1">Thêm live đầu tiên để tính ROI.</p>
        </div>
      )}

      <div className="space-y-3">
        {streams?.map(stream => (
          <LiveStreamCard key={stream.id} stream={stream} />
        ))}
      </div>
    </div>
  )
}

function LiveStreamCard({ stream }: { stream: LiveStreamResponse }) {
  const updateResults = useUpdateLiveStreamResults()
  const [editing, setEditing] = useState(false)
  const [gmv, setGmv] = useState(stream.attributed_gmv ?? "")

  const roi = stream.live_roi ? parseFloat(stream.live_roi) : null
  const roiColor = roi === null ? "text-gray-400"
    : roi >= 10 ? "text-green-600"
    : roi >= 3 ? "text-amber-600"
    : "text-red-600"

  return (
    <div className="bg-white border rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium text-sm">📡 Live {stream.livestream_date}</p>
          <p className="text-xs text-gray-500">{stream.duration_minutes} phút</p>
        </div>
        <div className="text-right">
          <p className={`text-lg font-bold ${roiColor}`}>
            {roi !== null ? `${formatROI(stream.live_roi)} ROI` : "Chưa cập nhật"}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="bg-gray-50 rounded-lg p-2">
          <p className="text-xs text-gray-500">Tổng chi phí</p>
          <p className="font-medium">{formatVND(stream.total_cost)}</p>
        </div>
        <div className="bg-gray-50 rounded-lg p-2">
          <p className="text-xs text-gray-500">GMV trong live</p>
          <p className="font-medium">{stream.attributed_gmv ? formatVND(stream.attributed_gmv) : "—"}</p>
        </div>
      </div>

      {stream.notes && (
        <p className="text-xs text-gray-500">{stream.notes}</p>
      )}

      {!stream.attributed_gmv && (
        <div className="flex gap-2">
          {!editing ? (
            <button
              onClick={() => setEditing(true)}
              className="text-blue-600 text-xs hover:underline"
            >
              Cập nhật kết quả →
            </button>
          ) : (
            <div className="flex gap-2 items-center w-full">
              <input
                type="number"
                placeholder="GMV trong live (₫)"
                value={gmv}
                onChange={e => setGmv(e.target.value)}
                className="border rounded px-2 py-1 text-xs flex-1"
              />
              <button
                onClick={async () => {
                  await updateResults.mutateAsync({
                    id: stream.id,
                    data: { attributed_gmv: gmv },
                  })
                  setEditing(false)
                }}
                className="bg-blue-600 text-white text-xs px-3 py-1 rounded"
              >
                Lưu
              </button>
              <button onClick={() => setEditing(false)} className="text-gray-400 text-xs">Huỷ</button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function LiveStreamForm({
  onSubmit,
  onCancel,
  loading,
}: {
  onSubmit: (data: LiveStreamCreateRequest) => void
  onCancel: () => void
  loading: boolean
}) {
  const [form, setForm] = useState<LiveStreamCreateRequest>({
    livestream_date: new Date().toISOString().split("T")[0],
    host_cost: "0",
    studio_cost: "0",
    product_sample_cost: "0",
    ads_cost: "0",
    other_cost: "0",
  })

  const fields = [
    { key: "host_cost", label: "Host/MC" },
    { key: "studio_cost", label: "Studio & props" },
    { key: "product_sample_cost", label: "Hàng mẫu" },
    { key: "ads_cost", label: "Quảng cáo" },
    { key: "other_cost", label: "Khác" },
  ] as const

  const totalCost = fields.reduce((sum, f) => sum + parseFloat((form as any)[f.key] || "0"), 0)

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 space-y-4">
      <h2 className="font-medium text-sm">Thêm buổi live mới</h2>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-600">Ngày live</label>
          <input
            type="date"
            value={form.livestream_date}
            onChange={e => setForm({...form, livestream_date: e.target.value})}
            className="w-full border rounded px-2 py-1.5 text-sm mt-1"
          />
        </div>
        <div>
          <label className="text-xs text-gray-600">Thời lượng (phút)</label>
          <input
            type="number"
            placeholder="90"
            onChange={e => setForm({...form, duration_minutes: parseInt(e.target.value) || 0})}
            className="w-full border rounded px-2 py-1.5 text-sm mt-1"
          />
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium text-gray-600">Chi phí (₫)</p>
        {fields.map(({ key, label }) => (
          <div key={key} className="flex items-center gap-2">
            <span className="text-xs text-gray-500 w-28">{label}</span>
            <input
              type="number"
              placeholder="0"
              value={(form as any)[key]}
              onChange={e => setForm({...form, [key]: e.target.value})}
              className="border rounded px-2 py-1 text-sm flex-1"
            />
          </div>
        ))}
        <div className="flex items-center gap-2 pt-1 border-t">
          <span className="text-xs font-medium w-28">Tổng chi phí</span>
          <span className="text-sm font-bold text-blue-600">
            {new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 }).format(totalCost)}
          </span>
        </div>
      </div>

      <div>
        <label className="text-xs text-gray-600">Ghi chú</label>
        <input
          type="text"
          placeholder="VD: Flash sale sản phẩm mới, collab @beauty_linh"
          onChange={e => setForm({...form, notes: e.target.value})}
          className="w-full border rounded px-2 py-1.5 text-sm mt-1"
        />
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => onSubmit(form)}
          disabled={loading}
          className="bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Đang lưu..." : "Lưu buổi live"}
        </button>
        <button onClick={onCancel} className="text-gray-500 text-sm px-4 py-2">Huỷ</button>
      </div>
    </div>
  )
}
