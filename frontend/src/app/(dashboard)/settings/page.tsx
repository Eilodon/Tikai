"use client"
import { useState, useEffect, useRef } from "react"
import { useShop } from "@/hooks/useApi"
import { shopsApi, cogsApi, insightsApi, notificationsApi, COGSItemResponse, COGSHistoryEntry } from "@/lib/api"
import { getAuthToken } from "@/lib/supabase"
import { PriceRecommender } from "@/components/insights/PriceRecommender"

// ── COGS Table ────────────────────────────────────────────────────────────────

interface COGSRow extends COGSItemResponse {
  dirty: boolean
  original_cogs: string  // T3-3: value at load time, for variance detection
  selected: boolean       // T3-1: bulk-select state
}

// T3-2: History popover — fetches and displays previous COGS values for a SKU
function COGSHistoryPopover({ skuId, token, onClose }: { skuId: string; token: string; onClose: () => void }) {
  const [entries, setEntries] = useState<COGSHistoryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    cogsApi.getHistory(token, skuId)
      .then(setEntries)
      .catch(() => setEntries([]))
      .finally(() => setLoading(false))
  }, [skuId, token])

  // Close on outside click
  useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener("mousedown", handle)
    return () => document.removeEventListener("mousedown", handle)
  }, [onClose])

  return (
    <>
      <div className="fixed inset-0 z-10" onClick={onClose} />
      <div
        ref={ref}
        className="absolute left-0 top-full mt-1 z-20 bg-white border rounded-xl shadow-lg p-3 w-56 text-xs"
      >
        <div className="flex items-center justify-between mb-2">
          <p className="font-semibold text-gray-800">Lịch sử giá vốn</p>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 leading-none">✕</button>
        </div>
        {loading ? (
          <div className="space-y-1.5">
            {[1,2].map(i => <div key={i} className="h-4 bg-gray-100 rounded animate-pulse" />)}
          </div>
        ) : entries.length === 0 ? (
          <p className="text-gray-400">Chưa có lịch sử.</p>
        ) : (
          <ul className="space-y-1.5">
            {entries.slice(0, 6).map((e) => (
              <li key={e.id} className="flex items-center justify-between gap-2">
                <span className="text-gray-500">{e.effective_date}</span>
                <span className="font-medium text-gray-800 tabular-nums">
                  {parseInt(e.cogs_per_unit).toLocaleString("vi-VN")} đ
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  )
}

function COGSTable({ token }: { token: string }) {
  const [rows, setRows] = useState<COGSRow[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveResult, setSaveResult] = useState<"saved" | "recomputed" | null>(null)
  const [totalSkus, setTotalSkus] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [historySkuId, setHistorySkuId] = useState<string | null>(null)  // T3-2
  const [bulkValue, setBulkValue] = useState("")                          // T3-1
  const inputRefs = useRef<Map<string, HTMLInputElement>>(new Map()).current

  useEffect(() => {
    cogsApi.getAll(token)
      .then((res) => {
        setRows(res.items.map((item) => ({
          ...item,
          dirty: false,
          original_cogs: item.cogs_per_unit,
          selected: false,
        })))
        setTotalSkus(res.total_skus)
      })
      .catch(() => setError("Không tải được danh sách SKU."))
      .finally(() => setLoading(false))
  }, [token])

  function updateRow(skuId: string, newCogs: string) {
    setRows((prev) =>
      prev.map((r) => r.sku_id === skuId ? { ...r, cogs_per_unit: newCogs, dirty: true } : r)
    )
  }

  // T3-1: toggle individual row selection
  function toggleSelect(skuId: string) {
    setRows((prev) => prev.map((r) => r.sku_id === skuId ? { ...r, selected: !r.selected } : r))
  }

  function toggleSelectAll() {
    const allSelected = rows.every((r) => r.selected)
    setRows((prev) => prev.map((r) => ({ ...r, selected: !allSelected })))
  }

  // T3-1: apply bulkValue to all selected rows
  function applyBulkFill() {
    const val = bulkValue.trim()
    if (!val) return
    setRows((prev) => prev.map((r) =>
      r.selected ? { ...r, cogs_per_unit: val, dirty: true, selected: false } : r
    ))
    setBulkValue("")
  }

  const selectedRows = rows.filter((r) => r.selected)
  const selectedCount = selectedRows.length
  const allSelected = rows.length > 0 && rows.every((r) => r.selected)

  // T1-5: allow dirty rows with "0" so users can clear a previously-set COGS
  const dirtyRows = rows.filter((r) => r.dirty)
  const hasDirty = dirtyRows.length > 0

  // T1-4: coverage counts in-progress dirty inputs too, not just saved state
  const coveredCount = rows.filter((r) => parseFloat(r.cogs_per_unit) > 0).length
  const coveragePct = rows.length > 0 ? (coveredCount / rows.length) * 100 : 0

  // T1-3: keyboard navigation — Enter/ArrowDown advances to next row input
  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>, skuId: string) {
    if (e.key !== "Enter" && e.key !== "ArrowDown" && e.key !== "ArrowUp") return
    e.preventDefault()
    const idx = rows.findIndex((r) => r.sku_id === skuId)
    const nextIdx = e.key === "ArrowUp" ? idx - 1 : idx + 1
    if (nextIdx >= 0 && nextIdx < rows.length) {
      inputRefs.get(rows[nextIdx].sku_id)?.focus()
    } else if (e.key === "Enter" && hasDirty) {
      handleSave()
    }
  }

  // T1-1: save + auto-recompute in a single action — no separate nudge step
  async function handleSave() {
    if (!hasDirty) return
    setSaving(true)
    setError(null)
    setSaveResult(null)
    try {
      await cogsApi.upsert(token, dirtyRows.map((r) => ({
        sku_id: r.sku_id,
        sku_name: r.sku_name,
        cogs_per_unit: r.cogs_per_unit,
      })))
      setRows((prev) => prev.map((r) => ({
        ...r,
        dirty: false,
        original_cogs: r.dirty ? r.cogs_per_unit : r.original_cogs,
      })))
      setSaveResult("saved")
      // Fire-and-forget recompute — don't block UX, ignore 402 (free tier)
      insightsApi.recompute(token)
        .then(() => setSaveResult("recomputed"))
        .catch(() => {/* free tier: margin will update on next scheduled compute */})
    } catch {
      setError("Lưu thất bại. Vui lòng thử lại.")
    } finally {
      setSaving(false)
    }
  }

  if (loading) return (
    <div className="animate-pulse space-y-2">
      {[1,2,3].map(i => <div key={i} className="h-10 bg-gray-100 rounded" />)}
    </div>
  )

  if (error && rows.length === 0) return <p className="text-sm text-red-600 py-2">{error}</p>

  if (rows.length === 0) return (
    <div className="text-sm text-gray-500 py-6 text-center border rounded-lg bg-gray-50">
      Chưa có đơn nào. Import file TikTok Shop để bắt đầu.
    </div>
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-600">
          Đã nhập giá vốn:{" "}
          <strong className={coveredCount === rows.length ? "text-green-700" : "text-amber-700"}>
            {coveredCount}/{rows.length} SKU
          </strong>
        </span>
        {totalSkus > rows.length && (
          <span className="text-xs text-gray-400">Hiển thị {rows.length}/{totalSkus} SKU</span>
        )}
      </div>

      <div className="w-full bg-gray-100 rounded-full h-2">
        <div
          className="h-2 rounded-full transition-all duration-500"
          style={{
            width: `${coveragePct}%`,
            background: coveragePct === 100 ? "#059669" : coveragePct >= 50 ? "#2563eb" : "#d97706",
          }}
        />
      </div>

      {/* T3-1: Bulk-fill toolbar — appears when ≥1 row is selected */}
      {selectedCount > 0 && (
        <div className="flex items-center gap-2 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2">
          <span className="text-xs text-blue-700 font-medium whitespace-nowrap">
            Điền {selectedCount} SKU đã chọn:
          </span>
          <input
            type="number" min="0" step="1000" placeholder="Giá vốn chung..."
            value={bulkValue}
            onChange={(e) => setBulkValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") applyBulkFill() }}
            className="flex-1 text-right border rounded px-2 py-1 text-xs
                       focus:outline-none focus:ring-2 focus:ring-blue-500
                       [appearance:textfield] bg-white min-w-0"
          />
          <button
            onClick={applyBulkFill}
            disabled={!bulkValue.trim()}
            className="bg-blue-600 text-white text-xs px-3 py-1.5 rounded font-medium
                       hover:bg-blue-700 disabled:opacity-40 transition-colors whitespace-nowrap"
          >
            Áp dụng
          </button>
          <button
            onClick={() => setRows((prev) => prev.map((r) => ({ ...r, selected: false })))}
            className="text-xs text-blue-500 hover:text-blue-700 px-1"
            title="Bỏ chọn tất cả"
          >
            ✕
          </button>
        </div>
      )}

      <div className="border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-3 py-2.5 w-8">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleSelectAll}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  title="Chọn tất cả"
                />
              </th>
              <th className="text-left px-3 py-2.5 font-medium text-gray-600">SKU</th>
              <th className="text-right px-4 py-2.5 font-medium text-gray-600 w-48">Giá vốn / đơn vị (VND)</th>
              <th className="text-right px-3 py-2.5 font-medium text-gray-600 w-24">Gross ≈</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((row) => {
              const cogs = parseFloat(row.cogs_per_unit)
              const avg = row.avg_price ? parseFloat(row.avg_price) : null
              const grossPct = avg && avg > 0 && cogs > 0
                ? ((avg - cogs) / avg) * 100
                : null

              // T3-3: variance vs original saved value
              const origCogs = parseFloat(row.original_cogs)
              const variancePct = row.dirty && origCogs > 0 && cogs > 0
                ? ((cogs - origCogs) / origCogs) * 100
                : null
              const hasLargeVariance = variancePct !== null && Math.abs(variancePct) >= 30

              return (
                <tr
                  key={row.sku_id}
                  className={
                    row.selected ? "bg-blue-50" :
                    row.dirty    ? "bg-amber-50" : "hover:bg-gray-50"
                  }
                >
                  {/* T3-1: row checkbox */}
                  <td className="px-3 py-2.5">
                    <input
                      type="checkbox"
                      checked={row.selected}
                      onChange={() => toggleSelect(row.sku_id)}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                  </td>

                  {/* T3-2: SKU name + history button */}
                  <td className="px-3 py-2.5 relative">
                    <div className="flex items-center gap-1.5">
                      <div className="font-medium text-gray-900 truncate max-w-[200px]" title={row.sku_name}>
                        {row.sku_name}
                      </div>
                      <button
                        onClick={() => setHistorySkuId(row.sku_id === historySkuId ? null : row.sku_id)}
                        title="Xem lịch sử giá vốn"
                        className="text-gray-300 hover:text-blue-500 transition-colors flex-shrink-0 leading-none"
                      >
                        ↻
                      </button>
                    </div>
                    <div className="text-xs text-gray-400 font-mono mt-0.5">{row.sku_id}</div>
                    {historySkuId === row.sku_id && (
                      <COGSHistoryPopover
                        skuId={row.sku_id}
                        token={token}
                        onClose={() => setHistorySkuId(null)}
                      />
                    )}
                  </td>

                  {/* COGS input + T3-3 variance warning */}
                  <td className="px-4 py-2.5">
                    <input
                      ref={(el) => { if (el) inputRefs.set(row.sku_id, el) }}
                      type="number" min="0" step="1000" placeholder="VD: 50000"
                      value={row.cogs_per_unit === "0" ? "" : row.cogs_per_unit}
                      onChange={(e) => updateRow(row.sku_id, e.target.value || "0")}
                      onKeyDown={(e) => handleKeyDown(e, row.sku_id)}
                      className={`w-full text-right border rounded-lg px-2.5 py-1.5 text-sm
                                 focus:outline-none focus:ring-2 focus:ring-blue-500
                                 [appearance:textfield] bg-white ${
                                   hasLargeVariance ? "border-orange-400" : ""
                                 }`}
                    />
                    {hasLargeVariance && variancePct !== null && (
                      <p className="text-xs text-orange-600 text-right mt-0.5">
                        ⚠ {variancePct > 0 ? "+" : ""}{variancePct.toFixed(0)}% vs trước
                      </p>
                    )}
                  </td>

                  {/* T2-1: gross margin preview + T3-3 negative margin alert */}
                  <td className="px-3 py-2.5 text-right">
                    {grossPct !== null ? (
                      <div>
                        <span className={`text-xs font-medium tabular-nums ${
                          grossPct >= 15 ? "text-green-700" :
                          grossPct >= 5  ? "text-amber-600" : "text-red-600"
                        }`}>
                          {grossPct >= 0 ? "" : "−"}{Math.abs(grossPct).toFixed(0)}%
                        </span>
                        {grossPct < 0 && (
                          <p className="text-xs text-red-500 mt-0.5">COGS &gt; giá bán</p>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-gray-300">—</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex items-center gap-3 min-h-[36px]">
        {hasDirty && (
          <button onClick={handleSave} disabled={saving}
            className="bg-blue-600 text-white text-sm px-4 py-2 rounded-lg font-medium
                       hover:bg-blue-700 disabled:opacity-50 transition-colors">
            {saving ? "Đang lưu..." : `Lưu ${dirtyRows.length} thay đổi`}
          </button>
        )}
        {saveResult === "recomputed" && (
          <span className="text-sm text-green-700 font-medium">
            ✓ Đã lưu &amp; tính lại —{" "}
            <a href="/overview" className="underline">xem margin mới</a>
          </span>
        )}
        {saveResult === "saved" && (
          <span className="text-sm text-green-700 font-medium">✓ Đã lưu — đang tính lại margin...</span>
        )}
      </div>
    </div>
  )
}

// ── Notification Settings ─────────────────────────────────────────────────────

function NotificationSettings({ token, initialEmail, initialEnabled }: {
  token: string
  initialEmail?: string | null
  initialEnabled?: boolean
}) {
  const [email, setEmail] = useState(initialEmail ?? "")
  const [enabled, setEnabled] = useState(initialEnabled ?? false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function handleSave() {
    setSaving(true); setErr(null)
    try {
      await notificationsApi.update(token, {
        notification_email: email || null,
        email_digest_enabled: enabled,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (e: any) {
      setErr(e?.message ?? "Lưu thất bại.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <label className="flex items-center gap-3 cursor-pointer select-none">
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          onClick={() => setEnabled(!enabled)}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
                      ${enabled ? "bg-blue-600" : "bg-gray-200"}`}
        >
          <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform
                            ${enabled ? "translate-x-5" : "translate-x-0.5"}`} />
        </button>
        <span className="text-sm font-medium text-gray-900">Nhận báo cáo email hàng tuần</span>
      </label>

      {enabled && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Email nhận báo cáo</label>
          <input
            type="email" value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="ten@example.com"
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-xs text-gray-400 mt-1">
            Gửi mỗi sáng thứ Hai. Có thể dùng email khác với tài khoản đăng nhập.
          </p>
        </div>
      )}

      <div className="flex items-center gap-3">
        <button onClick={handleSave} disabled={saving}
          className="bg-gray-900 text-white text-sm px-4 py-2 rounded-lg font-medium
                     hover:bg-gray-700 disabled:opacity-50 transition-colors">
          {saving ? "Đang lưu..." : "Lưu"}
        </button>
        {saved && <span className="text-sm text-green-600">✓ Đã lưu</span>}
        {err && <span className="text-sm text-red-600">{err}</span>}
      </div>
    </div>
  )
}

// ── Zalo ZNS Settings ─────────────────────────────────────────────────────────

function ZaloSettings({ token, initialPhone, initialEnabled }: {
  token: string
  initialPhone?: string | null
  initialEnabled?: boolean
}) {
  const [phone, setPhone] = useState(initialPhone ?? "")
  const [enabled, setEnabled] = useState(initialEnabled ?? false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function handleSave() {
    setSaving(true); setErr(null)
    try {
      await shopsApi.updateMe(token, {
        seller_phone: phone || null,
        zns_enabled: enabled,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (e: any) {
      setErr(e?.message ?? "Lưu thất bại.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <label className="flex items-center gap-3 cursor-pointer select-none">
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          onClick={() => setEnabled(!enabled)}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
                      ${enabled ? "bg-blue-600" : "bg-gray-200"}`}
        >
          <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform
                            ${enabled ? "translate-x-5" : "translate-x-0.5"}`} />
        </button>
        <span className="text-sm font-medium text-gray-900">Nhận thông báo Zalo (ZNS)</span>
      </label>

      {enabled && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Số điện thoại Zalo</label>
          <input
            type="tel" value={phone} onChange={(e) => setPhone(e.target.value)}
            placeholder="0901234567"
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 max-w-xs"
          />
          <p className="text-xs text-gray-400 mt-1">
            Số điện thoại đã đăng ký Zalo để nhận thông báo P&L hàng tuần.
          </p>
        </div>
      )}

      <div className="flex items-center gap-3">
        <button onClick={handleSave} disabled={saving}
          className="bg-gray-900 text-white text-sm px-4 py-2 rounded-lg font-medium
                     hover:bg-gray-700 disabled:opacity-50 transition-colors">
          {saving ? "Đang lưu..." : "Lưu"}
        </button>
        {saved && <span className="text-sm text-green-600">✓ Đã lưu</span>}
        {err && <span className="text-sm text-red-600">{err}</span>}
      </div>
    </div>
  )
}

// ── Main Settings Page ────────────────────────────────────────────────────────

export default function SettingsPage() {
  const { data: shop, isLoading, refetch } = useShop()
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [shopName, setShopName] = useState("")
  const [token, setToken] = useState<string | null>(null)

  useEffect(() => { getAuthToken().then((t) => setToken(t)) }, [])
  useEffect(() => { if (shop && !shopName) setShopName(shop.shop_name) }, [shop])

  async function handleSave(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setSaved(false)
    try {
      const t = await getAuthToken()
      if (!t) throw new Error("Not authenticated")
      await shopsApi.updateMe(t, { shop_name: shopName })
      await refetch()
      setSaved(true); setTimeout(() => setSaved(false), 3000)
    } catch (err) { console.error(err) }
    finally { setSaving(false) }
  }

  if (isLoading || !token) return (
    <div className="animate-pulse space-y-4 max-w-xl">
      <div className="h-40 bg-gray-200 rounded-xl" />
      <div className="h-60 bg-gray-200 rounded-xl" />
    </div>
  )

  return (
    <div className="space-y-8 max-w-xl">
      <div>
        <h1 className="text-xl font-semibold">Cài đặt</h1>
        <p className="text-sm text-gray-500 mt-1">Thông tin shop, giá vốn và thông báo.</p>
      </div>

      {/* Shop Info */}
      <div className="bg-white rounded-xl border p-6">
        <h2 className="font-semibold mb-4">Thông tin shop</h2>
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label htmlFor="shop-name" className="block text-sm font-medium mb-1">Tên shop</label>
            <input id="shop-name" type="text" value={shopName} onChange={(e) => setShopName(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div className="flex items-center gap-3">
            <button type="submit" disabled={saving}
              className="bg-gray-900 text-white text-sm px-4 py-2 rounded-lg font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors">
              {saving ? "Đang lưu..." : "Lưu"}
            </button>
            {saved && <span className="text-sm text-green-600">✓ Đã lưu</span>}
          </div>
        </form>
      </div>

      {/* COGS */}
      <div className="bg-white rounded-xl border p-6">
        <h2 className="font-semibold mb-1">Giá vốn (COGS)</h2>
        <p className="text-sm text-gray-500 mb-4">
          Nhập giá vốn per SKU để tính margin chính xác. Không có giá vốn, Tikai chỉ hiển thị Net Revenue.
        </p>
        <COGSTable token={token} />
      </div>

      {/* Price Recommender */}
      <div className="bg-white rounded-xl border p-6">
        <h2 className="font-semibold mb-1">Tính giá bán tối thiểu</h2>
        <p className="text-sm text-gray-500 mb-4">
          Nhập giá vốn và margin mục tiêu — Tikai tính ngược ra giá bán tối thiểu sau khi trừ hết phí sàn, affiliate, voucher.
        </p>
        <PriceRecommender />
      </div>

      {/* Email Notifications */}
      <div className="bg-white rounded-xl border p-6">
        <h2 className="font-semibold mb-1">Thông báo hàng tuần</h2>
        <p className="text-sm text-gray-500 mb-4">
          Nhận báo cáo P&L tóm tắt mỗi sáng thứ Hai qua email.
        </p>
        <NotificationSettings
          token={token}
          initialEmail={shop?.notification_email}
          initialEnabled={shop?.email_digest_enabled ?? false}
        />
      </div>

      {/* Zalo ZNS */}
      <div className="bg-white rounded-xl border p-6">
        <h2 className="font-semibold mb-1">Thông báo Zalo (ZNS)</h2>
        <p className="text-sm text-gray-500 mb-4">
          Nhận báo cáo P&L tóm tắt qua Zalo ZNS. Cần gói Pro và số điện thoại đã đăng ký Zalo.
        </p>
        <ZaloSettings
          token={token}
          initialPhone={shop?.seller_phone}
          initialEnabled={shop?.zns_enabled ?? false}
        />
      </div>

      {/* Billing */}
      <div className="bg-white rounded-xl border p-6">
        <h2 className="font-semibold mb-1">Gói đăng ký</h2>
        <div className="flex items-center justify-between py-3 border-b">
          <span className="text-sm text-gray-600">Gói hiện tại</span>
          <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
            shop?.subscription_tier === "business" ? "bg-purple-100 text-purple-700" :
            (shop?.subscription_tier === "pro" || shop?.subscription_tier === "pro_trial") ? "bg-blue-100 text-blue-700" :
            "bg-gray-100 text-gray-600"}`}>
            {shop?.subscription_tier === "business" ? "Business" :
             shop?.subscription_tier === "pro" ? "Pro" :
             shop?.subscription_tier === "pro_trial" ? "Pro (dùng thử)" : "Free"}
          </span>
        </div>
        {(!shop?.subscription_tier || shop.subscription_tier === "free") && (
          <div className="mt-4 space-y-3">
            <ul className="text-sm text-gray-600 space-y-1.5">
              {[
                "Tính lại P&L sau khi cập nhật COGS",
                "Lịch sử 12 tuần (thay vì 4 tuần)",
                "Benchmark ngành",
                "Xuất CSV",
                "Nhận báo cáo Zalo hàng tuần",
              ].map((f) => (
                <li key={f} className="flex items-center gap-2">
                  <span className="text-blue-500 font-bold">✓</span> {f}
                </li>
              ))}
            </ul>
            <a
              href="mailto:hi@tikai.vn?subject=Nâng cấp Pro — 99k/tháng"
              className="block w-full text-center bg-blue-600 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              Nâng cấp Pro — 99k/tháng →
            </a>
            <p className="text-xs text-gray-400 text-center">Gửi email, team sẽ kích hoạt trong 24h.</p>
          </div>
        )}
      </div>

      {/* Fee Config */}
      <div className="bg-white rounded-xl border p-6">
        <h2 className="font-semibold mb-1">Cấu hình phí</h2>
        <p className="text-sm text-gray-500 mb-3">Tikai dùng config phí TikTok Shop VN đã được verify.</p>
        <div className="flex items-center justify-between py-2 border-b">
          <span className="text-sm text-gray-600">Version hiện tại</span>
          <span className="text-sm font-mono text-gray-900">{shop?.fee_config_version}</span>
        </div>
        <div className="flex items-center justify-between py-2">
          <span className="text-sm text-gray-600">Gói đăng ký</span>
          <span className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
            shop?.subscription_tier === "business" ? "bg-purple-100 text-purple-700" :
            (shop?.subscription_tier === "pro" || shop?.subscription_tier === "pro_trial") ? "bg-blue-100 text-blue-700" :
            "bg-gray-100 text-gray-600"}`}>
            {shop?.subscription_tier === "business" ? "Business" :
             shop?.subscription_tier === "pro" ? "Pro" :
             shop?.subscription_tier === "pro_trial" ? "Pro (dùng thử)" : "Free"}
          </span>
        </div>
      </div>

      {/* Trust Center — Gap #3 */}
      <div className="bg-white rounded-xl border p-6">
        <h2 className="font-semibold mb-1">Trung tâm bảo mật & quyền riêng tư</h2>
        <p className="text-sm text-gray-500 mb-4">
          Tikai xử lý dữ liệu của bạn theo tiêu chuẩn bảo mật cao nhất.
        </p>
        <div className="space-y-3 text-sm">
          <div className="flex items-start gap-3 p-3 bg-green-50 rounded-lg">
            <span className="text-green-600 mt-0.5">✓</span>
            <div>
              <p className="font-medium text-green-800">Dữ liệu cá nhân được ẩn tự động</p>
              <p className="text-green-700 text-xs mt-0.5">
                Tên khách hàng, số điện thoại, địa chỉ giao hàng được thay thế bằng{" "}
                <code className="bg-green-100 px-1 rounded">***</code> trước khi AI phân tích.
                AI không bao giờ nhìn thấy thông tin cá nhân.
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 bg-green-50 rounded-lg">
            <span className="text-green-600 mt-0.5">✓</span>
            <div>
              <p className="font-medium text-green-800">Dữ liệu tài chính không bao giờ ra ngoài</p>
              <p className="text-green-700 text-xs mt-0.5">
                Số liệu P&L, GMV, margin của shop chỉ được xử lý bằng Rule Engine
                deterministic — không gửi cho LLM.
              </p>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 bg-blue-50 rounded-lg">
            <span className="text-blue-600 mt-0.5">ℹ</span>
            <div>
              <p className="font-medium text-blue-800">Yêu cầu xóa dữ liệu</p>
              <p className="text-blue-700 text-xs mt-0.5">
                Bạn có thể yêu cầu xóa toàn bộ dữ liệu import bất kỳ lúc nào bằng cách
                gửi email tới{" "}
                <a href="mailto:privacy@tikai.vn" className="underline font-medium">
                  privacy@tikai.vn
                </a>
                . Dữ liệu sẽ bị xóa trong vòng 72 giờ.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
