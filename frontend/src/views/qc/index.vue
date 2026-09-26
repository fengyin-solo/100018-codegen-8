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

    <form class="filter-bar" @submit.prevent="submitSearch">
      <label class="filter-item">
        <span>质控编号</span>
        <input v-model.trim="filters.code" placeholder="如 QC-0001" />
      </label>
      <label class="filter-item">
        <span>质控类别</span>
        <select v-model="filters.category">
          <option value="">全部类别</option>
          <option v-for="item in categoryOptions" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>标准值</span>
        <span class="range-inputs">
          <input v-model.trim="filters.standardMin" inputmode="decimal" placeholder="下限" />
          <em>~</em>
          <input v-model.trim="filters.standardMax" inputmode="decimal" placeholder="上限" />
        </span>
      </label>
      <label class="filter-item">
        <span>允许偏差</span>
        <span class="range-inputs">
          <input v-model.trim="filters.deviationMin" inputmode="decimal" placeholder="下限" />
          <em>~</em>
          <input v-model.trim="filters.deviationMax" inputmode="decimal" placeholder="上限" />
        </span>
      </label>
      <label class="filter-item">
        <span>质控状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div v-if="validationMessage" class="banner banner-error">{{ validationMessage }}</div>
    <div v-else-if="errorMessage" class="banner banner-error">{{ errorMessage }}</div>
    <div v-else-if="loading" class="banner banner-notice">列表加载中…</div>
    <div v-else-if="notice" class="banner banner-notice">{{ notice }}</div>

    <div v-if="activeChips.length" class="active-chips">
      <span class="chips-label">当前条件：</span>
      <span v-for="chip in activeChips" :key="chip" class="chip">{{ chip }}</span>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th
            v-for="column in columns"
            :key="column"
            :class="{ sortable: sortableColumns.includes(column), active: sortField === column }"
            @click="toggleSort(column)"
          >
            {{ column }}
            <span v-if="sortableColumns.includes(column)" class="sort-mark">{{ sortMark(column) }}</span>
          </th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading && !rows.length">
          <td :colspan="columns.length + 1" class="empty-state">列表加载中…</td>
        </tr>
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
        <tr v-if="!loading && !rows.length">
          <td :colspan="columns.length + 1" class="empty-state">
            <template v-if="hasActiveFilters">
              未找到符合当前条件的质控样品，请调整筛选条件，或
              <button class="link" type="button" @click="resetFilters">重置条件</button>
              后重试
            </template>
            <template v-else>暂无质量控制数据，可先登记质控样品</template>
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot pager-foot">
      <span>
        共 {{ total }} 条质量控制记录 · 第 {{ total ? page : 0 }} / {{ lastPage }} 屏
        <em v-if="page >= lastPage && total > 0" class="last-page-hint">（已在最后一屏）</em>
      </span>
      <span class="pager-controls">
        <label class="size-select">
          每屏
          <select v-model.number="size" @change="changePageSize">
            <option v-for="option in sizeOptions" :key="option" :value="option">{{ option }}</option>
          </select>
          条
        </label>
        <button class="btn ghost" type="button" :disabled="page <= 1 || loading" @click="goPage(page - 1)">上一屏</button>
        <button
          class="btn ghost"
          type="button"
          :disabled="page >= lastPage || loading"
          :title="page >= lastPage ? '已经是最后一屏' : ''"
          @click="goPage(page + 1)"
        >
          下一屏
        </button>
      </span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'
import { loadQcState, saveQcState } from './query_cache'

type Row = Record<string, string | number | null>
type SortDir = 'asc' | 'desc'

interface Filters {
  code: string
  category: string
  standardMin: string
  standardMax: string
  deviationMin: string
  deviationMax: string
  status: string
}

interface ListPayload {
  items?: Row[]
  total?: number
  page?: number
  size?: number
  stats?: Record<string, number>
  categories?: string[]
  notice?: string
  detail?: string
}

const ENDPOINT = '/api/qc'
const DEFAULT_SORT_FIELD = '质控编号'
const columns = ["质控编号", "质控类别", "标准值", "允许偏差", "实测值", "判定结果", "检测日期", "质控状态"]
const sortableColumns = ["质控编号", "质控类别", "标准值", "允许偏差"]
const actions = ["检测质控", "确认受控", "标记失控"]
const statuses = ["待检测", "检测中", "受控", "失控"]
const sizeOptions = [10, 20, 50]

const route = useRoute()
const router = useRouter()

const rows = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(10)
const sortField = ref(DEFAULT_SORT_FIELD)
const sortDir = ref<SortDir>('asc')
const categoryOptions = ref<string[]>([])
const stats = ref<Record<string, number>>({})
const errorMessage = ref('')
const notice = ref('')
const loading = ref(false)
const filters = ref<Filters>({
  code: '',
  category: '',
  standardMin: '',
  standardMax: '',
  deviationMin: '',
  deviationMax: '',
  status: '',
})

const statCards = computed(() => [
  { label: '待检质控品', value: stats.value['待检质控品'] ?? 0 },
  { label: '受控质控品', value: stats.value['受控质控品'] ?? 0 },
  { label: '失控质控品', value: stats.value['失控质控品'] ?? 0 },
])

const lastPage = computed(() => Math.max(1, Math.ceil(total.value / size.value)))
const hasActiveFilters = computed(() => Object.values(filters.value).some((value) => value.trim() !== ''))

const activeChips = computed(() => {
  const chips: string[] = []
  const value = filters.value
  if (value.code) chips.push(`质控编号含“${value.code}”`)
  if (value.category) chips.push(`质控类别＝${value.category}`)
  if (value.standardMin || value.standardMax) {
    chips.push(`标准值 ${value.standardMin || '…'} ~ ${value.standardMax || '…'}`)
  }
  if (value.deviationMin || value.deviationMax) {
    chips.push(`允许偏差 ${value.deviationMin || '…'} ~ ${value.deviationMax || '…'}`)
  }
  if (value.status) chips.push(`质控状态＝${value.status}`)
  chips.push(`按${sortField.value}${sortDir.value === 'asc' ? '升序' : '降序'}`)
  return chips
})

const validationMessage = computed(() => {
  const ranges: Array<[string, string, string]> = [
    ['标准值', filters.value.standardMin, filters.value.standardMax],
    ['允许偏差', filters.value.deviationMin, filters.value.deviationMax],
  ]
  for (const [label, minText, maxText] of ranges) {
    if (minText.trim() && !Number.isFinite(Number(minText))) {
      return `${label}下限「${minText}」不是有效数字，请修正后再查询`
    }
    if (maxText.trim() && !Number.isFinite(Number(maxText))) {
      return `${label}上限「${maxText}」不是有效数字，请修正后再查询`
    }
    if (minText.trim() && maxText.trim() && Number(minText) > Number(maxText)) {
      return `${label}的下限（${minText}）大于上限（${maxText}），两个条件互斥，请调整区间后再查询`
    }
  }
  return ''
})

function sortMark(column: string): string {
  if (sortField.value !== column) return '↕'
  return sortDir.value === 'asc' ? '↑' : '↓'
}

function toggleSort(column: string) {
  if (!sortableColumns.includes(column)) return
  if (sortField.value === column) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = column
    sortDir.value = 'asc'
  }
  clearTimeout(debounceTimer)
  page.value = 1
  void reload()
}

function submitSearch() {
  if (validationMessage.value) return
  clearTimeout(debounceTimer)
  page.value = 1
  void reload()
}

function resetFilters() {
  filters.value = {
    code: '',
    category: '',
    standardMin: '',
    standardMax: '',
    deviationMin: '',
    deviationMax: '',
    status: '',
  }
  // 本次重置由这里统一发请求，通知 watcher 跳过，避免同一条件重复加载
  filterSignature = JSON.stringify(filters.value)
  clearTimeout(debounceTimer)
  sortField.value = DEFAULT_SORT_FIELD
  sortDir.value = 'asc'
  page.value = 1
  notice.value = ''
  errorMessage.value = ''
  void reload()
}

function changePageSize() {
  clearTimeout(debounceTimer)
  page.value = 1
  void reload()
}

function goPage(target: number) {
  if (target < 1 || target > lastPage.value || target === page.value) return
  clearTimeout(debounceTimer)
  page.value = target
  void reload()
}

function buildQuery(withPaging = true): URLSearchParams {
  const params = new URLSearchParams()
  const value = filters.value
  if (value.code) params.set('code', value.code.trim())
  if (value.category) params.set('category', value.category.trim())
  if (value.standardMin) params.set('standard_min', value.standardMin.trim())
  if (value.standardMax) params.set('standard_max', value.standardMax.trim())
  if (value.deviationMin) params.set('deviation_min', value.deviationMin.trim())
  if (value.deviationMax) params.set('deviation_max', value.deviationMax.trim())
  if (value.status) params.set('status', value.status.trim())
  params.set('sort_field', sortField.value)
  params.set('sort_dir', sortDir.value)
  if (withPaging) {
    params.set('page', String(page.value))
    params.set('size', String(size.value))
  }
  return params
}

function persistState() {
  const snapshot = {
    filters: { ...filters.value },
    sortField: sortField.value,
    sortDir: sortDir.value,
    page: page.value,
    size: size.value,
  }
  saveQcState(snapshot)
  const query: Record<string, string> = {}
  buildQuery().forEach((value, key) => {
    query[key] = value
  })
  void router.replace({ path: '/qc', query })
}

let requestSeq = 0

async function reload() {
  if (validationMessage.value) return
  persistState()
  const seq = ++requestSeq
  loading.value = true
  errorMessage.value = ''
  notice.value = ''
  try {
    const response = await request(`${ENDPOINT}?${buildQuery().toString()}`)
    const payload = (await response.json().catch(() => null)) as ListPayload | null
    // 连续调整时只接受最后一次请求的结果，避免列表、数量指标与条件错位
    if (seq !== requestSeq) return
    if (!response.ok) {
      throw new Error(typeof payload?.detail === 'string' ? payload.detail : '质控样品列表读取失败')
    }
    // 列表、总数、统计卡片来自同一次响应，原子更新，保证数量与当前列表不错位
    rows.value = payload?.items ?? []
    total.value = payload?.total ?? 0
    stats.value = payload?.stats ?? {}
    categoryOptions.value = Array.from(
      new Set([...(payload?.categories ?? []), ...(filters.value.category ? [filters.value.category] : [])]),
    )
    notice.value = payload?.notice ?? ''
    if (payload?.page && payload.page !== page.value) {
      page.value = payload.page
      persistState()
    }
  } catch (error) {
    if (seq !== requestSeq) return
    errorMessage.value = error instanceof Error ? error.message : '质量控制列表读取失败'
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

function exportRows() {
  window.open(`${ENDPOINT}/export?${buildQuery(false).toString()}`, '_blank')
}

function openCreate() {
  errorMessage.value = '质控样品登记入口尚未接入审批流'
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

function hydrateFromQuery() {
  const get = (key: string): string => {
    const value = route.query[key]
    return Array.isArray(value) ? String(value[0] ?? '') : String(value ?? '')
  }
  const hasUrlCondition = Object.keys(route.query).some((key) => key !== 'size')
  const cached = hasUrlCondition ? null : loadQcState()
  if (cached) {
    filters.value = { ...cached.filters }
    sortField.value = cached.sortField
    sortDir.value = cached.sortDir
    page.value = cached.page
    size.value = cached.size
    return
  }
  filters.value = {
    code: get('code'),
    category: get('category'),
    standardMin: get('standard_min'),
    standardMax: get('standard_max'),
    deviationMin: get('deviation_min'),
    deviationMax: get('deviation_max'),
    status: get('status'),
  }
  sortField.value = sortableColumns.includes(get('sort_field')) ? get('sort_field') : DEFAULT_SORT_FIELD
  sortDir.value = get('sort_dir') === 'desc' ? 'desc' : 'asc'
  const queryPage = Number.parseInt(get('page'), 10)
  page.value = Number.isFinite(queryPage) && queryPage > 0 ? queryPage : 1
  const querySize = Number.parseInt(get('size'), 10)
  size.value = sizeOptions.includes(querySize) ? querySize : 10
}

// 筛选条件变化时自动刷新（输入即时反馈，页码回到第一屏）。
// filterSignature 记录上一次已生效的条件快照：程序化写入（重置、恢复缓存）已各自触发加载，
// 这里直接跳过，避免同一份条件重复请求；连续输入做 300ms 防抖，由请求序号保证最终一致。
let filterSignature = ''
let debounceTimer: ReturnType<typeof setTimeout> | undefined

watch(
  filters,
  (value) => {
    const signature = JSON.stringify(value)
    if (signature === filterSignature) return
    filterSignature = signature
    if (validationMessage.value) return
    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      page.value = 1
      void reload()
    }, 300)
  },
  { deep: true },
)

onMounted(() => {
  hydrateFromQuery()
  filterSignature = JSON.stringify(filters.value)
  void reload()
})
</script>

<style scoped>
.range-inputs {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.range-inputs input {
  width: 68px;
}
.range-inputs em {
  color: var(--muted);
  font-style: normal;
}
.sortable {
  cursor: pointer;
  white-space: nowrap;
  user-select: none;
}
.sortable:hover {
  background: #eef4ff;
}
.sortable.active {
  color: var(--brand);
}
.sort-mark {
  margin-left: 4px;
  font-size: 11px;
  color: var(--brand);
}
.banner {
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 13px;
  margin-bottom: 10px;
}
.banner-error {
  background: #fef3f2;
  border: 1px solid #fecdca;
  color: #b42318;
}
.banner-notice {
  background: #fffaeb;
  border: 1px solid #fedf89;
  color: #b54708;
}
.active-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin: -2px 0 10px;
  font-size: 12px;
  color: var(--muted);
}
.chip {
  background: #eef4ff;
  color: #1d4ed8;
  border-radius: 999px;
  padding: 2px 10px;
}
.pager-foot {
  align-items: center;
}
.pager-controls {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.size-select {
  color: var(--muted);
}
.size-select select {
  margin: 0 2px;
}
.last-page-hint {
  color: #b54708;
  font-style: normal;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
