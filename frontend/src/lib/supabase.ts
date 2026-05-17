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
  const { data: { session } } = await supabase.auth.getSession()
  return session?.access_token ?? null
}
