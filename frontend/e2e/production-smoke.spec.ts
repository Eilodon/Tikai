import { expect, type Page, test } from "@playwright/test"

const shop = {
  id: "shop-001",
  shop_name: "E2E Shop",
  subscription_tier: "pro",
  fee_config_version: "2026-VN-v3",
  trial_expires_at: null,
  is_active: true,
  notification_email: "owner@example.com",
  email_digest_enabled: false,
  seller_phone: null,
  zns_enabled: false,
}

const insight = {
  id: "snapshot-001",
  shop_id: "shop-001",
  period_start: "2026-05-01",
  period_end: "2026-05-07",
  gmv_total: "186000000.0000",
  net_revenue: "122500000.0000",
  total_orders: 312,
  total_refunds: 13,
  refund_rate: "0.0420",
  cash_in_14d: "89000000.0000",
  cash_in_30d: "142000000.0000",
  cash_pending_total: "53000000.0000",
  top_leaks: [
    {
      type: "sku",
      id: "SKU-001",
      name: "Serum Vitamin C 30ml",
      estimated_loss: "5800000.0000",
      reason: "voucher_high",
      confidence: "high",
      can_act_now: true,
    },
  ],
  top_skus: [
    {
      sku_id: "SKU-001",
      sku_name: "Serum Vitamin C 30ml",
      gmv: "92000000.0000",
      net_revenue: "61000000.0000",
      order_count: 156,
      total_quantity: 180,
      refund_rate: "0.0380",
      margin_pct: "0.1200",
      margin: "7320000.0000",
      gmv_rank: 1,
      affiliate_commission: "9200000.0000",
      voucher_cost: "4600000.0000",
      health_status: "healthy",
      health_reasons: [],
    },
  ],
  top_creators: [
    {
      creator_id: "creator-001",
      creator_name: "Creator A",
      attributed_gmv: "55000000.0000",
      attributed_net_revenue: "36000000.0000",
      total_commission: "5500000.0000",
      order_count: 88,
      revenue_efficiency: "6.55",
      performance_label: "star",
      suggested_max_commission_rate: "0.08",
      commission_on_refunded_orders: "550000.0000",
    },
  ],
  action_triggers: [],
  rule_engine_version: "0.1.0",
  fee_config_version: "v3",
  cogs_coverage_pct: "0.8500",
  is_net_revenue_mode: false,
  days_in_period: 7,
  is_partial_period: false,
  is_first_import: false,
  created_at: "2026-05-08T01:00:00Z",
}

const actionList = {
  items: [
    {
      id: "action-001",
      shop_id: "shop-001",
      action_type: "reduce_voucher",
      rule_trigger: "voucher_high",
      title: "Giảm voucher SKU Serum A",
      why: "Voucher 20% đang ăn hết margin",
      do_today: "Vào TikTok Seller Center giảm voucher xuống 8%",
      expected_impact: "Margin tăng từ -2% lên 6%",
      confidence: "high",
      status: "pending",
      completed_at: null,
      is_confirmed_impact: false,
      confirmed_delta: null,
      created_at: "2026-05-08T01:00:00Z",
    },
  ],
  total: 1,
  pending_count: 1,
}

const importSession = {
  id: "e2e-import",
  original_filename: "orders.csv",
  status: "completed",
  file_type: "order_export",
  rows_parsed: 2,
  rows_failed: 0,
  error_summary: null,
  ai_rescue_message: null,
  top_skus_for_cogs: [
    { sku_id: "SKU-001", sku_name: "Serum Vitamin C 30ml", gmv: "92000000.0000" },
  ],
  created_at: "2026-05-08T01:00:00Z",
  completed_at: "2026-05-08T01:02:00Z",
}

async function mockBackend(page: Page) {
  await page.route("**/v1/**", async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === "GET" && path === "/v1/shops/me") return route.fulfill({ json: shop })
    if (method === "PATCH" && path === "/v1/shops/me") return route.fulfill({ json: shop })
    if (method === "PATCH" && path === "/v1/shops/me/notifications") return route.fulfill({ json: shop })
    if (method === "GET" && path === "/v1/insights/latest") return route.fulfill({ json: insight })
    if (method === "GET" && path === "/v1/insights/history") return route.fulfill({ json: [] })
    if (method === "POST" && path === "/v1/insights/recompute") return route.fulfill({ json: insight })
    if (method === "GET" && path === "/v1/actions") return route.fulfill({ json: actionList })
    if (method === "PATCH" && path.startsWith("/v1/actions/")) {
      return route.fulfill({ json: { ...actionList.items[0], status: "done" } })
    }
    if (method === "POST" && path === "/v1/imports") return route.fulfill({ json: importSession })
    if (method === "GET" && path === "/v1/imports/e2e-import") return route.fulfill({ json: importSession })
    if (method === "GET" && path === "/v1/cogs") {
      return route.fulfill({
        json: {
          updated: 0,
          total_skus: 1,
          items: [{ sku_id: "SKU-001", sku_name: "Serum Vitamin C 30ml", cogs_per_unit: "45000" }],
        },
      })
    }
    if (method === "POST" && path === "/v1/cogs") {
      return route.fulfill({
        json: {
          updated: 1,
          total_skus: 1,
          items: [{ sku_id: "SKU-001", sku_name: "Serum Vitamin C 30ml", cogs_per_unit: "45000" }],
        },
      })
    }
    if (method === "GET" && path === "/v1/weekly-receipts/latest") {
      return route.fulfill({ status: 404, json: { detail: "No receipt found" } })
    }
    if (method === "GET" && path === "/v1/tools/fee-schedule/public") {
      return route.fulfill({
        json: {
          version: "2026-VN-v3",
          platform_commission_rate: "0.04",
          transaction_fee_rate: "0.05",
          order_processing_fee_per_order: "0",
        },
      })
    }
    if (method === "POST" && path.includes("/price-recommend")) {
      return route.fulfill({
        json: {
          min_price: "150000",
          target_margin_pct: "0.20",
          actual_margin_pct: "0.22",
          breakdown: { cogs: "45000", platform_commission: "6000" },
          warning: null,
          fee_config_version: "2026-VN-v3",
        },
      })
    }

    return route.fulfill({ status: 404, json: { error: { code: "E2E_UNMOCKED", message: path } } })
  })
}

test.beforeEach(async ({ page }) => {
  await mockBackend(page)
})

test("login page is public and preserves redirect", async ({ page }) => {
  await page.goto("/login?redirect=/import")
  await expect(page.getByRole("heading", { name: "Tikai" })).toBeVisible()
  await expect(page.getByText("Đăng nhập vào tài khoản")).toBeVisible()
  await expect(page).toHaveURL(/redirect=%2Fimport|redirect=\/import/)
})

test("dashboard overview and actions render financial state", async ({ page }) => {
  await page.goto("/overview")
  await expect(page.getByRole("navigation")).toContainText("Tổng quan")
  await expect(page.getByText("186.000.000")).toBeVisible()
  await expect(page.getByText("Giảm voucher SKU Serum A")).toBeVisible()

  await page.goto("/actions")
  await expect(page.getByRole("heading", { name: "Hành động" })).toBeVisible()
  await expect(page.getByRole("button", { name: /đã làm/i })).toBeVisible()
})

test("import flow accepts a file and shows completed status", async ({ page }) => {
  await page.goto("/import")
  await page.getByLabel(/kéo thả file/i).setInputFiles({
    name: "orders.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("order_id,sku_id,sku_name\n1,SKU-001,Serum\n"),
  })

  await expect(page.getByText("Hoàn thành")).toBeVisible()
  await expect(page.getByText(/Đã xử lý 2 đơn hàng/)).toBeVisible()
  await expect(page.getByText(/Nhập giá vốn/)).toBeVisible()
})

test("settings page saves shop and notification workflows", async ({ page }) => {
  await page.goto("/settings")
  await expect(page.getByRole("heading", { name: "Cài đặt" })).toBeVisible()
  await page.getByLabel("Tên shop").fill("E2E Shop Updated")
  await page.getByRole("button", { name: "Lưu" }).first().click()
  await expect(page.getByText("Đã lưu").first()).toBeVisible()
  await expect(page.getByRole("heading", { name: "Giá vốn (COGS)" })).toBeVisible()
})

test("public price tool works on mobile and PWA offline assets are present", async ({ page, isMobile }) => {
  await page.goto("/tinh-gia-ban")
  await expect(page.getByRole("heading", { name: /bán giá bao nhiêu/i })).toBeVisible()
  await page.getByLabel(/giá vốn/i).fill("80000")
  await page.getByRole("button", { name: /tính giá bán/i }).click()
  await expect(page.getByText(/giá bán tối thiểu để đạt/i)).toBeVisible()
  await expect(page.getByText(/150\.000/)).toBeVisible()
  await expect(page.locator('link[rel="manifest"]')).toHaveAttribute("href", "/manifest.json")

  const response = await page.request.get("/manifest.json")
  expect(response.ok()).toBeTruthy()
  const manifest = await response.json()
  expect(manifest.display).toBe("standalone")

  if (isMobile) {
    await expect(page.getByRole("heading", { name: /bán giá bao nhiêu/i })).toBeInViewport()
  }
})
