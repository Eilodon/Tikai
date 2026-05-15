import Link from "next/link"
import { TrialBanner } from "@/components/common/TrialBanner"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen bg-gray-50">
      <TrialBanner />
      <nav className="border-b bg-white px-6 py-3 flex items-center gap-6 overflow-x-auto">
        <span className="font-semibold text-lg shrink-0">Tikai</span>
        <Link href="/overview" className="text-sm text-gray-600 hover:text-gray-900 shrink-0">Tổng quan</Link>
        <Link href="/import" className="text-sm text-gray-600 hover:text-gray-900 shrink-0">Import</Link>
        <Link href="/actions" className="text-sm text-gray-600 hover:text-gray-900 shrink-0">Hành động</Link>
        <Link href="/tools/campaign" className="text-sm text-gray-600 hover:text-gray-900 shrink-0">Kiểm tra chiến dịch</Link>
        <Link href="/livestream" className="text-sm text-gray-600 hover:text-gray-900 shrink-0">Livestream</Link>
        <Link href="/creators" className="text-sm text-gray-600 hover:text-gray-900 shrink-0">Creators</Link>
        <Link href="/doi-soat" className="text-sm text-gray-600 hover:text-gray-900 shrink-0">Đối soát</Link>
        <Link href="/settings" className="text-sm text-gray-600 hover:text-gray-900 shrink-0">Cài đặt</Link>
      </nav>
      <main className="px-6 py-6 max-w-4xl mx-auto">{children}</main>
    </div>
  )
}
