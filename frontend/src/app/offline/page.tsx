export const dynamic = "force-static"

export default function OfflinePage() {
  return (
    <main className="min-h-screen flex items-center justify-center px-6 bg-gray-50">
      <div className="max-w-sm text-center space-y-4">
        <div className="text-5xl">📡</div>
        <h1 className="text-xl font-semibold">Mất kết nối</h1>
        <p className="text-sm text-gray-600 leading-relaxed">
          Tikai cần internet để hiển thị dữ liệu mới nhất. Vui lòng kiểm tra kết
          nối và thử lại.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          🔄 Thử lại
        </button>
        <p className="text-xs text-gray-400 pt-4">
          Dữ liệu xem gần nhất vẫn có sẵn trong cache.
        </p>
      </div>
    </main>
  )
}

export const metadata = {
  title: "Mất kết nối — Tikai",
}
