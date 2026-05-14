import { redirect } from "next/navigation"

// Root route: redirect to dashboard
// middleware.ts handles auth — if not logged in, middleware redirects to /login
export default function RootPage() {
  redirect("/overview")
}
