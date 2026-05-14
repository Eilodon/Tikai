export default function ActionsLoading() {
  return (
    <div className="space-y-3 animate-pulse">
      <div className="h-6 bg-gray-200 rounded w-32 mb-6" />
      {[...Array(3)].map((_, i) => (
        <div key={i} className="bg-white rounded-xl border p-5 space-y-3">
          <div className="h-4 bg-gray-200 rounded w-3/4" />
          <div className="h-3 bg-gray-200 rounded w-full" />
          <div className="h-12 bg-gray-100 rounded-lg" />
          <div className="h-9 bg-gray-200 rounded-lg" />
        </div>
      ))}
    </div>
  )
}
