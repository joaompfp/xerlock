// The milestone tracker: each milestone's forecast against its target (P6's planned
// date), and a status from the variance. Shared by the Progress view and the review.

import type { Activity } from '../types/schedule'
import { isMilestone } from './format'
import { displayEnd } from './p6'

export type MilestoneStatus = 'achieved' | 'on-track' | 'watch' | 'at-risk' | 'unknown'

export const MILESTONE_STATUS_LABELS: Record<MilestoneStatus, string> = {
  achieved: 'Achieved', 'on-track': 'On track', watch: 'Watch', 'at-risk': 'At risk', unknown: 'Unknown',
}

export interface Milestone extends Activity {
  forecast: string | null
  target: string | null
  /** Calendar days the forecast is after (+) or before (−) the target. */
  varianceDays: number | null
  achieved: boolean
  status: MilestoneStatus
}

/** Every milestone with its forecast, target, variance and status, in forecast order.
 *  Within 10 days late is "watch"; beyond, "at risk". */
export function milestoneTracker(activities: Activity[]): Milestone[] {
  return activities
    .filter(isMilestone)
    .map(a => {
      const forecast = displayEnd(a) || a.act_start || a.early_start
      const target = a.target_end || a.target_start
      const achieved = a.status === 'TK_Complete' || !!a.act_end || !!a.act_start
      let varianceDays: number | null = null
      if (forecast && target) {
        varianceDays = Math.round((new Date(forecast).getTime() - new Date(target).getTime()) / 86400000)
      }
      let status: MilestoneStatus
      if (achieved) status = 'achieved'
      else if (varianceDays == null) status = 'unknown'
      else if (varianceDays <= 0) status = 'on-track'
      else if (varianceDays <= 10) status = 'watch'
      else status = 'at-risk'
      return { ...a, forecast, target, varianceDays, achieved, status }
    })
    .sort((x, y) => new Date(x.forecast || 0).getTime() - new Date(y.forecast || 0).getTime())
}
