import { createBrowserClient } from "@supabase/ssr"

// Supabase client — auth ONLY
// All business data queries go through FastAPI (src/lib/api.ts)
export const supabase = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
)

export async function getAuthToken(): Promise<string | null> {
  const { data: { session } } = await supabase.auth.getSession()
  return session?.access_token ?? null
}
