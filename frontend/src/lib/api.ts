/**
 * Tikai API Client
 * Typed HTTP client that calls FastAPI backend.
 * ALL money fields come back as string (Decimal serialized) — use formatVND() to display.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { token?: string } = {},
): Promise<T> {
  const { token, ...init } = options

  // FIX P0-2: Never override Content-Type when body is FormData.
  // The browser must set multipart/form-data with the correct boundary= string automatically.
  // Hardcoding application/json causes FastAPI to reject the file upload entirely.
  const isFormData = init.body instanceof FormData
  const contentTypeHeader = isFormData ? {} : { "Content-Type": "application/json" }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...contentTypeHeader,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(
      body?.error?.code ?? "UNKNOWN_ERROR",
      body?.error?.message ?? "Something went wrong",
      res.status,
    )
  }

  return res.json() as Promise<T>
}

// ── Shops ─────────────────────────────────────────────────────────────────────

export const shopsApi = {
  getMe: (token: string) =>
    request<ShopResponse>("/v1/shops/me", { token }),

  updateMe: (token: string, data: UpdateShopRequest) =>
    request<ShopResponse>("/v1/shops/me", {
      method: "PATCH",
      body: JSON.stringify(data),
      token,
    }),
}

// ── Imports ───────────────────────────────────────────────────────────────────

export const importsApi = {
  upload: (token: string, file: File) => {
    const formData = new FormData()
    formData.append("file", file)
    return request<ImportSessionResponse>("/v1/imports", {
      method: "POST",
      body: formData,
      headers: { Authorization: `Bearer ${token}` },
    })
  },

  getById: (token: string, id: string) =>
    request<ImportSessionResponse>(`/v1/imports/${id}`, { token }),
}

// ── Insights ──────────────────────────────────────────────────────────────────

export const insightsApi = {
  getLatest: (token: string) =>
    request<InsightSnapshotResponse>("/v1/insights/latest", { token }),

  getById: (token: string, id: string) =>
    request<InsightSnapshotResponse>(`/v1/insights/${id}`, { token }),

  // NEW: week-over-week comparison
  getHistory: (token: string, weeks = 4) =>
    request<InsightSnapshotResponse[]>(`/v1/insights/history?weeks=${weeks}`, { token }),

  // NEW: re-run Rule Engine with current COGS (no file re-upload)
  recompute: (token: string, snapshotId?: string) =>
    request<InsightSnapshotResponse>(
      `/v1/insights/recompute${snapshotId ? `?snapshot_id=${snapshotId}` : ""}`,
      { method: "POST", token }
    ),
}

// ── Actions ───────────────────────────────────────────────────────────────────

export const actionsApi = {
  list: (token: string) =>
    request<AIActionListResponse>("/v1/actions", { token }),  // FIX BUG-CRITICAL-2

  complete: (token: string, id: string) =>
    request<AIActionResponse>(`/v1/actions/${id}/complete`, {
      method: "PATCH",
      token,
    }),

  dismiss: (token: string, id: string) =>
    request<AIActionResponse>(`/v1/actions/${id}/dismiss`, {
      method: "PATCH",
      token,
    }),
}

// ── Types (mirror Pydantic schemas) ──────────────────────────────────────────
// NOTE: money fields are string to preserve Decimal precision

export interface ShopResponse {
  id: string
  shop_name: string
  subscription_tier: string
  fee_config_version: string
}

export interface UpdateShopRequest {
  shop_name?: string
}

export interface ImportSessionResponse {
  id: string
  // FIX P0-6: original_filename was missing — UI used session.original_filename which was undefined
  original_filename: string
  status: "pending" | "processing" | "completed" | "completed_with_caveats" | "failed"
  file_type: "order_export" | "transaction_export" | "settlement_export" | "unknown"
  rows_parsed: number
  rows_failed: number
  // FIX P0-6: error_summary shape mirrors backend ImportSessionResponse Pydantic schema
  error_summary: {
    warning?: string
    error_type?: string
    user_message_vi?: string
    internal_detail?: string
    fee_config_version?: string
  } | null
  ai_rescue_message: ImportRescueMessage | null
  created_at: string
  completed_at: string | null  // FIX P0-6: was missing
}

export interface ImportRescueMessage {
  file_type_guess: string
  file_type_confidence: "high" | "medium" | "low"
  missing_columns: string[]
  can_continue_mode: "full" | "limited" | "blocked"
  user_message_vi: string
  next_step_instruction: string
}

export interface LeakItem {
  type: "sku" | "creator" | "category"
  id: string
  name: string
  estimated_loss: string  // Decimal as string
  reason: string
  confidence: "high" | "medium" | "low"
  can_act_now: boolean
}

export interface SKUSummaryItem {
  sku_id: string
  sku_name: string
  gmv: string          // Decimal as string
  net_revenue: string
  order_count: number
  refund_rate: string  // "0.0420" = 4.20%
  margin_pct: string | null  // null if COGS missing
  gmv_rank: number
}

export interface CreatorSummaryItem {
  creator_id: string
  creator_name: string
  attributed_gmv: string
  attributed_net_revenue: string
  total_commission: string
  order_count: number
  // FIX P0-4: renamed from 'roi' — use revenue_efficiency in UI label
  revenue_efficiency: string | null  // null if commission=0
}

export interface InsightSnapshotResponse {
  id: string
  shop_id: string
  period_start: string
  period_end: string
  gmv_total: string       // Decimal as string — use formatVND()
  net_revenue: string
  total_orders: number
  // FIX P0-6: total_refunds was missing from frontend type
  total_refunds: number
  refund_rate: string     // "0.0420" = 4.20%
  cash_in_14d: string | null
  top_leaks: LeakItem[]
  // FIX P0-6: top_skus and top_creators were missing — SKUTable / CreatorTable used them
  top_skus: SKUSummaryItem[]
  top_creators: CreatorSummaryItem[]
  is_net_revenue_mode: boolean
  cogs_coverage_pct: string
  rule_engine_version: string
  fee_config_version: string
  // NEW: period metadata for incomplete-week warning
  days_in_period: number
  is_partial_period: boolean
  created_at: string
}

export interface AIActionResponse {
  id: string
  // FIX P0-6: shop_id, rule_trigger, created_at were missing from frontend type
  shop_id: string
  action_type: string
  rule_trigger: string
  title: string
  why: string
  do_today: string
  expected_impact: string
  confidence: "high" | "medium" | "low"
  status: "pending" | "done" | "dismissed"
  completed_at: string | null
  // FIX P0-6: is_confirmed_impact and confirmed_delta were missing — Actions page uses them
  is_confirmed_impact: boolean
  confirmed_delta: string | null  // Decimal as string | null
  created_at: string
}

// FIX BUG-CRITICAL-2: backend returns object {items, total, pending_count},
// NOT an array. Previous type AIActionResponse[] caused actionsData?.items to be
// undefined (accessing .items on what TS thought was an array) → pending actions
// never displayed. AIActionListResponse mirrors the Pydantic AIActionListResponse schema.
export interface AIActionListResponse {
  items: AIActionResponse[]
  total: number
  pending_count: number
}

// ── Formatters ────────────────────────────────────────────────────────────────

/**
 * Format Decimal string to Vietnamese currency display.
 * Input: "186000000.0000"
 * Output: "186.000.000 ₫"
 */
export function formatVND(decimalStr: string | null | undefined): string {
  if (!decimalStr) return "—"
  const num = parseFloat(decimalStr)
  if (isNaN(num)) return "—"
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
    maximumFractionDigits: 0,
  }).format(num)
}

/**
 * Format Decimal string as percentage.
 * Input: "0.0420"
 * Output: "4.2%"
 */
export function formatPct(decimalStr: string | null | undefined): string {
  if (!decimalStr) return "—"
  const num = parseFloat(decimalStr) * 100
  if (isNaN(num)) return "—"
  return `${num.toFixed(1)}%`
}


// ── Live Stream ───────────────────────────────────────────────────────────────

export interface LiveStreamResponse {
  id: string
  livestream_date: string
  duration_minutes: number
  host_cost: string
  studio_cost: string
  product_sample_cost: string
  ads_cost: string
  other_cost: string
  total_cost: string
  attributed_gmv: string | null
  attributed_orders: number
  attributed_net_revenue: string | null
  live_roi: string | null   // attributed_gmv / total_cost
  net_roi: string | null    // attributed_net_revenue / total_cost
  notes: string | null
}

export interface LiveStreamCreateRequest {
  livestream_date: string    // ISO date
  duration_minutes?: number
  host_cost?: string
  studio_cost?: string
  product_sample_cost?: string
  ads_cost?: string
  other_cost?: string
  notes?: string
}

export const livestreamApi = {
  list: (token: string) =>
    request<LiveStreamResponse[]>("/v1/livestream", { token }),

  create: (token: string, data: LiveStreamCreateRequest) =>
    request<LiveStreamResponse>("/v1/livestream", {
      method: "POST",
      body: JSON.stringify(data),
      token,
    }),

  updateResults: (token: string, id: string, data: { attributed_gmv?: string; attributed_orders?: number; attributed_net_revenue?: string }) =>
    request<LiveStreamResponse>(`/v1/livestream/${id}/results`, {
      method: "PATCH",
      body: JSON.stringify(data),
      token,
    }),

  delete: (token: string, id: string) =>
    request<void>(`/v1/livestream/${id}`, { method: "DELETE", token }),
}

/**
 * Format a ratio as a multiplier string.
 * Input: "15.2" → "15.2x"
 */
export function formatROI(roiStr: string | null | undefined): string {
  if (!roiStr) return "—"
  const n = parseFloat(roiStr)
  if (isNaN(n)) return "—"
  return `${n.toFixed(1)}x`
}

// ── COGS ─────────────────────────────────────────────────────────────────────

export interface COGSItemResponse {
  sku_id: string
  sku_name: string
  cogs_per_unit: string  // Decimal as string, "0" = not set
}

export interface COGSBatchResponse {
  updated: number
  items: COGSItemResponse[]
  total_skus: number
}

export const cogsApi = {
  getAll: (token: string) =>
    request<COGSBatchResponse>("/v1/cogs", { token }),

  upsert: (token: string, items: { sku_id: string; sku_name: string; cogs_per_unit: string }[]) =>
    request<COGSBatchResponse>("/v1/cogs", {
      method: "POST",
      body: JSON.stringify({ items }),
      token,
    }),
}

// ── Notification settings ─────────────────────────────────────────────────────

export interface NotificationSettingsRequest {
  notification_email?: string | null
  email_digest_enabled?: boolean | null
}

export const notificationsApi = {
  update: (token: string, data: NotificationSettingsRequest) =>
    request<ShopResponse>("/v1/shops/me/notifications", {
      method: "PATCH",
      body: JSON.stringify(data),
      token,
    }),
}
