<template>
  <section class="page" data-module="qc">
    <header class="page-head">
      <div>
        <h2>质量控制管理</h2>
        <p class="page-desc">维护质控样品，围绕质控编号、质控类别、标准值、允许偏差做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记质控样品</button>
        <button class="btn" type="button" @click="exportRows">导出质量控制清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in statCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label class="filter-item">
        <span>质控编号</span>
        <input v-model="queryStore.filters.keyword" placeholder="按质控编号检索" />
      </label>
      <label class="filter-item">
        <span>质控类别</span>
        <input v-model="queryStore.filters.category" placeholder="按质控类别检索" />
      </label>
      <label class="filter-item">
        <span>标准值</span>
        <input v-model="queryStore.filters.standardValue" placeholder="按标准值检索" />
      </label>
      <label class="filter-item">
        <span>允许偏差</span>
        <input v-model="queryStore.filters.deviation" placeholder="按允许偏差检索" />
      </label>
      <label class="filter-item">
        <span>标准值区间</span>
        <div class="range-inputs">
          <input v-model="queryStore.filters.standardMin" placeholder="下限" inputmode="decimal" />
          <span>—</span>
          <input v-model="queryStore.filters.standardMax" placeholder="上限" inputmode="decimal" />
        </div>
      </label>
      <label class="filter-item">
        <span>允许偏差区间</span>
        <div class="range-inputs">
          <input v-model="queryStore.filters.deviationMin" placeholder="下限" inputmode="decimal" />
          <span>—</span>
          <input v-model="queryStore.filters.deviationMax" placeholder="上限" inputmode="decimal" />
        </div>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
      <span v-if="validationMessage" class="conflict-text">{{ validationMessage }}</span>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th
            v-for="column in columns"
            :key="column"
            :class="{ sortable: sortableColumns.has(column) }"
            @click="toggleSort(column)"
          >
            {{ column }}<span v-if="sortIndicator(column)" class="sort-indicator">{{ sortIndicator(column) }}</span>
          </th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyMessage }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条质量控制记录</span>
      <span v-if="noticeMessage" class="hint-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <div class="pager">
        <button class="btn" type="button" :disabled="currentPage <= 1" @click="goToPage(currentPage - 1)">上一屏</button>
        <span>第 {{ currentPage }} / {{ pages }} 屏</span>
        <button class="btn" type="button" :disabled="currentPage >= pages" @click="goToPage(currentPage + 1)">下一屏</button>
        <select v-model.number="queryStore.size" @change="changeSize">
          <option :value="10">10 条/屏</option>
          <option :value="20">20 条/屏</option>
          <option :value="50">50 条/屏</option>
        </select>
      </div>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useQcQueryStore } from '@/stores/qcQuery'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/qc'
const columns = ["质控编号", "质控类别", "标准值", "允许偏差", "实测值", "判定结果", "检测日期", "质控状态"]
const sortableColumns = new Set(["质控编号", "质控类别", "标准值", "允许偏差", "实测值", "判定结果", "检测日期"])
const actions = ["检测质控", "确认受控", "标记失控"]

const queryStore = useQcQueryStore()

const rows = ref<Row[]>([])
const total = ref(0)
const pages = ref(1)
const currentPage = ref(1)
const stats = ref<Record<string, number>>({})
const errorMessage = ref('')
const noticeMessage = ref('')
// 空态文案跟随「已生效」的条件，而不是输入框里的草稿，避免反馈与当前列表错位
const appliedWithFilter = ref(false)

// 连续调整条件时只认最后一次请求的响应，保证统计数字与当前列表始终同一口径
let requestSeq = 0

const statCards = computed(() => [
  { label: '待检质控品', value: stats.value['待检测'] ?? 0 },
  { label: '检测中质控品', value: stats.value['检测中'] ?? 0 },
  { label: '受控质控品', value: stats.value['受控'] ?? 0 },
  { label: '失控质控品', value: stats.value['失控'] ?? 0 },
])

const rangeFields: Array<[keyof typeof queryStore.filters, keyof typeof queryStore.filters, string]> = [
  ['standardMin', 'standardMax', '标准值'],
  ['deviationMin', 'deviationMax', '允许偏差'],
]

const validationMessage = computed(() => {
  for (const [minKey, maxKey, label] of rangeFields) {
    const min = queryStore.filters[minKey].trim()
    const max = queryStore.filters[maxKey].trim()
    if ((min && Number.isNaN(Number(min))) || (max && Number.isNaN(Number(max)))) {
      return `${label}区间需填写数字`
    }
    if (min && max && Number(min) > Number(max)) {
      return `${label}下限大于上限，条件互相矛盾，请调整后再查询`
    }
  }
  return ''
})

const emptyMessage = computed(() => (appliedWithFilter.value
  ? '当前组合条件下没有匹配的质控样品，可调整条件或点击重置条件'
  : '暂无质量控制数据，可先登记质控样品'))

function sortIndicator(column: string) {
  if (column !== queryStore.sortField) return ''
  return queryStore.sortOrder === 'asc' ? '▲' : '▼'
}

function toggleSort(column: string) {
  if (!sortableColumns.has(column)) return
  if (queryStore.sortField === column) {
    queryStore.sortOrder = queryStore.sortOrder === 'asc' ? 'desc' : 'asc'
  } else {
    queryStore.sortField = column
    queryStore.sortOrder = 'asc'
  }
  queryStore.page = 1
  void reload()
}

function applyFilters() {
  if (validationMessage.value) {
    errorMessage.value = validationMessage.value
    return
  }
  queryStore.page = 1
  void reload()
}

function resetFilters() {
  queryStore.reset()
  errorMessage.value = ''
  void reload()
}

function goToPage(page: number) {
  queryStore.page = Math.min(Math.max(page, 1), pages.value)
  void reload()
}

function changeSize() {
  queryStore.page = 1
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '质控样品登记入口尚未接入审批流'
}

async function readDetail(response: Response): Promise<string | null> {
  try {
    const body = await response.json()
    return typeof body?.detail === 'string' ? body.detail : null
  } catch {
    return null
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('质量控制动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '质量控制操作失败'
  }
}

async function reload() {
  if (validationMessage.value) {
    errorMessage.value = validationMessage.value
    return
  }
  errorMessage.value = ''
  noticeMessage.value = ''
  const seq = ++requestSeq
  const filters = queryStore.filters
  const params = new URLSearchParams()
  if (filters.keyword.trim()) params.set('keyword', filters.keyword.trim())
  if (filters.category.trim()) params.set('category', filters.category.trim())
  if (filters.standardValue.trim()) params.set('standard_value', filters.standardValue.trim())
  if (filters.deviation.trim()) params.set('deviation', filters.deviation.trim())
  if (filters.standardMin.trim()) params.set('standard_min', filters.standardMin.trim())
  if (filters.standardMax.trim()) params.set('standard_max', filters.standardMax.trim())
  if (filters.deviationMin.trim()) params.set('deviation_min', filters.deviationMin.trim())
  if (filters.deviationMax.trim()) params.set('deviation_max', filters.deviationMax.trim())
  const hasFilter = params.size > 0
  params.set('sort', queryStore.sortField)
  params.set('order', queryStore.sortOrder)
  params.set('page', String(queryStore.page))
  params.set('size', String(queryStore.size))
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      const detail = await readDetail(response)
      throw new Error(detail ?? '质控样品列表读取失败')
    }
    const payload = await response.json()
    if (seq !== requestSeq) return
    rows.value = payload.items ?? []
    total.value = payload.total ?? 0
    pages.value = payload.pages ?? 1
    currentPage.value = payload.page ?? 1
    stats.value = payload.stats ?? {}
    appliedWithFilter.value = hasFilter
    if (payload.page < queryStore.page) {
      // 条件收紧后原页码越界，后端已收敛到最后一屏
      noticeMessage.value = '目标屏超出当前结果范围，已定位到最后一屏'
      queryStore.page = payload.page
    } else if (payload.total > 0 && payload.pages > 1 && payload.page === payload.pages) {
      noticeMessage.value = '已到最后一屏'
    }
  } catch (error) {
    if (seq !== requestSeq) return
    errorMessage.value = error instanceof Error ? error.message : '质量控制列表读取失败'
  }
}

onMounted(reload)
</script>
