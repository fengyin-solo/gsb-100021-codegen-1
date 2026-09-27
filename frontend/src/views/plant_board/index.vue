<template>
  <section class="page" data-module="plant-owner-board">
    <header class="page-head">
      <div>
        <h2>运维责任看板</h2>
        <p class="page-desc">
          按运维负责人分组排列电站卡片，一眼比较各人的责任范围；点击负责人只看其名下记录，再点一次恢复全部。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" :disabled="loading" @click="reload">
          {{ loading ? '刷新中…' : '刷新看板' }}
        </button>
        <RouterLink class="btn ghost" to="/plant">返回电站档案列表</RouterLink>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in summaryCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div v-if="errorMessage" class="board-banner" role="alert">
      <div>
        <strong>{{ board ? '最新数据读取中断，当前仍展示上一版看板。' : '看板数据读取中断，暂时没有可展示的内容。' }}</strong>
        <span class="banner-detail">{{ errorMessage }}</span>
      </div>
      <button class="btn primary" type="button" :disabled="loading" @click="reload">
        {{ loading ? '重试中…' : '重新加载' }}
      </button>
    </div>

    <template v-if="board">
      <div v-if="activeOwner" class="focus-tip">
        <span>当前只展示 <strong>{{ activeOwner }}</strong> 名下 {{ activeGroup?.total ?? 0 }} 座电站</span>
        <button class="link" type="button" @click="clearFocus">恢复全部负责人</button>
      </div>

      <div class="owner-tabs" role="group" aria-label="按负责人筛选">
        <button
          v-for="group in board.groups"
          :key="group.owner"
          type="button"
          class="owner-tab"
          :class="{ active: activeOwner === group.owner }"
          :aria-pressed="activeOwner === group.owner"
          @click="toggleOwner(group.owner)"
        >
          <span class="owner-name">{{ group.owner }}</span>
          <span class="owner-meta">{{ group.total }} 座 · 运行 {{ group.running }}</span>
        </button>
      </div>

      <div class="board-columns">
        <section
          v-for="group in visibleGroups"
          :key="group.owner"
          class="owner-column"
          :class="{ focused: activeOwner === group.owner }"
        >
          <header class="column-head" role="button" tabindex="0" @click="toggleOwner(group.owner)"
                  @keyup.enter="toggleOwner(group.owner)" @keyup.space.prevent="toggleOwner(group.owner)">
            <div class="column-title">
              <h3>{{ group.owner }}</h3>
              <span v-if="activeOwner === group.owner" class="focus-badge">聚焦中，再点恢复</span>
            </div>
            <div class="column-kpis">
              <span class="kpi running"><strong>{{ group.running }}</strong> 运行</span>
              <span class="kpi"><strong>{{ group.total }}</strong> 总数</span>
              <span class="kpi"><strong>{{ formatCapacity(group.capacity_mw) }}</strong> MW</span>
            </div>
            <div class="capacity-bar" :title="`占全部装机容量的 ${capacityShare(group.capacity_mw)}%`">
              <span class="capacity-fill" :style="{ width: capacityShare(group.capacity_mw) + '%' }"></span>
            </div>
            <div class="status-line">
              <span
                v-for="status in board.statuses"
                :key="status"
                class="status-chip"
                :class="statusClass(status)"
              >
                {{ status }} {{ group.status_breakdown[status] ?? 0 }}
              </span>
            </div>
          </header>

          <ul class="plant-list">
            <li v-for="plant in group.plants" :key="String(plant.id)" class="plant-card"
                :class="statusClass(plant.status)">
              <div class="plant-top">
                <span class="plant-code">{{ plant['电站编号'] ?? '—' }}</span>
                <span class="plant-status" :class="statusClass(plant.status)">{{ plant.status ?? '未知' }}</span>
              </div>
              <p class="plant-name">{{ plant['电站名称'] ?? '未命名电站' }}</p>
              <dl class="plant-fields">
                <div>
                  <dt>装机容量</dt>
                  <dd>{{ plant['装机容量'] ?? '—' }}</dd>
                </div>
                <div>
                  <dt>所属区域</dt>
                  <dd>{{ plant['所属区域'] ?? '—' }}</dd>
                </div>
              </dl>
            </li>
          </ul>
        </section>
      </div>

      <p v-if="!visibleGroups.length" class="empty-state">没有匹配到负责人名下的电站记录。</p>
    </template>

    <div v-else-if="!loading" class="board-empty">
      <p>看板暂时没有内容。</p>
      <button class="btn primary" type="button" @click="reload">重新加载</button>
    </div>

    <footer class="page-foot">
      <span v-if="board">
        数据时间：{{ loadedAtLabel }}<template v-if="errorMessage">（读取中断，展示的是上一版数据）</template>
      </span>
      <span v-else>{{ loading ? '正在读取看板数据…' : '' }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}，可点击上方按钮重试。</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type StatusBreakdown = Record<string, number>

interface OwnerGroup {
  owner: string
  total: number
  running: number
  capacity_mw: number
  running_capacity_mw: number
  status_breakdown: StatusBreakdown
  plants: PlantRow[]
}

interface PlantRow {
  id: number
  status: string | null
  电站编号?: string
  电站名称?: string
  装机容量?: string
  所属区域?: string
  运维负责人?: string
}

interface OwnerBoard {
  total_owners: number
  total_plants: number
  total_running: number
  total_capacity_mw: number
  statuses: string[]
  groups: OwnerGroup[]
}

const ENDPOINT = '/api/plant/owner-board'

const board = ref<OwnerBoard | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const loadedAt = ref('')
const activeOwner = ref<string | null>(null)

const visibleGroups = computed<OwnerGroup[]>(() => {
  if (!board.value) {
    return []
  }
  if (!activeOwner.value) {
    return board.value.groups
  }
  return board.value.groups.filter((group) => group.owner === activeOwner.value)
})

const activeGroup = computed<OwnerGroup | undefined>(() =>
  board.value?.groups.find((group) => group.owner === activeOwner.value),
)

const summaryCards = computed(() => {
  if (!board.value) {
    return [
      { label: '运维负责人', value: '—' },
      { label: '电站总数', value: '—' },
      { label: '运行电站', value: '—' },
      { label: '总装机容量(MW)', value: '—' },
    ]
  }
  return [
    { label: '运维负责人', value: board.value.total_owners },
    { label: '电站总数', value: board.value.total_plants },
    { label: '运行电站', value: board.value.total_running },
    { label: '总装机容量(MW)', value: formatCapacity(board.value.total_capacity_mw) },
  ]
})

const loadedAtLabel = computed(() => loadedAt.value)

function formatCapacity(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function capacityShare(capacityMw: number): number {
  const total = board.value?.total_capacity_mw ?? 0
  if (!total) {
    return 0
  }
  return Math.max(2, Math.round((capacityMw / total) * 100))
}

function statusClass(status: string | null | undefined): string {
  switch (status) {
    case '并网运行':
      return 'is-running'
    case '停运维护':
      return 'is-maintenance'
    case '建设中':
      return 'is-building'
    case '已退役':
      return 'is-retired'
    default:
      return 'is-unknown'
  }
}

function toggleOwner(owner: string) {
  activeOwner.value = activeOwner.value === owner ? null : owner
}

function clearFocus() {
  activeOwner.value = null
}

async function reload() {
  loading.value = true
  // 不清空 board：读取中断时页面继续保留上一版看板。
  try {
    const payload = await fetchJson<OwnerBoard>(ENDPOINT)
    board.value = payload
    errorMessage.value = ''
    loadedAt.value = new Date().toLocaleString('zh-CN', { hour12: false })
    if (activeOwner.value && !payload.groups.some((group) => group.owner === activeOwner.value)) {
      activeOwner.value = null
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '数据读取失败'
  } finally {
    loading.value = false
  }
}

let timer: ReturnType<typeof setInterval> | undefined

onMounted(() => {
  void reload()
  timer = setInterval(() => void reload(), 30000)
})

onBeforeUnmount(() => {
  if (timer) {
    clearInterval(timer)
  }
})
</script>

<style scoped>
.page-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.btn.ghost {
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  font-size: 13px;
}

.board-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  background: #fff7ed;
  border: 1px solid #fdba74;
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #9a3412;
}
.banner-detail {
  display: block;
  margin-top: 2px;
  color: #c2410c;
  font-size: 12px;
}

.focus-tip {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #eff6ff;
  border: 1px solid #93c5fd;
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #1e40af;
}

.owner-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}
.owner-tab {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 8px;
  padding: 8px 14px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.owner-tab:hover {
  border-color: var(--brand);
}
.owner-tab.active {
  border-color: var(--brand);
  box-shadow: 0 0 0 2px rgba(31, 111, 235, 0.2);
  background: #f5f9ff;
}
.owner-name {
  font-weight: 600;
  font-size: 14px;
}
.owner-meta {
  font-size: 12px;
  color: var(--muted);
}

.board-columns {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
  align-items: start;
}
.owner-column {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
}
.owner-column.focused {
  border-color: var(--brand);
  box-shadow: 0 0 0 2px rgba(31, 111, 235, 0.15);
}
.column-head {
  cursor: pointer;
  border-bottom: 1px dashed var(--border);
  padding-bottom: 10px;
  margin-bottom: 10px;
  outline: none;
}
.column-head:focus-visible {
  border-radius: 6px;
  box-shadow: 0 0 0 2px rgba(31, 111, 235, 0.35);
}
.column-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.column-title h3 {
  margin: 0;
  font-size: 16px;
}
.focus-badge {
  font-size: 11px;
  color: var(--brand);
  background: #eff6ff;
  border-radius: 999px;
  padding: 2px 8px;
  white-space: nowrap;
}
.column-kpis {
  display: flex;
  gap: 10px;
  margin: 8px 0 6px;
  font-size: 12px;
  color: var(--muted);
}
.column-kpis .kpi strong {
  font-size: 16px;
  color: #1f2937;
  margin-right: 2px;
}
.column-kpis .kpi.running strong {
  color: #047857;
}
.capacity-bar {
  height: 6px;
  border-radius: 999px;
  background: #e5e7eb;
  overflow: hidden;
  margin-bottom: 8px;
}
.capacity-fill {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #1d4ed8);
  border-radius: 999px;
}
.status-line {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.status-chip {
  font-size: 11px;
  border-radius: 999px;
  padding: 1px 8px;
  border: 1px solid transparent;
}
.status-chip.is-running {
  color: #047857;
  background: #ecfdf5;
  border-color: #a7f3d0;
}
.status-chip.is-maintenance {
  color: #b45309;
  background: #fffbeb;
  border-color: #fcd34d;
}
.status-chip.is-building {
  color: #1d4ed8;
  background: #eff6ff;
  border-color: #bfdbfe;
}
.status-chip.is-retired {
  color: #6b7280;
  background: #f3f4f6;
  border-color: #d1d5db;
}

.plant-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.plant-card {
  border: 1px solid var(--border);
  border-left-width: 4px;
  border-radius: 8px;
  padding: 8px 10px;
  background: #fcfdff;
}
.plant-card.is-running {
  border-left-color: #10b981;
}
.plant-card.is-maintenance {
  border-left-color: #f59e0b;
}
.plant-card.is-building {
  border-left-color: #3b82f6;
}
.plant-card.is-retired {
  border-left-color: #9ca3af;
}
.plant-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.plant-code {
  font-weight: 600;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.plant-status {
  font-size: 11px;
  border-radius: 999px;
  padding: 1px 8px;
  white-space: nowrap;
}
.plant-status.is-running {
  color: #047857;
  background: #ecfdf5;
}
.plant-status.is-maintenance {
  color: #b45309;
  background: #fffbeb;
}
.plant-status.is-building {
  color: #1d4ed8;
  background: #eff6ff;
}
.plant-status.is-retired {
  color: #6b7280;
  background: #f3f4f6;
}
.plant-name {
  margin: 6px 0;
  font-size: 13px;
  color: #374151;
}
.plant-fields {
  display: flex;
  gap: 14px;
  margin: 0;
}
.plant-fields dt {
  font-size: 11px;
  color: var(--muted);
}
.plant-fields dd {
  margin: 1px 0 0;
  font-size: 13px;
  font-weight: 600;
}

.board-empty {
  background: #fff;
  border: 1px dashed var(--border);
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  color: var(--muted);
}
.empty-state {
  text-align: center;
  color: var(--muted);
  padding: 24px 0;
}
</style>
