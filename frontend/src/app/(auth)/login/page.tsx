"use client"
import { Suspense, useState } from "react"
import type { Route } from "next"
import { useRouter, useSearchParams } from "next/navigation"
import { supabase } from "@/lib/supabase"

const ORIGIN = typeof window !== "undefined" ? window.location.origin : ""

function getSafeRedirect(raw: string | null): string {
  // Only allow internal relative paths — reject external URLs to prevent open redirect.
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return "/overview"
  return raw
}

function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<"login" | "signup">("login")
  const [forgotMode, setForgotMode] = useState(false)
  const [forgotEmail, setForgotEmail] = useState("")
  const [forgotSent, setForgotSent] = useState(false)

  async function handleGoogleLogin() {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${ORIGIN}/auth/callback` },
    })
  }

  async function handleForgotPassword(e: React.FormEvent) {
    e.preventDefault()
    if (!forgotEmail) { setError("Nhập email để tiếp tục."); return }
    setLoading(true); setError(null)
    try {
      const { error: err } = await supabase.auth.resetPasswordForEmail(forgotEmail, {
        redirectTo: `${ORIGIN}/auth/reset-password`,
      })
      if (err) throw err
      setForgotSent(true)
    } catch (e: any) {
      setError(e?.message ?? "Không gửi được email.")
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const { error: authError } =
        mode === "login"
          ? await supabase.auth.signInWithPassword({ email, password })
          : await supabase.auth.signUp({ email, password })

      if (authError) throw authError
      router.push(getSafeRedirect(searchParams.get("redirect")) as Route)
    } catch (err: any) {
      setError(err?.message ?? "Đã xảy ra lỗi. Vui lòng thử lại.")
    } finally {
      setLoading(false)
    }
  }

  if (forgotMode) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="w-full max-w-sm bg-white rounded-2xl border shadow-sm p-8">
          <h1 className="text-xl font-bold mb-6">Quên mật khẩu</h1>
          {forgotSent ? (
            <div className="space-y-4">
              <p className="text-sm text-green-700 font-medium">✓ Email đã gửi! Kiểm tra hộp thư.</p>
              <p className="text-sm text-gray-500">Link đặt lại mật khẩu có hiệu lực trong 1 giờ.</p>
              <button onClick={() => setForgotMode(false)} className="text-sm text-blue-600 hover:underline">
                ← Quay lại đăng nhập
              </button>
            </div>
          ) : (
            <form onSubmit={handleForgotPassword} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Email</label>
                <input type="email" required value={forgotEmail}
                  onChange={(e) => setForgotEmail(e.target.value)}
                  placeholder="ban@email.com"
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <button type="submit" disabled={loading}
                className="w-full bg-gray-900 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors">
                {loading ? "Đang gửi..." : "Gửi link đặt lại mật khẩu"}
              </button>
              <button type="button" onClick={() => setForgotMode(false)} className="text-sm text-gray-400 hover:text-gray-600">
                ← Quay lại
              </button>
            </form>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm bg-white rounded-2xl border shadow-sm p-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold">Tikai</h1>
          <p className="text-sm text-gray-500 mt-1">
            {mode === "login" ? "Đăng nhập vào tài khoản" : "Tạo tài khoản mới"}
          </p>
        </div>

        {/* Google OAuth */}
        <button
          type="button"
          onClick={handleGoogleLogin}
          className="w-full flex items-center justify-center gap-2 border rounded-lg py-2.5 text-sm font-medium hover:bg-gray-50 transition-colors mb-4"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M17.64 9.205c0-.639-.057-1.252-.164-1.841H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
            <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z" fill="#34A853"/>
            <path d="M3.964 10.71A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 000 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
            <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
          </svg>
          Tiếp tục với Google
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="flex-1 border-t" />
          <span className="text-xs text-gray-400">hoặc dùng email</span>
          <div className="flex-1 border-t" />
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ban@email.com"
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Mật khẩu</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-gray-900 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Đang xử lý..." : mode === "login" ? "Đăng nhập" : "Tạo tài khoản"}
          </button>
        </form>

        {mode === "login" && (
          <div className="text-center mt-3">
            <button onClick={() => setForgotMode(true)} className="text-xs text-gray-400 hover:text-blue-600">
              Quên mật khẩu?
            </button>
          </div>
        )}

        <p className="text-center text-sm text-gray-500 mt-6">
          {mode === "login" ? "Chưa có tài khoản?" : "Đã có tài khoản?"}{" "}
          <button
            onClick={() => setMode(mode === "login" ? "signup" : "login")}
            className="text-blue-600 hover:underline"
          >
            {mode === "login" ? "Tạo mới" : "Đăng nhập"}
          </button>
        </p>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-50" />}>
      <LoginForm />
    </Suspense>
  )
}
