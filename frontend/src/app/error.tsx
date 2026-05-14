"use client"

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html>
      <body>
        <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
          <div className="text-center max-w-sm">
            <p className="text-4xl mb-4">⚠️</p>
            <p className="font-semibold text-gray-800 mb-2">Đã xảy ra lỗi</p>
            <p className="text-sm text-gray-500 mb-6">
              {error.message || "Vui lòng thử lại hoặc liên hệ support."}
            </p>
            <button
              onClick={reset}
              className="bg-gray-900 text-white text-sm px-5 py-2 rounded-lg hover:bg-gray-700 transition-colors"
            >
              Thử lại
            </button>
          </div>
        </div>
      </body>
    </html>
  )
}
