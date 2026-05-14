import Link from "next/link"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="border-b bg-white px-6 py-3 flex items-center gap-6">
        <span className="font-semibold text-lg">Tikai</span>
        <Link href="/overview" className="text-sm text-gray-600 hover:text-gray-900">Tổng quan</Link>
        <Link href="/import" className="text-sm text-gray-600 hover:text-gray-900">Import</Link>
        <Link href="/actions" className="text-sm text-gray-600 hover:text-gray-900">Hành động</Link>
        <Link href="/livestream" className="text-sm text-gray-600 hover:text-gray-900">Livestream</Link>
        <Link href="/settings" className="text-sm text-gray-600 hover:text-gray-900">Cài đặt</Link>
      </nav>
      <main className="px-6 py-6 max-w-4xl mx-auto">{children}</main>
    </div>
  )
}
