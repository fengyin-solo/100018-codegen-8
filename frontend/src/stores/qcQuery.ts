import { defineStore } from 'pinia'

export interface QcFilters {
  keyword: string
  category: string
  standardValue: string
  deviation: string
  standardMin: string
  standardMax: string
  deviationMin: string
  deviationMax: string
}

function emptyFilters(): QcFilters {
  return {
    keyword: '',
    category: '',
    standardValue: '',
    deviation: '',
    standardMin: '',
    standardMax: '',
    deviationMin: '',
    deviationMax: '',
  }
}

/** 质量控制列表的查询条件：离开页面再回来时，筛选、排序、分页都保持原样。 */
export const useQcQueryStore = defineStore('qcQuery', {
  state: () => ({
    filters: emptyFilters(),
    sortField: '质控编号',
    sortOrder: 'asc' as 'asc' | 'desc',
    page: 1,
    size: 10,
  }),
  actions: {
    reset() {
      this.filters = emptyFilters()
      this.sortField = '质控编号'
      this.sortOrder = 'asc'
      this.page = 1
    },
  },
})
