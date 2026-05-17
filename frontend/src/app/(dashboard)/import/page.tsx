"use client"
import { useState, useCallback, useEffect } from "react"
import { useImportStatus } from "@/hooks/useApi"
import { importsApi, cogsApi, ImportSessionResponse } from "@/lib/api"
import { getAuthToken } from "@/lib/supabase"

function ExportGuide() {
  const [open, setOpen] = useState(false)
  return (
    <div className="border rounded-xl overflow-hidden text-sm">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
      >
        <span className="font-medium text-gray-700">Hướng dẫn xuất file từ Seller Center</span>
        <span className="text-gray-400">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="px-4 py-4 grid sm:grid-cols-2 gap-6">
          <div>
            <p className="font-semibold text-gray-800 mb-2">TikTok Shop</p>
            <ol className="list-decimal list-inside space-y-1.5 text-gray-600">
              <li>Vào <strong>Seller Center</strong> → <strong>Quản lý đơn hàng</strong></li>
              <li>Nhấn <strong>Xuất dữ liệu</strong> (Export Orders)</li>
              <li>Chọn khoảng thời gian cần phân tích</li>
              <li>Tải file <code className="bg-gray-100 px-1 rounded">.xlsx</code> về máy</li>
              <li>Upload lên đây</li>
            </ol>
          </div>
          <div>
            <p className="font-semibold text-gray-800 mb-2">Shopee</p>
            <ol className="list-decimal list-inside space-y-1.5 text-gray-600">
              <li>Vào <strong>Seller Center</strong> → <strong>Đơn hàng</strong> → <strong>Tra cứu đơn hàng</strong></li>
              <li>Chọn khoảng thời gian cần phân tích</li>
              <li>Nhấn <strong>Xuất file Excel</strong> (Export)</li>
              <li>Upload lên đây</li>
            </ol>
          </div>
        </div>
      )}
    </div>
  )
}

export default function ImportPage() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [showCogsStep, setShowCogsStep] = useState(false)
  const [topSkusForCogs, setTopSkusForCogs] = useState<Array<{ sku_id: string; sku_name: string; gmv: string }>>([])

  const [token, setToken] = useState<string | null>(null)
  const { data: session } = useImportStatus(sessionId)
  
  useEffect(() => { getAuthToken().then(t => setToken(t)) }, [])

  const handleFile = useCallback(async (file: File) => {
    setUploadError(null)
    setUploading(true)
    try {
      const token = await getAuthToken()
      if (!token) throw new Error("Vui lòng đăng nhập lại.")
      const result = await importsApi.upload(token, file)
      setSessionId(result.id.toString())
    } catch (err: any) {
      setUploadError(err?.message ?? "Upload thất bại. Vui lòng thử lại.")
    } finally {
      setUploading(false)
    }
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      const file = e.dataTransfer.files[0]
      if (file) handleFile(file)
    },
    [handleFile]
  )

  return (
    <div className="space-y-6 max-w-xl">
      <div>
        <h1 className="text-xl font-semibold">Import dữ liệu</h1>
        <p className="text-sm text-gray-500 mt-1">Upload file Order Export từ TikTok Shop hoặc Shopee Seller Center.</p>
      </div>

      <ExportGuide />

      {/* Dropzone */}
      {!sessionId && (
        <label
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          className="block border-2 border-dashed border-gray-300 rounded-xl p-10 text-center cursor-pointer hover:border-blue-400 transition-colors"
        >
          <input
            type="file"
            accept=".csv,.xlsx,.xls"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
          {uploading ? (
            <p className="text-gray-500">Đang upload...</p>
          ) : (
            <>
              <p className="font-medium">Kéo thả file vào đây</p>
              <p className="text-sm text-gray-400 mt-1">hoặc click để chọn file (.csv, .xlsx)</p>
            </>
          )}
        </label>
      )}

      {uploadError && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
          {uploadError}
        </div>
      )}

      {/* Processing Status */}
      {session && <ImportStatus session={session} onCompletedWithTopSkus={(skus) => {
        setTopSkusForCogs(skus)
        if (skus.length > 0) setShowCogsStep(true)
      }} />}
      {showCogsStep && token && (
        session?.status === "completed" || session?.status === "completed_with_caveats"
      ) && (
        <PostImportCOGSPrompt
          token={token}
          topSkus={topSkusForCogs}
          onSkip={() => setShowCogsStep(false)}
        />
      )}
    </div>
  )
}

// Platform display labels
const PLATFORM_LABELS: Record<string, string> = {
  "order_export": "TikTok Shop",
  "shopee_order_export": "Shopee",
  "shopee_order_export_vi": "Shopee",
  "transaction_export": "TikTok Giao Dịch",
  "settlement_export": "TikTok Thanh Toán",
  "unknown": "Không xác định",
}

// Post-import COGS micro-step
function PostImportCOGSPrompt({
  token,
  topSkus,
  onSkip,
}: {
  token: string
  topSkus: { sku_id: string; sku_name: string; gmv: string }[]
  onSkip: () => void
}) {
  const [rows, setRows] = useState(
    topSkus.slice(0, 5).map((s) => ({ ...s, cogs: "" }))
  )
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)

  const filledRows = rows.filter((r) => r.cogs !== "" && parseFloat(r.cogs) > 0)

  async function handleSave() {
    if (filledRows.length === 0) { onSkip(); return }
    setSaving(true)
    try {
      await cogsApi.upsert(token, filledRows.map((r) => ({
        sku_id: r.sku_id,
        sku_name: r.sku_name,
        cogs_per_unit: r.cogs,
      })))
      setDone(true)
    } finally {
      setSaving(false)
    }
  }

  if (done) return (
    <div className="bg-green-50 border border-green-200 rounded-xl p-6 text-center">
      <div className="text-2xl mb-2">🎉</div>
      <p className="font-semibold text-green-900">Xong! Tikai đang tính margin...</p>
      <p className="text-sm text-green-700 mt-1">Vào Overview để xem P&L với margin chính xác.</p>
      <a href="/overview"
        className="mt-4 inline-block bg-green-600 text-white text-sm
                   px-5 py-2 rounded-lg font-medium hover:bg-green-700 transition-colors">
        Xem kết quả →
      </a>
    </div>
  )

  return (
    <div className="bg-white border rounded-xl p-6 space-y-4">
      <div>
        <h3 className="font-semibold text-gray-900">
          Nhập giá vốn để xem Margin ngay — 2 phút ⚡
        </h3>
        <p className="text-sm text-gray-500 mt-1">
          Chỉ cần nhập top {rows.length} SKU theo doanh thu. Bỏ trống = bỏ qua.
        </p>
      </div>

      <div className="space-y-2">
        {rows.map((row, i) => (
          <div key={row.sku_id} className="flex items-center gap-3">
            <div className="flex-1 text-sm text-gray-700 truncate" title={row.sku_name}>
              {row.sku_name}
            </div>
            <input
              type="number" placeholder="Giá vốn (VND)" min="0"
              value={row.cogs}
              onChange={(e) => {
                const updated = [...rows]
                updated[i] = { ...updated[i], cogs: e.target.value }
                setRows(updated)
              }}
              className="w-36 text-right border rounded-lg px-2.5 py-1.5 text-sm
                         focus:outline-none focus:ring-2 focus:ring-blue-500
                         [appearance:textfield]"
            />
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3">
        <button onClick={handleSave} disabled={saving}
          className="bg-blue-600 text-white text-sm px-4 py-2 rounded-lg font-medium
                     hover:bg-blue-700 disabled:opacity-50 transition-colors">
          {saving ? "Đang lưu..." : filledRows.length > 0 ? `Lưu ${filledRows.length} giá vốn →` : "Tiếp theo →"}
        </button>
        <button onClick={onSkip} className="text-sm text-gray-400 hover:text-gray-600">
          Bỏ qua
        </button>
      </div>
    </div>
  )
}

function ImportStatus({ session, onCompletedWithTopSkus }: {
  session: ImportSessionResponse
  onCompletedWithTopSkus?: (skus: {sku_id: string; sku_name: string; gmv: string}[]) => void
}) {
  useEffect(() => {
    // P0-1 fix: pass actual top_skus_for_cogs (was always [])
    // P0-4 fix: also trigger for completed_with_caveats (Shopee partial imports)
    if (
      (session.status === "completed" || session.status === "completed_with_caveats")
      && onCompletedWithTopSkus
    ) {
      onCompletedWithTopSkus(session.top_skus_for_cogs ?? [])
    }
  }, [session.status, session.top_skus_for_cogs, onCompletedWithTopSkus])

  const statusConfig = {
    pending:                { label: "Đang chờ xử lý...",   color: "text-gray-500"  },
    processing:             { label: "Đang phân tích...",   color: "text-blue-600"  },
    completed:              { label: "Hoàn thành",           color: "text-green-600" },
    completed_with_caveats: { label: "Hoàn thành (lưu ý)", color: "text-amber-600" },
    failed:                 { label: "Có vấn đề",            color: "text-red-600"   },
  }[session.status] ?? { label: session.status, color: "text-gray-500" }

  return (
    <div className="bg-white rounded-xl border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <p className="font-medium text-sm">{session.original_filename}</p>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            session.file_type?.startsWith("shopee")
              ? "bg-orange-100 text-orange-700"
              : "bg-gray-100 text-gray-600"
          }`}>
            {PLATFORM_LABELS[session.file_type] ?? session.file_type}
          </span>
        </div>
        <span className={`text-sm font-medium ${statusConfig.color}`}>{statusConfig.label}</span>
      </div>

      {(session.status === "processing" || session.status === "pending") && (
        <div className="w-full bg-gray-100 rounded-full h-1.5">
          <div className="bg-blue-500 h-1.5 rounded-full animate-pulse w-2/3" />
        </div>
      )}

      {session.status === "completed" && (
        <div className="text-sm text-gray-600">
          ✓ Đã xử lý {session.rows_parsed} đơn hàng.{" "}
          <a href="/overview" className="text-blue-600 underline">Xem kết quả →</a>
        </div>
      )}

      {session.status === "completed_with_caveats" && (
        <div className="space-y-2">
          <div className="text-sm text-gray-600">
            ✓ Đã xử lý {session.rows_parsed} đơn hàng.
            {/* FIX BUG-NM4: only show link when it's NOT a fee_config_missing caveat */}
            {session.error_summary?.warning !== "fee_config_missing" && (
              <>{" "}<a href="/overview" className="text-blue-600 underline">Xem kết quả →</a></>
            )}
          </div>
          {session.error_summary?.user_message_vi && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
              <p className="text-xs font-semibold text-amber-700 mb-1">⚠ Lưu ý</p>
              <p className="text-sm text-amber-900">{session.error_summary.user_message_vi}</p>
            </div>
          )}
        </div>
      )}

      {/* AI Rescue Message */}
      {session.ai_rescue_message && session.status === "failed" && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-2">
          <p className="text-sm font-medium text-amber-900">
            {session.ai_rescue_message.user_message_vi}
          </p>
          {session.ai_rescue_message.missing_columns.length > 0 && (
            <p className="text-xs text-amber-700">
              Thiếu cột: {session.ai_rescue_message.missing_columns.join(", ")}
            </p>
          )}
          <p className="text-xs text-amber-800 whitespace-pre-wrap">
            {session.ai_rescue_message.next_step_instruction}
          </p>
        </div>
      )}
    </div>
  )
}
