"use client"
import { useState, useEffect } from "react"

export interface ActivationProgressProps {
  hasImported: boolean          // Step 1
  hasCogsEntered: boolean       // Step 2 — true if cogs_coverage_pct > 0
  hasActedOnAction: boolean     // Step 3
  hasUsedSimulator: boolean     // Step 4 — track in localStorage
  hasReconciledSettlement: boolean // Step 5 — track in localStorage
}

const STEPS = [
  {
    key: "hasImported" as const,
    label: "Import order file",
    linkLabel: "Import file →",
    href: "/import",
  },
  {
    key: "hasCogsEntered" as const,
    label: "Nhập COGS cho top 5 SKU",
    linkLabel: "Nhập COGS →",
    href: "/settings",
  },
  {
    key: "hasActedOnAction" as const,
    label: "Xem và thực hiện 1 Action",
    linkLabel: "Xem Actions →",
    href: "/actions",
  },
  {
    key: "hasUsedSimulator" as const,
    label: "Thử What-If Simulator",
    linkLabel: "Mở Simulator →",
    href: "/overview#skus",
  },
  {
    key: "hasReconciledSettlement" as const,
    label: "Upload settlement để đối soát",
    linkLabel: "Đối soát ngay →",
    href: "/import?tab=settlement",
  },
]

type StepKey = keyof ActivationProgressProps

export function ActivationProgress(props: ActivationProgressProps) {
  // Track which steps just became complete for the flash animation
  const [flashedSteps, setFlashedSteps] = useState<Set<StepKey>>(new Set())

  const completedCount = STEPS.filter(s => props[s.key]).length

  // Flash animation for newly completed steps
  useEffect(() => {
    const newFlashes: StepKey[] = []
    STEPS.forEach(step => {
      if (props[step.key]) {
        newFlashes.push(step.key)
      }
    })
    if (newFlashes.length > 0) {
      setFlashedSteps(new Set(newFlashes))
      const timer = setTimeout(() => setFlashedSteps(new Set()), 800)
      return () => clearTimeout(timer)
    }
  }, [
    props.hasImported,
    props.hasCogsEntered,
    props.hasActedOnAction,
    props.hasUsedSimulator,
    props.hasReconciledSettlement,
  ])

  // Hide entirely if all 5 steps complete
  if (completedCount === 5) return null

  const progressPct = (completedCount / 5) * 100

  return (
    <div className="bg-white border rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-sm text-gray-800">
          Kích hoạt đầy đủ tính năng ({completedCount}/5)
        </h2>
        <span className="text-xs text-gray-400">{completedCount === 4 ? "Gần xong rồi!" : ""}</span>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
        <div
          className="bg-green-500 h-1.5 rounded-full transition-all duration-500"
          style={{ width: `${progressPct}%` }}
        />
      </div>

      {/* Steps */}
      <ol className="space-y-2">
        {STEPS.map((step, i) => {
          const done = props[step.key]
          const isFlashing = flashedSteps.has(step.key)
          return (
            <li key={step.key} className="flex items-center gap-3">
              <div
                className={`w-5 h-5 rounded-full flex items-center justify-center text-xs flex-shrink-0 transition-colors duration-300 ${
                  done
                    ? isFlashing
                      ? "bg-green-300 text-green-900"
                      : "bg-green-100 text-green-700"
                    : "border-2 border-gray-200 text-gray-300"
                }`}
              >
                {done ? "✓" : <span className="w-1.5 h-1.5 rounded-full bg-gray-300 block" />}
              </div>
              <span
                className={`text-sm flex-1 ${
                  done ? "text-gray-400 line-through" : "text-gray-700"
                }`}
              >
                {i + 1}. {step.label}
              </span>
              {!done && (
                <a
                  href={step.href}
                  className="text-xs text-blue-600 hover:underline font-medium whitespace-nowrap"
                >
                  {step.linkLabel}
                </a>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
