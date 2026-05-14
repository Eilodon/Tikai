/**
 * TypeScript types mirroring Pydantic schemas from FastAPI backend.
 * Money fields are string (Decimal serialized) — use formatVND() to display.
 * Auto-generate with: npm run generate-types
 */

export interface Shop {
  id: string
  shop_name: string
  tiktok_shop_id: string | null
  subscription_tier: string
  fee_config_version: string
  is_active: boolean
  created_at: string
}

export interface ImportSession {
  id: string
  shop_id: string
  original_filename: string
  file_type: "order_export" | "transaction_export" | "settlement_export" | "unknown"
  status: "pending" | "processing" | "completed" | "failed"
  can_continue_mode: "full" | "limited" | "blocked" | null
  date_range_start: string | null
  date_range_end: string | null
  rows_parsed: number
  rows_failed: number
  error_summary: Record<string, unknown> | null
  ai_rescue_message: ImportRescueMessage | null
  created_at: string
  updated_at: string
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
  estimated_loss: string  // Decimal string
  reason: "voucher_high" | "affiliate_high" | "cogs_missing" | "refund_spike" | "commission_exceeds_margin"
  confidence: "high" | "medium" | "low"
  can_act_now: boolean
}

export interface ActionTrigger {
  rule_id: string
  entity_type: "sku" | "creator" | "shop"
  entity_id: string
  entity_name: string
  metric_key: string
  metric_value: string  // Decimal string
  priority: number
}

export interface SKUSummaryItem {
  sku_id: string
  sku_name: string
  gmv: string            // Decimal string
  net_revenue: string    // Decimal string
  order_count: number
  refund_rate: string    // Decimal string 0-1
  margin_pct: string | null
  gmv_rank: number
}

export interface InsightSnapshot {
  id: string
  shop_id: string
  period_start: string
  period_end: string
  gmv_total: string       // Decimal string — use formatVND()
  net_revenue: string     // Decimal string
  total_orders: number
  total_refunds: number
  refund_rate: string     // "0.0420" = 4.20%
  cash_in_14d: string | null
  top_leaks: LeakItem[]
  top_skus: SKUSummaryItem[]
  action_triggers: ActionTrigger[]
  rule_engine_version: string
  fee_config_version: string
  cogs_coverage_pct: string
  is_net_revenue_mode: boolean
  created_at: string
}

export interface AIAction {
  id: string
  shop_id: string
  action_type: "reduce_voucher" | "pause_creator" | "fix_pdp" | "check_cogs" | "review_script"
  rule_trigger: string
  title: string
  why: string
  do_today: string
  expected_impact: string
  confidence: "high" | "medium" | "low"
  status: "pending" | "done" | "dismissed"
  completed_at: string | null
  is_confirmed_impact: boolean
  confirmed_delta: string | null  // Decimal string
  created_at: string
}

export interface WeeklyReceipt {
  id: string
  period_label: string
  total_confirmed_saved: string  // Decimal string
  total_estimated_saved: string  // Decimal string
  actions_completed_count: number
  headline: string
  confirmed_section: string
  estimated_section: string
  next_week_focus: string
  disclaimer: string
  is_read: boolean
  created_at: string
}

export interface COGSItem {
  sku_id: string
  sku_name: string
  cogs_per_unit: string  // Decimal string
}

// API error shape
export interface ApiError {
  error: {
    code: string
    message: string
    detail?: unknown
  }
}
