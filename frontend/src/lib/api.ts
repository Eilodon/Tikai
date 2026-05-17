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
  options: RequestInit & { token?: string; _retried?: boolean } = {},
): Promise<T> {
  const { token, _retried, ...init } = options

  // FIX P0-2: Never override Content-Type when body is FormData.
  // The browser must set multipart/form-data with the correct boundary= string automatically.
  // Hardcoding application/json causes FastAPI to reject the file upload entirely.
  const isFormData = init.body instanceof FormData
  const headers = new Headers(init.headers)
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`)
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  })

  // 401 interceptor: refresh Supabase session and retry once
  if (res.status === 401 && !_retried) {
    const { createClient } = await import("@/lib/supabase")
    const supabase = createClient()
    const { data } = await supabase.auth.refreshSession()
    const newToken = data.session?.access_token
    if (newToken) {
      return request<T>(path, { ...options, token: newToken, _retried: true })
    }
  }

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
      token,
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
  trial_expires_at?: string | null
  tiktok_shop_id?: string | null
  is_active?: boolean
  notification_email?: string | null
  email_digest_enabled?: boolean
  category?: string | null
  seller_phone?: string | null
  zns_enabled?: boolean
  // Gap #5: dynamic settlement window rates
  ldr_rate?: number | null
  sfcr_rate?: number | null
}

// Gap #1: Full fee config with verified_date for PLSummary badge
export interface FeeConfigCurrentResponse {
  version: string
  platform: string
  platform_commission_rate: string
  transaction_fee_rate: string
  order_processing_fee_per_order: string
  effective_from: string
  effective_to: string | null
  verified_date: string
  notes: string | null
  is_stale: boolean
}

export interface FeeScheduleResponse {
  version: string
  platform_commission_rate: string
  transaction_fee_rate: string
  order_processing_fee_per_order: string
}

export interface CampaignSKUInput {
  sku_id: string
  planned_units: number
  price_change_pct?: string | null
  affiliate_rate?: string | null
  voucher_rate?: string | null
}

export interface CampaignSKUResult {
  sku_id: string
  sku_name: string
  planned_units: number
  current_net_revenue: string
  simulated_net_revenue: string
  net_revenue_delta: string
  current_margin: string | null
  simulated_margin: string | null
  simulated_margin_pct: string | null
  verdict: string
}

export interface CampaignSimulateResponse {
  snapshot_id: string
  fee_config_version: string
  skus: CampaignSKUResult[]
  portfolio: {
    total_current_net_revenue: string
    total_simulated_net_revenue: string
    total_net_revenue_delta: string
    total_current_margin: string | null
    total_simulated_margin: string | null
    total_margin_delta: string | null
  }
}

export interface UpdateShopRequest {
  shop_name?: string
  tiktok_shop_id?: string | null
  category?: string | null
  seller_phone?: string | null
  zns_enabled?: boolean
  // Gap #5: dynamic settlement window — pass as decimal (0.023 = 2.3%)
  ldr_rate?: number | null
  sfcr_rate?: number | null
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
  // P0-1 fix: top 5 SKUs by GMV for post-import COGS prompt
  top_skus_for_cogs: Array<{ sku_id: string; sku_name: string; gmv: string }>
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
  margin: string | null
  gmv_rank: number
  // Aggregated cost components — used by What-If Simulator
  affiliate_commission: string
  voucher_cost: string
  // Feature 2: SKU Health Score
  health_status: "healthy" | "warning" | "critical"
  health_reasons: string[]
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
  // Feature 4: Creator Scorecard
  performance_label: "star" | "break_even" | "losing"
  suggested_max_commission_rate: string | null
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
  // Feature 6: Cash Flow Forecast
  cash_in_30d: string | null
  cash_pending_total: string | null
  top_leaks: LeakItem[]
  // FIX P0-6: top_skus and top_creators were missing — SKUTable / CreatorTable used them
  top_skus: SKUSummaryItem[]
  top_creators: CreatorSummaryItem[]
  is_net_revenue_mode: boolean
  cogs_coverage_pct: string
  rule_engine_version: string
  fee_config_version: string
  // Gap #4: orders where fees were estimated (not parsed from CSV)
  fee_discrepancy_notes: string[]
  // NEW: period metadata for incomplete-week warning
  days_in_period: number
  is_partial_period: boolean
  is_first_import: boolean
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

// ── Tools API ─────────────────────────────────────────────────────────────────

export interface PriceRecommendRequest {
  cogs_per_unit: string
  target_margin_pct: string   // "0.20" = 20%
  affiliate_rate?: string
  voucher_rate?: string
}

export interface PriceRecommendResponse {
  min_price: string
  target_margin_pct: string
  actual_margin_pct: string
  breakdown: Record<string, string>  // {cogs, platform_commission, ...}
  warning: string | null
  fee_config_version: string
}

export interface SimulateRequest {
  snapshot_id: string
  sku_id: string
  affiliate_rate?: string | null
  voucher_rate?: string | null
  price_change_pct?: string | null
}

export interface SimulationResult {
  current_net_revenue: string
  current_margin: string | null
  current_margin_pct: string | null
  simulated_net_revenue: string
  simulated_margin: string | null
  simulated_margin_pct: string | null
  net_revenue_delta: string
  margin_delta: string | null
  breakeven_extra_orders: number | null
  verdict: string
}

export interface BenchmarkComparison {
  metric: string
  metric_label: string
  shop_value: string
  industry_value: string
  deviation_pct: string
  verdict: "better" | "on_par" | "worse"
  label: string
  category: string
  source: string
}

export interface BenchmarkResponse {
  category: string
  comparisons: BenchmarkComparison[]
}

export const publicToolsApi = {
  priceRecommend: (data: PriceRecommendRequest) =>
    request<PriceRecommendResponse>("/v1/tools/price-recommend/public", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getFeeSchedule: () =>
    request<FeeScheduleResponse>("/v1/tools/fee-schedule/public"),
}

export const toolsApi = {
  priceRecommend: (token: string, data: PriceRecommendRequest) =>
    request<PriceRecommendResponse>("/v1/tools/price-recommend", {
      method: "POST",
      body: JSON.stringify(data),
      token,
    }),

  simulate: (token: string, data: SimulateRequest) =>
    request<SimulationResult>("/v1/tools/simulate", {
      method: "POST",
      body: JSON.stringify(data),
      token,
    }),

  simulateCampaign: (token: string, data: { snapshot_id: string; skus: CampaignSKUInput[] }) =>
    request<CampaignSimulateResponse>("/v1/tools/simulate-campaign", {
      method: "POST",
      body: JSON.stringify(data),
      token,
    }),

  getBenchmark: (token: string, snapshotId: string, category = "other") =>
    request<BenchmarkResponse>(
      `/v1/insights/${snapshotId}/benchmark?category=${category}`,
      { token }
    ),

  // Gap #1: get full fee config with verified_date + stale flag
  getCurrentFeeConfig: (token: string) =>
    request<FeeConfigCurrentResponse>("/v1/fee-config/current", { token }),
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
  avg_price?: string     // SUM(gmv)/SUM(qty) — used for live margin preview, absent on upsert responses
}

export interface COGSBatchResponse {
  updated: number
  items: COGSItemResponse[]
  total_skus: number
}

export interface COGSHistoryEntry {
  id: string
  sku_id: string
  cogs_per_unit: string
  effective_date: string
  note: string | null
  created_at: string
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

  getHistory: (token: string, skuId: string) =>
    request<COGSHistoryEntry[]>(`/v1/cogs/history/${encodeURIComponent(skuId)}`, { token }),
}

// ── Reconcile ─────────────────────────────────────────────────────────────────

export interface ReconcileResponse {
  total_payout: string          // Decimal as string
  expected_payout: string
  gap: string                   // positive = settlement > expected; negative = shortfall
  gap_pct: string               // 0–1 absolute ratio

  // Hidden cost breakdown
  shipping_adjustments_total: string
  refund_admin_fees_total: string
  non_clawback_commissions: string
  reserve_held: string

  // Actionable signals
  high_shipping_adj_skus: string[]
  commission_waste_on_returns: string

  // Verdict
  verdict: "matched" | "minor_gap" | "major_gap" | "investigate"
  action_items_vi: string[]

  // Metadata
  settlement_rows_parsed: number
  snapshot_id: string | null
}

export const reconcileApi = {
  upload: (
    token: string,
    file: File,
    opts: { snapshotId?: string; expectedPayout?: string },
  ) => {
    const formData = new FormData()
    formData.append("file", file)

    const params = new URLSearchParams()
    if (opts.snapshotId) params.set("snapshot_id", opts.snapshotId)
    if (opts.expectedPayout) params.set("expected_payout", opts.expectedPayout)
    const qs = params.toString()

    return request<ReconcileResponse>(`/v1/reconcile${qs ? `?${qs}` : ""}`, {
      method: "POST",
      body: formData,
      headers: { Authorization: `Bearer ${token}` },
    })
  },
}

// ── Creator CRM ───────────────────────────────────────────────────────────────

export interface CreatorProfileResponse {
  id: string
  shop_id: string
  creator_id: string
  creator_name: string
  gmv_30d: string
  net_revenue_30d: string
  revenue_efficiency_30d: string | null
  avg_refund_rate: string
  total_orders_lifetime: number
  last_order_date: string | null
  total_commission_paid: string
  commission_on_refunded_orders: string
  status: "active" | "paused" | "blacklisted" | "vip"
  tags: string[] | null
  negotiated_rate: string | null
  internal_note: string | null
  contact_zalo: string | null
  contact_email: string | null
  performance_label: "star" | "break_even" | "losing"
  suggested_max_commission: string | null
}

export interface CreatorProfileUpdateRequest {
  status?: "active" | "paused" | "blacklisted" | "vip"
  tags?: string[]
  negotiated_rate?: string  // 0–1
  internal_note?: string
  contact_zalo?: string
  contact_email?: string
}

export interface CreatorCohortInsight {
  creator_id: string
  creator_name: string
  trend: "growing" | "stable" | "fading" | "new" | "churned"
  gmv_first_period: string
  gmv_last_period: string
  change_pct: string
  periods_active: number
  avg_orders_per_period: string
}

export const creatorsApi = {
  list: (
    token: string,
    opts: { status?: string; performance_label?: string; limit?: number } = {},
  ) => {
    const params = new URLSearchParams()
    if (opts.status) params.set("status", opts.status)
    if (opts.performance_label) params.set("performance_label", opts.performance_label)
    if (opts.limit) params.set("limit", String(opts.limit))
    const qs = params.toString()
    return request<CreatorProfileResponse[]>(`/v1/creators${qs ? `?${qs}` : ""}`, { token })
  },

  getById: (token: string, profileId: string) =>
    request<CreatorProfileResponse>(`/v1/creators/${profileId}`, { token }),

  update: (token: string, profileId: string, data: CreatorProfileUpdateRequest) =>
    request<CreatorProfileResponse>(`/v1/creators/${profileId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
      token,
    }),

  sync: (token: string) =>
    request<{ synced: number; message?: string }>("/v1/creators/sync", {
      method: "POST",
      token,
    }),

  getCohort: (token: string, periodIds: string[]) =>
    request<CreatorCohortInsight[]>(
      `/v1/insights/creator-cohort?period_ids=${periodIds.join(",")}`,
      { token },
    ),
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
