<template>
  <section class="page" data-module="plant-board">
    <header class="page-head">
      <div>
        <h2>运维责任看板</h2>
        <p class="page-desc">按运维负责人分组排列电站卡片，横向对比各人的责任范围；点击负责人只看其名下电站，再点一次恢复全部。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" :disabled="loading" @click="reload">
          {{ loading ? '刷新中…' : '刷新看板' }}
        </button>
      </div>
    </header>

    <div v-if="errorMessage" class="board-alert" role="alert">
      <span>{{ errorMessage }}</span>
      <button class="btn primary" type="button" :disabled="loading" @click="reload">重试</button>
    </div>

    <div class="owner-compare">
      <button
        v-for="group in owners"
        :key="group.owner"
        class="owner-chip"
        :class="{ active: selectedOwner === group.owner }"
        type="button"
        :title="`只看${group.owner}名下电站`"
        @click="toggleOwner(group.owner)"
      >
        <span class="owner-name">{{ group.owner }}</span>
        <span class="owner-running">{{ group.running }}<small> 座运行</small></span>
        <span class="owner-meta">共 {{ group.total }} 座 · {{ group.capacity_mw }} MW</span>
        <span class="owner-bar"><i :style="{ width: barWidth(group) }"></i></span>
      </button>
      <p v-if="!owners.length && !loading" class="empty-state">暂无电站数据，请先在电站档案中登记</p>
    </div>

    <p v-if="selectedOwner" class="filter-hint">
      当前只看「{{ selectedOwner }}」名下的 {{ visibleStations }} 座电站，
      <button class="link" type="button" @click="toggleOwner(selectedOwner)">恢复全部</button>
    </p>

    <div class="board-columns">
      <section v-for="group in visibleOwners" :key="group.owner" class="board-column">
        <header
          class="column-head"
          :class="{ active: selectedOwner === group.owner }"
          @click="toggleOwner(group.owner)"
        >
          <strong>{{ group.owner }}</strong>
          <span class="column-stat">运行 {{ group.running }} / {{ group.total }} 座</span>
          <span class="column-stat">装机 {{ group.capacity_mw }} MW</span>
        </header>
        <article v-for="station in group.stations" :key="station.id" class="station-card">
          <header class="station-head">
            <span class="station-code">{{ station['电站编号'] }}</span>
            <span class="status-pill" :data-status="station['电站状态']">{{ station['电站状态'] }}</span>
          </header>
          <p class="station-capacity">装机容量：{{ station['装机容量'] }}</p>
        </article>
      </section>
    </div>

    <footer class="page-foot">
      <span>共 {{ owners.length }} 名负责人 · {{ totalStations }} 座电站</span>
      <span v-if="lastUpdated">最近更新 {{ lastUpdated }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type StationCard = {
  id: number
  电站编号: string
  装机容量: string
  电站状态: string
}

type OwnerGroup = {
  owner: string
  total: number
  running: number
  capacity_mw: number
  stations: StationCard[]
}

type BoardPayload = {
  owners: OwnerGroup[]
}

const ENDPOINT = '/api/plant/board'

const owners = ref<OwnerGroup[]>([])
const selectedOwner = ref<string | null>(null)
const errorMessage = ref('')
const loading = ref(false)
const lastUpdated = ref('')

const visibleOwners = computed(() =>
  selectedOwner.value ? owners.value.filter((group) => group.owner === selectedOwner.value) : owners.value,
)
const visibleStations = computed(() =>
  visibleOwners.value.reduce((sum, group) => sum + group.total, 0),
)
const totalStations = computed(() => owners.value.reduce((sum, group) => sum + group.total, 0))
const maxRunning = computed(() => Math.max(1, ...owners.value.map((group) => group.running)))

function barWidth(group: OwnerGroup): string {
  return `${Math.round((group.running / maxRunning.value) * 100)}%`
}

function toggleOwner(owner: string) {
  selectedOwner.value = selectedOwner.value === owner ? null : owner
}

async function reload() {
  loading.value = true
  try {
    const payload = await fetchJson<BoardPayload>(ENDPOINT)
    owners.value = payload.owners ?? []
    if (selectedOwner.value && !owners.value.some((group) => group.owner === selectedOwner.value)) {
      selectedOwner.value = null
    }
    lastUpdated.value = new Date().toLocaleTimeString()
    errorMessage.value = ''
  } catch (error) {
    const detail = error instanceof Error ? error.message : '数据读取中断'
    // 读取失败时保留上一版看板数据，只提示重试，不清空页面
    errorMessage.value = owners.value.length
      ? `${detail}：看板仍显示上一版数据（${lastUpdated.value || '此前'}更新），请检查网络连接后点击重试。`
      : `${detail}：看板暂时无法加载，请检查网络连接后点击重试。`
  } finally {
    loading.value = false
  }
}

onMounted(reload)
</script>

<style scoped>
.board-alert {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  background: #fef3f2;
  border: 1px solid #fecdca;
  color: #b42318;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
  font-size: 13px;
}
.owner-compare {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.owner-chip {
  flex: 1;
  min-width: 160px;
  text-align: left;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.owner-chip.active {
  border-color: var(--brand);
  box-shadow: 0 0 0 1px var(--brand);
}
.owner-name { font-size: 13px; color: var(--muted); }
.owner-running { font-size: 22px; font-weight: 600; }
.owner-running small { font-size: 12px; font-weight: 400; color: var(--muted); }
.owner-meta { font-size: 12px; color: var(--muted); }
.owner-bar { display: block; height: 4px; background: #eef2f7; border-radius: 2px; overflow: hidden; }
.owner-bar i { display: block; height: 100%; background: var(--brand); border-radius: 2px; }
.filter-hint { font-size: 13px; color: var(--muted); margin: 0 0 12px; }
.board-columns {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  overflow-x: auto;
  padding-bottom: 4px;
}
.board-column {
  flex: 1 1 0;
  min-width: 220px;
  background: #f1f4f9;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.column-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
  cursor: pointer;
  padding: 2px 4px 8px;
  border-bottom: 1px solid var(--border);
}
.column-head.active strong { color: var(--brand); }
.column-stat { font-size: 12px; color: var(--muted); }
.station-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
}
.station-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.station-code { font-weight: 600; font-size: 13px; }
.station-capacity { margin: 6px 0 0; font-size: 12px; color: var(--muted); }
.status-pill {
  font-size: 12px;
  border-radius: 999px;
  padding: 2px 8px;
  background: #eef2f7;
  color: var(--muted);
  white-space: nowrap;
}
.status-pill[data-status='并网运行'] { background: #dcfae6; color: #067647; }
.status-pill[data-status='建设中'] { background: #e0eaff; color: #1f6feb; }
.status-pill[data-status='停运维护'] { background: #fef0c7; color: #b54708; }
.status-pill[data-status='已退役'] { background: #eef2f7; color: var(--muted); }
</style>
