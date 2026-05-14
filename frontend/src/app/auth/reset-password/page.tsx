"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { supabase } from "@/lib/supabase"

export default function ResetPasswordPage() {
  const router = useRouter()
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (password !== confirm) { setError("Mật khẩu không khớp."); return }
    if (password.length < 6) { setError("Mật khẩu phải ít nhất 6 ký tự."); return }
    setError(null)
    setLoading(true)
    try {
      const { error: err } = await supabase.auth.updateUser({ password })
      if (err) throw err
      setDone(true)
      setTimeout(() => router.replace("/overview"), 2000)
    } catch (e: any) {
      setError(e?.message ?? "Đổi mật khẩu thất bại.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm bg-white rounded-2xl border shadow-sm p-8">
        <h1 className="text-xl font-bold mb-6">Đặt mật khẩu mới</h1>

        {done ? (
          <div className="text-center space-y-2">
            <p className="text-green-700 font-medium">✓ Mật khẩu đã được cập nhật!</p>
            <p className="text-sm text-gray-500">Đang chuyển hướng...</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Mật khẩu mới</label>
              <input
                type="password" required minLength={6} value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Ít nhất 6 ký tự"
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Xác nhận mật khẩu</label>
              <input
                type="password" required value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Nhập lại mật khẩu"
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}
            <button type="submit" disabled={loading}
              className="w-full bg-gray-900 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-gray-700 disabled:opacity-50 transition-colors">
              {loading ? "Đang cập nhật..." : "Đặt mật khẩu mới"}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
