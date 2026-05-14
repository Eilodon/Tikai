import { InsightSnapshotResponse, formatVND, formatPct } from "@/lib/api"

export function SKUTable({ insight }: { insight: InsightSnapshotResponse }) {
  if (!insight.top_skus || insight.top_skus.length === 0) return null

  return (
    <div className="bg-white rounded-xl border overflow-hidden">
      <div className="px-5 py-4 border-b">
        <h2 className="font-semibold text-sm">Top SKUs theo GMV</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
              <th className="text-left px-5 py-3 font-medium">#</th>
              <th className="text-left px-5 py-3 font-medium">SKU</th>
              <th className="text-right px-5 py-3 font-medium">GMV</th>
              <th className="text-right px-5 py-3 font-medium">Net Revenue</th>
              <th className="text-right px-5 py-3 font-medium">Margin</th>
              <th className="text-right px-5 py-3 font-medium">Hoàn</th>
            </tr>
          </thead>
          <tbody>
            {insight.top_skus.slice(0, 10).map((sku) => (
              <tr key={sku.sku_id} className="border-t hover:bg-gray-50 transition-colors">
                <td className="px-5 py-3 text-gray-400 text-xs">{sku.gmv_rank}</td>
                <td className="px-5 py-3">
                  <p className="font-medium text-sm truncate max-w-[160px]">{sku.sku_name}</p>
                  <p className="text-xs text-gray-400">{sku.sku_id}</p>
                </td>
                <td className="px-5 py-3 text-right">{formatVND(sku.gmv)}</td>
                <td className="px-5 py-3 text-right">{formatVND(sku.net_revenue)}</td>
                <td className="px-5 py-3 text-right">
                  {sku.margin_pct ? (
                    <span
                      className={
                        parseFloat(sku.margin_pct) < 0
                          ? "text-red-600 font-medium"
                          : "text-green-700"
                      }
                    >
                      {formatPct(sku.margin_pct)}
                    </span>
                  ) : (
                    <span className="text-gray-300 text-xs">—</span>
                  )}
                </td>
                <td className="px-5 py-3 text-right">
                  <span
                    className={parseFloat(sku.refund_rate) > 0.1 ? "text-red-600" : "text-gray-600"}
                  >
                    {formatPct(sku.refund_rate)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
