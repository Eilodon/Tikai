"use client"
import { useState } from "react"

export function PrivacyBanner() {
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null

  return (
    <div className="flex items-start gap-3 bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 text-sm text-blue-800">
      <span className="text-base mt-0.5 shrink-0">🔒</span>
      <div className="flex-1 min-w-0">
        <p className="font-medium">Dữ liệu của bạn được bảo vệ</p>
        <p className="mt-0.5 text-blue-700">
          File được xử lý trên server của Tikai. Tên khách hàng, số điện thoại và địa chỉ
          được{" "}
          <strong>ẩn tự động</strong> trước khi phân tích — AI không bao giờ nhìn thấy thông
          tin cá nhân.
        </p>
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="text-blue-400 hover:text-blue-600 shrink-0 text-base leading-none mt-0.5"
        aria-label="Đóng"
      >
        ×
      </button>
    </div>
  )
}
