export default function OverviewLoading() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-4 bg-gray-200 rounded w-40" />
      <div className="bg-white rounded-xl border p-5 grid grid-cols-2 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i}>
            <div className="h-3 bg-gray-200 rounded w-16 mb-2" />
            <div className="h-6 bg-gray-200 rounded w-24" />
          </div>
        ))}
      </div>
      <div className="bg-white rounded-xl border p-5 space-y-3">
        <div className="h-4 bg-gray-200 rounded w-32" />
        {[...Array(3)].map((_, i) => (
          <div key={i} className="flex justify-between py-2 border-b last:border-0">
            <div className="h-4 bg-gray-200 rounded w-1/2" />
            <div className="h-4 bg-gray-200 rounded w-20" />
          </div>
        ))}
      </div>
    </div>
  )
}
