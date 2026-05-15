const HIDDEN_FEES = [
  {
    icon: "⚖️",
    title: "Phí điều chỉnh vận chuyển",
    subtitle: "Weight discrepancy fee",
    desc: "TikTok Shop kiểm tra lại cân nặng thực tế kiện hàng. Nếu khác với khai báo, bạn bị trừ thêm — thường 3-8% giá trị đơn. Khoản này xuất hiện âm thầm trong settlement mà không có thông báo.",
  },
  {
    icon: "💸",
    title: "Hoa hồng affiliate không thu hồi khi hoàn",
    subtitle: "Non-clawback commission",
    desc: "Khi đơn bị hoàn trả, TikTok Shop không thu hồi hoa hồng đã trả cho creator. Shop mất cả hàng lẫn tiền hoa hồng. Với refund rate 15-20%, đây có thể là khoản lỗ lớn nhất.",
  },
  {
    icon: "📦",
    title: "Phí quản lý hoàn hàng",
    subtitle: "Return handling fee — 20% referral fee",
    desc: "Mỗi đơn hoàn, TikTok thu thêm phí xử lý bằng 20% referral fee. Khoản này cộng dồn khi refund rate cao, nhưng thường bị bỏ qua trong báo cáo GMV.",
  },
  {
    icon: "🔒",
    title: "Reserve holds (Tiền bị giữ)",
    subtitle: "Settlement reserve",
    desc: "TikTok giữ lại một phần tiền settlement (thường 5-10%) trong 7-14 ngày để đảm bảo đơn hoàn. Khoản này làm cash flow thực tế nhỏ hơn nhiều so với GMV trên dashboard.",
  },
]

export default function DoiSoatSettlementPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white px-6 py-4 flex items-center justify-between">
        <a href="/" className="font-bold text-lg">Tikai</a>
        <a href="/login" className="text-sm text-blue-600 hover:underline">Đăng nhập →</a>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-10 space-y-10">
        {/* Hero */}
        <section className="text-center space-y-4">
          <div className="inline-block bg-red-100 text-red-700 text-xs font-semibold px-3 py-1 rounded-full">
            Chênh lệch 15–25%
          </div>
          <h1 className="text-3xl font-bold">Tại sao GMV ≠ tiền về tài khoản?</h1>
          <p className="text-gray-500 text-sm max-w-lg mx-auto">
            Nhiều seller thấy GMV 100 triệu nhưng tài khoản chỉ nhận 75–85 triệu.
            Khoản chênh lệch 15–25% đó đi đâu? Đây là 4 khoản bị trừ âm thầm mà
            settlement report không giải thích rõ.
          </p>
          <div className="bg-white border rounded-2xl p-6 inline-block text-left">
            <div className="flex items-center gap-8 text-center">
              <div>
                <p className="text-3xl font-bold text-gray-900">100 triệu</p>
                <p className="text-xs text-gray-500 mt-1">GMV trên dashboard</p>
              </div>
              <div className="text-2xl text-red-500 font-bold">≠</div>
              <div>
                <p className="text-3xl font-bold text-red-600">75–85 triệu</p>
                <p className="text-xs text-gray-500 mt-1">Tiền thực về tài khoản</p>
              </div>
            </div>
          </div>
        </section>

        {/* 4 Hidden Fees */}
        <section className="space-y-4">
          <h2 className="text-xl font-bold text-center">4 Khoản Bị Trừ Âm Thầm</h2>
          <p className="text-gray-500 text-sm text-center">
            Không có trong báo cáo doanh thu — chỉ thấy khi đọc kỹ settlement CSV
          </p>
          <div className="space-y-4">
            {HIDDEN_FEES.map((fee, i) => (
              <div key={i} className="bg-white border rounded-xl p-5">
                <div className="flex gap-4">
                  <div className="text-2xl flex-shrink-0">{fee.icon}</div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold text-gray-900">{fee.title}</h3>
                      <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                        {fee.subtitle}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600">{fee.desc}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* How Tikai helps */}
        <section className="bg-white border rounded-2xl p-6 space-y-4">
          <h2 className="text-xl font-bold">Đối Soát với Tikai</h2>
          <p className="text-sm text-gray-600">
            Tikai đọc settlement CSV của bạn và tự động phân loại từng khoản trừ — không cần bạn phải tự tính.
          </p>
          <div className="space-y-3">
            {[
              { step: "1", text: "Upload file Settlement Export từ TikTok Seller Center" },
              { step: "2", text: "Tikai phân tích từng dòng — phân loại khoản trừ theo loại" },
              { step: "3", text: "Xem breakdown: bao nhiêu do phí vận chuyển, bao nhiêu do hoàn hàng, bao nhiêu bị hold" },
              { step: "4", text: "So sánh với GMV để biết chính xác % thực nhận" },
            ].map(({ step, text }) => (
              <div key={step} className="flex gap-3 items-start">
                <div className="w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                  {step}
                </div>
                <p className="text-sm text-gray-700">{text}</p>
              </div>
            ))}
          </div>
        </section>

        {/* CTA */}
        <section className="bg-gray-900 text-white rounded-2xl p-8 text-center space-y-4">
          <h2 className="text-xl font-bold">Đối Soát Settlement của bạn</h2>
          <p className="text-sm text-gray-300">
            Upload file settlement — Tikai giải thích mọi khoản trừ trong 60 giây.
            Miễn phí, không cần cài đặt.
          </p>
          <a
            href="/"
            className="inline-block bg-white text-gray-900 text-sm font-semibold px-6 py-3 rounded-xl hover:bg-gray-100 transition-colors"
          >
            Đối soát Settlement của bạn →
          </a>
          <p className="text-xs text-gray-400">
            Hỗ trợ TikTok Shop · Shopee · Lazada · định dạng CSV / XLSX
          </p>
        </section>

        {/* Footer links */}
        <section className="text-center space-x-4 text-xs text-gray-400">
          <a href="/tinh-gia-ban" className="hover:text-blue-600 hover:underline">Tính giá bán</a>
          <span>·</span>
          <a href="/tinh-phi-tiktok" className="hover:text-blue-600 hover:underline">Tính phí TikTok</a>
          <span>·</span>
          <a href="/kiem-tra-margin" className="hover:text-blue-600 hover:underline">Kiểm tra margin</a>
          <span>·</span>
          <a href="/tinh-hoa-hong-creator" className="hover:text-blue-600 hover:underline">Tính hoa hồng creator</a>
        </section>
      </main>
    </div>
  )
}
