"use client"
import { useState, useEffect } from "react"
import { useShop } from "@/hooks/useApi"
import { shopsApi, cogsApi, insightsApi, notificationsApi, COGSItemResponse } from "@/lib/api"
import { getAuthToken } from "@/lib/supabase"

// ── COGS Table ────────────────────────────────────────────────────────────────

interface COGSRow extends COGSItemResponse {
  dirty: boolean
}

function COGSTable({ token }: { token: string }) {
  const [rows, setRows] = useState<COGSRow[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [totalSkus, setTotalSkus] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    cogsApi.getAll(token)
      .then((res) => {
        setRows(res.items.map((item) => ({ ...item, dirty: false })))
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

  const dirtyRows = rows.filter((r) => r.dirty && r.cogs_per_unit !== "" && r.cogs_per_unit !== "0")
  const hasDirty = dirtyRows.length > 0
  const coveredCount = rows.filter((r) => parseFloat(r.cogs_per_unit) > 0).length
  const coveragePct = rows.length > 0 ? (coveredCount / rows.length) * 100 : 0

  async function handleSave() {
    if (!hasDirty) return
    setSaving(true)
    setError(null)
    try {
      await cogsApi.upsert(token, dirtyRows.map((r) => ({
        sku_id: r.sku_id,
        sku_name: r.sku_name,
        cogs_per_unit: r.cogs_per_unit,
      })))
      setRows((prev) => prev.map((r) => ({ ...r, dirty: false })))
      setSaved(true)
      setTimeout(() => setSaved(false), 4000)
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

      <div className="border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-2.5 font-medium text-gray-600">SKU</th>
              <th className="text-right px-4 py-2.5 font-medium text-gray-600 w-48">Giá vốn / đơn vị (VND)</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((row) => (
              <tr key={row.sku_id} className={row.dirty ? "bg-amber-50" : "hover:bg-gray-50"}>
                <td className="px-4 py-2.5">
                  <div className="font-medium text-gray-900 truncate max-w-[260px]" title={row.sku_name}>
                    {row.sku_name}
                  </div>
                  <div className="text-xs text-gray-400 font-mono mt-0.5">{row.sku_id}</div>
                </td>
                <td className="px-4 py-2.5">
                  <input
                    type="number" min="0" step="1000" placeholder="VD: 50000"
                    value={row.cogs_per_unit === "0" ? "" : row.cogs_per_unit}
                    onChange={(e) => updateRow(row.sku_id, e.target.value || "0")}
                    className="w-full text-right border rounded-lg px-2.5 py-1.5 text-sm
                               focus:outline-none focus:ring-2 focus:ring-blue-500
                               [appearance:textfield] bg-white"
                  />
                </td>
              </tr>
            ))}
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
        {saved && <span className="text-sm text-green-700 font-medium">✓ Đã lưu — nhớ Tính lại P&L để cập nhật margin</span>}
      </div>

      {saved && <RecomputeNudge token={token} />}
    </div>
  )
}

function RecomputeNudge({ token }: { token: string }) {
  const [recomputing, setRecomputing] = useState(false)
  const [done, setDone] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  async function handleRecompute() {
    setRecomputing(true)
    setErr(null)
    try {
      await insightsApi.recompute(token)
      setDone(true)
    } catch (e: any) {
      setErr(e?.status === 402
        ? "Tính lại P&L cần gói Pro."
        : "Tính lại thất bại. Thử lại hoặc vào Overview.")
    } finally {
      setRecomputing(false)
    }
  }

  if (done) return (
    <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-800">
      ✓ Đã tính lại — <a href="/overview" className="underline font-medium">vào Overview để xem margin mới nhất</a>.
    </div>
  )

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm space-y-2">
      <p className="text-blue-800 font-medium">Tính lại P&L với giá vốn mới?</p>
      <p className="text-blue-700 text-xs">Margin sẽ được cập nhật dựa trên giá vốn vừa nhập.</p>
      <button onClick={handleRecompute} disabled={recomputing}
        className="bg-blue-600 text-white text-xs px-3 py-1.5 rounded-lg font-medium
                   hover:bg-blue-700 disabled:opacity-50 transition-colors">
        {recomputing ? "Đang tính lại..." : "Tính lại P&L →"}
      </button>
      {err && <p className="text-xs text-red-600">{err}</p>}
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
            <label className="block text-sm font-medium mb-1">Tên shop</label>
            <input type="text" value={shopName} onChange={(e) => setShopName(e.target.value)}
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

      {/* Email Notifications */}
      <div className="bg-white rounded-xl border p-6">
        <h2 className="font-semibold mb-1">Thông báo hàng tuần</h2>
        <p className="text-sm text-gray-500 mb-4">
          Nhận báo cáo P&L tóm tắt mỗi sáng thứ Hai qua email.
        </p>
        <NotificationSettings
          token={token}
          initialEmail={(shop as any)?.notification_email}
          initialEnabled={(shop as any)?.email_digest_enabled ?? false}
        />
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
            shop?.subscription_tier === "pro" ? "bg-blue-100 text-blue-700" :
            "bg-gray-100 text-gray-600"}`}>
            {shop?.subscription_tier === "business" ? "Business" :
             shop?.subscription_tier === "pro" ? "Pro" : "Free"}
          </span>
        </div>
      </div>
    </div>
  )
}
