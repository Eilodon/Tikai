import { createBrowserClient } from "@supabase/ssr"

// Supabase client — auth ONLY
// All business data queries go through FastAPI (src/lib/api.ts)
const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL ?? "https://placeholder.supabase.co"
const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "placeholder-anon-key"

export const supabase = createBrowserClient(
  supabaseUrl,
  supabaseAnonKey,
)

export function createClient() {
  return supabase
}

export async function getAuthToken(): Promise<string | null> {
  if (process.env.NEXT_PUBLIC_E2E_AUTH_BYPASS === "true") {
    return process.env.NEXT_PUBLIC_E2E_AUTH_TOKEN ?? "e2e-token"
  }

  const { data: { session } } = await supabase.auth.getSession()
  return session?.access_token ?? null
}
