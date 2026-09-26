/** 质控列表查询条件的会话级缓存：离开页面再回来时，仍能沿用上次的筛选、排序与页码。 */
export interface QcListState {
  filters: {
    code: string
    category: string
    standardMin: string
    standardMax: string
    deviationMin: string
    deviationMax: string
    status: string
  }
  sortField: string
  sortDir: 'asc' | 'desc'
  page: number
  size: number
}

let saved: QcListState | null = null

export function saveQcState(state: QcListState): void {
  saved = state
}

export function loadQcState(): QcListState | null {
  return saved
}
