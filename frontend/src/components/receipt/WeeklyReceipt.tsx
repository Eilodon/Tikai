"use client"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-client"
import { formatVND } from "@/lib/api"
import { getAuthToken } from "@/lib/supabase"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

interface WeeklyReceiptData {
  id: string
  period_label: string
  total_confirmed_saved: string
  total_estimated_saved: string
  actions_completed_count: number
  headline: string
  confirmed_section: string
  estimated_section: string
  next_week_focus: string
  disclaimer: string
  is_read: boolean
  created_at: string
}

async function fetchLatestReceipt(token: string): Promise<WeeklyReceiptData> {
  const res = await fetch(`${API_BASE}/v1/weekly-receipts/latest`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error("No receipt")
  return res.json()
}

async function markRead(token: string, id: string): Promise<void> {
  await fetch(`${API_BASE}/v1/weekly-receipts/${id}/read`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${token}` },
  })
}

export function WeeklyReceipt() {
  const qc = useQueryClient()

  const { data: receipt, isLoading, error } = useQuery({
    queryKey: ["weekly-receipt-latest"],
    queryFn: async () => {
      const token = await getAuthToken()
      if (!token) throw new Error("Not authenticated")
      return fetchLatestReceipt(token)
    },
    retry: (count, err: any) => err?.message !== "No receipt" && count < 1,
  })

  const markReadMutation = useMutation({
    mutationFn: async (id: string) => {
      const token = await getAuthToken()
      if (token) await markRead(token, id)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["weekly-receipt-latest"] }),
  })

  if (isLoading) return <ReceiptSkeleton />
  if (error || !receipt) return null

  return (
    <div className="bg-white rounded-xl border overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-gray-900 to-gray-700 px-5 py-4 flex items-center justify-between">
        <div>
          <p className="text-xs text-gray-400 uppercase tracking-wide font-medium">
            Weekly Receipt
          </p>
          <p className="text-white font-semibold mt-0.5">{receipt.period_label}</p>
        </div>
        {!receipt.is_read && (
          <button
            onClick={() => markReadMutation.mutate(receipt.id)}
            className="text-xs text-gray-400 hover:text-white transition-colors"
          >
            Đánh dấu đã đọc
          </button>
        )}
      </div>

      <div className="p-5 space-y-4">
        {/* Headline */}
        <p className="font-semibold text-base">{receipt.headline}</p>

        {/* Confirmed savings */}
        {parseFloat(receipt.total_confirmed_saved) > 0 && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <p className="text-xs font-semibold text-green-700 mb-1 uppercase tracking-wide">
              ✓ Đã xác nhận
            </p>
            <p className="text-2xl font-bold text-green-700">
              {formatVND(receipt.total_confirmed_saved)}
            </p>
            <p className="text-sm text-green-800 mt-1">{receipt.confirmed_section}</p>
          </div>
        )}

        {/* Estimated savings */}
        {parseFloat(receipt.total_estimated_saved) > 0 && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-xs font-semibold text-blue-700 mb-1 uppercase tracking-wide">
              ~ Ước tính
            </p>
            <p className="text-2xl font-bold text-blue-700">
              {formatVND(receipt.total_estimated_saved)}
            </p>
            <p className="text-sm text-blue-800 mt-1">{receipt.estimated_section}</p>
          </div>
        )}

        {/* Next week focus */}
        <div className="border-t pt-4">
          <p className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-1">
            Tuần tới
          </p>
          <p className="text-sm text-gray-700">{receipt.next_week_focus}</p>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-gray-400 border-t pt-3">{receipt.disclaimer}</p>
      </div>
    </div>
  )
}

function ReceiptSkeleton() {
  return (
    <div className="bg-white rounded-xl border overflow-hidden animate-pulse">
      <div className="bg-gray-200 h-16" />
      <div className="p-5 space-y-3">
        <div className="h-4 bg-gray-200 rounded w-3/4" />
        <div className="h-20 bg-gray-100 rounded-lg" />
        <div className="h-16 bg-gray-100 rounded-lg" />
      </div>
    </div>
  )
}
