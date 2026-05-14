"use client"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-client"
import { insightsApi, actionsApi, shopsApi, importsApi, livestreamApi, type AIActionListResponse, type LiveStreamCreateRequest } from "@/lib/api"
import { getAuthToken } from "@/lib/supabase"

// ── Auth helper ──────────────────────────────────────────────────────────────

async function withToken<T>(fn: (token: string) => Promise<T>): Promise<T> {
  const token = await getAuthToken()
  if (!token) throw new Error("Not authenticated")
  return fn(token)
}

// ── Shop ─────────────────────────────────────────────────────────────────────

export function useShop() {
  return useQuery({
    queryKey: queryKeys.shop(),
    queryFn: () => withToken((t) => shopsApi.getMe(t)),
  })
}

// ── Insights ─────────────────────────────────────────────────────────────────

export function useLatestInsight() {
  return useQuery({
    queryKey: queryKeys.insight(),
    queryFn: () => withToken((t) => insightsApi.getLatest(t)),
    retry: (failureCount, error: any) => {
      if (error?.status === 404) return false  // no insight yet — don't retry
      return failureCount < 1
    },
  })
}

// ── Actions ───────────────────────────────────────────────────────────────────

export function useActions() {
  return useQuery({
    queryKey: queryKeys.actions(),
    queryFn: () => withToken((t) => actionsApi.list(t)),
  })
}

export function useCompleteAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => withToken((t) => actionsApi.complete(t, id)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.actions() })
    },
  })
}

export function useDismissAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => withToken((t) => actionsApi.dismiss(t, id)),
    onMutate: async (id) => {
      // Optimistic update
      await qc.cancelQueries({ queryKey: queryKeys.actions() })
      const prev = qc.getQueryData(queryKeys.actions())
      qc.setQueryData(queryKeys.actions(), (old: AIActionListResponse | undefined) => ({
        ...old,
        items: old?.items?.filter((a) => a.id !== id) ?? [],
      }))
      return { prev }
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.actions(), ctx.prev)
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: queryKeys.actions() })
    },
  })
}

// ── Imports ───────────────────────────────────────────────────────────────────

// F-3-02: Max polling duration = job_timeout (300s) + buffer
const IMPORT_MAX_POLL_MS = 360_000  // 6 minutes

export function useImportStatus(sessionId: string | null) {
  return useQuery({
    queryKey: queryKeys.importById(sessionId ?? ""),
    queryFn: () => withToken((t) => importsApi.getById(t, sessionId!)),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      const data = query.state.data as any
      if (!data) return 2000
      // Stop on terminal states
      if (data.status === "completed" || data.status === "failed") return false
      // F-3-02: Stop polling if stuck longer than max import duration
      // Prevents infinite "Đang xử lý..." spinner when ARQ job times out
      if (data.created_at) {
        const elapsed = Date.now() - new Date(data.created_at).getTime()
        if (elapsed > IMPORT_MAX_POLL_MS) return false
      }
      return 2000
    },
  })
}

// ── Insights History (week-over-week) ────────────────────────────────────────

export function useInsightHistory(weeks = 4) {
  return useQuery({
    queryKey: [...queryKeys.insight(), "history", weeks],
    queryFn: () => withToken((t) => insightsApi.getHistory(t, weeks)),
    retry: (failureCount, error: any) => {
      if (error?.status === 404) return false
      return failureCount < 1
    },
  })
}

export function useRecomputeInsight() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (snapshotId?: string) => withToken((t) => insightsApi.recompute(t, snapshotId)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.insight() })
    },
  })
}

// ── Live Stream ───────────────────────────────────────────────────────────────

export function useLiveStreams() {
  return useQuery({
    queryKey: ["livestream"],
    queryFn: () => withToken((t) => livestreamApi.list(t)),
  })
}

export function useCreateLiveStream() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: LiveStreamCreateRequest) => withToken((t) => livestreamApi.create(t, data)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["livestream"] }),
  })
}

export function useUpdateLiveStreamResults() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      withToken((t) => livestreamApi.updateResults(t, id, data)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["livestream"] }),
  })
}
