import Link from "next/link"

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <p className="text-6xl font-bold text-gray-200 mb-4">404</p>
        <p className="text-lg font-medium text-gray-700 mb-2">Trang không tồn tại</p>
        <p className="text-sm text-gray-500 mb-6">Đường dẫn bạn truy cập không được tìm thấy.</p>
        <Link
          href="/overview"
          className="text-sm text-blue-600 hover:underline"
        >
          ← Về trang chủ
        </Link>
      </div>
    </div>
  )
}
