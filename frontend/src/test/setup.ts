import "@testing-library/jest-dom"
import { afterAll, afterEach, beforeAll, vi } from "vitest"
import { server } from "./msw-server"

process.env.NEXT_PUBLIC_SUPABASE_URL ??= "https://test.supabase.co"
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??= "test-anon-key"

const supabaseAuthMock = {
  getSession: vi.fn().mockResolvedValue({
    data: { session: { access_token: "test-token" } },
  }),
  refreshSession: vi.fn().mockResolvedValue({
    data: { session: { access_token: "test-token-refreshed" } },
  }),
  signInWithOAuth: vi.fn().mockResolvedValue({ error: null }),
  signInWithPassword: vi.fn().mockResolvedValue({ error: null }),
  signUp: vi.fn().mockResolvedValue({ error: null }),
  resetPasswordForEmail: vi.fn().mockResolvedValue({ error: null }),
}

vi.mock("@/lib/supabase", () => ({
  supabase: { auth: supabaseAuthMock },
  createClient: () => ({ auth: supabaseAuthMock }),
  getAuthToken: vi.fn().mockResolvedValue("test-token"),
}))

// Start MSW mock server before all tests
beforeAll(() => server.listen({ onUnhandledRequest: "error" }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
