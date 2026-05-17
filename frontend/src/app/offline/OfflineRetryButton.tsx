"use client"

export function OfflineRetryButton() {
  return (
    <button
      onClick={() => window.location.reload()}
      className="bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
    >
      🔄 Thử lại
    </button>
  )
}
