<script lang="ts" setup>
import { computed, markRaw, nextTick, onMounted, ref } from "vue"
import {
  ChatDotRound,
  Collection,
  Files,
  MagicStick,
  School,
  UserFilled
} from "@element-plus/icons-vue"
import SvgDashboard from "../images/dashboard.svg?component"
import { useUserStore } from "@/pinia/stores/user"
import {
  getActiveStudentsApi,
  getAssistantRankingApi,
  getClassRankingApi,
  getConversationTrendApi,
  getOverviewApi
} from "@/common/apis/dashboard"
import type {
  AssistantRankingItem,
  ChartDataPoint,
  ClassRankingItem,
  OverviewData
} from "@/common/apis/dashboard/type"
import { use } from "echarts/core"
import { BarChart, LineChart } from "echarts/charts"
import { GridComponent, TooltipComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"
import dayjs from "dayjs"
import VChart from "vue-echarts"

use([CanvasRenderer, LineChart, BarChart, TooltipComponent, GridComponent])

const userStore = useUserStore()
const username = userStore.username

const loading = ref(true)
const timeRange = ref<"24h" | "7d" | "30d">("7d")
const overviewData = ref<OverviewData | null>(null)
const activeStudentsData = ref<ChartDataPoint[]>([])
const conversationTrendData = ref<ChartDataPoint[]>([])
const assistantRankingData = ref<AssistantRankingItem[]>([])
const classRankingData = ref<ClassRankingItem[]>([])
const displayedValues = ref<Record<string, number>>({})
const lastUpdatedAt = ref("--")

const metricIcons = {
  students: markRaw(UserFilled),
  classes: markRaw(School),
  conversations: markRaw(ChatDotRound),
  assistants: markRaw(MagicStick),
  files: markRaw(Files),
  knowledgebases: markRaw(Collection)
}

const rangeLabelMap: Record<"24h" | "7d" | "30d", string> = {
  "24h": "24 小时",
  "7d": "7 天",
  "30d": "30 天"
}

const overviewCards = computed(() => [
  {
    key: "student_count",
    label: "学生数量",
    caption: "当前纳入统计的学生总量",
    value: overviewData.value?.student_count ?? 0,
    icon: metricIcons.students,
    tone: "blue"
  },
  {
    key: "class_count",
    label: "班级数量",
    caption: "已建立教学关系的班级",
    value: overviewData.value?.class_count ?? 0,
    icon: metricIcons.classes,
    tone: "slate"
  },
  {
    key: "conversation_count",
    label: "会话数量",
    caption: "累计记录的教学对话",
    value: overviewData.value?.conversation_count ?? 0,
    icon: metricIcons.conversations,
    tone: "amber"
  },
  {
    key: "assistant_count",
    label: "助教数量",
    caption: "当前可用的 AI 助教实例",
    value: overviewData.value?.assistant_count ?? 0,
    icon: metricIcons.assistants,
    tone: "violet"
  },
  {
    key: "file_count",
    label: "文件数量",
    caption: "上传并纳入管理的文件",
    value: overviewData.value?.file_count ?? 0,
    icon: metricIcons.files,
    tone: "rose"
  },
  {
    key: "knowledgebase_count",
    label: "知识库数量",
    caption: "可供检索与问答的知识库",
    value: overviewData.value?.knowledgebase_count ?? 0,
    icon: metricIcons.knowledgebases,
    tone: "emerald"
  }
])

const assistantRankingList = computed(() => assistantRankingData.value.map(item => ({
  label: item.assistant_name,
  value: item.call_count
})))

const classRankingList = computed(() => classRankingData.value.map(item => ({
  label: item.class_name,
  value: item.conversation_count
})))

const timeRangeSummary = computed(() => `观察窗口 · 最近 ${rangeLabelMap[timeRange.value]}`)

function animateValue(key: string, endValue: number, duration: number = 900) {
  const startTime = Date.now()

  function update() {
    const elapsed = Date.now() - startTime
    const progress = Math.min(elapsed / duration, 1)
    const easeOut = 1 - (1 - progress) ** 3
    displayedValues.value[key] = Math.floor(endValue * easeOut)

    if (progress < 1) {
      requestAnimationFrame(update)
    }
  }

  requestAnimationFrame(update)
}

function formatMetric(value: number) {
  return value.toLocaleString()
}

function formatTime(time: string, range: "24h" | "7d" | "30d") {
  if (range === "24h") {
    return dayjs(time).format("HH:mm")
  }
  return dayjs(time).format("MM-DD")
}

function buildTooltip(title: string, value: number | string, suffix: string, accent: string) {
  return `<div style="min-width: 132px; padding: 2px 0;">
    <div style="color: #64748b; font-size: 12px; line-height: 1.4;">${title}</div>
    <div style="margin-top: 6px; color: ${accent}; font-size: 16px; font-weight: 600; line-height: 1.2;">
      ${value}${suffix}
    </div>
  </div>`
}

function createLineOption(config: {
  data: ChartDataPoint[]
  lineColor: string
  fillColor: string
  yAxisName: string
  seriesName: string
  valueSuffix: string
}) {
  return {
    animationDuration: 600,
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(255, 255, 255, 0.98)",
      borderColor: "#E2E8F0",
      borderWidth: 1,
      textStyle: { color: "#0f172a", fontSize: 12 },
      extraCssText: "border-radius: 14px; box-shadow: 0 12px 30px rgba(15, 23, 42, 0.10);",
      formatter: (params: Array<{ axisValue: string, value: number }>) => {
        const [param] = params
        return buildTooltip(param.axisValue, param.value, config.valueSuffix, config.lineColor)
      }
    },
    grid: {
      left: "2%",
      right: "2%",
      top: 26,
      bottom: 8,
      containLabel: true
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: config.data.map(item => formatTime(item.time, timeRange.value)),
      axisLine: {
        lineStyle: {
          color: "#E2E8F0"
        }
      },
      axisTick: { show: false },
      axisLabel: {
        color: "#64748B",
        fontSize: 12,
        margin: 12
      },
      splitLine: { show: false }
    },
    yAxis: {
      type: "value",
      name: config.yAxisName,
      nameGap: 18,
      nameTextStyle: {
        color: "#94A3B8",
        fontSize: 12,
        padding: [0, 0, 0, 6]
      },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: "#64748B",
        fontSize: 12,
        margin: 12
      },
      splitLine: {
        lineStyle: {
          color: "#EEF2F7"
        }
      }
    },
    series: [
      {
        name: config.seriesName,
        type: "line",
        data: config.data.map(item => item.count),
        smooth: true,
        symbol: "circle",
        symbolSize: 6,
        showSymbol: false,
        lineStyle: {
          width: 2.5,
          color: config.lineColor
        },
        itemStyle: {
          color: config.lineColor,
          borderColor: "#FFFFFF",
          borderWidth: 2
        },
        emphasis: {
          focus: "series",
          scale: true,
          itemStyle: {
            color: config.lineColor
          }
        },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: config.fillColor },
              { offset: 1, color: "rgba(255, 255, 255, 0)" }
            ]
          }
        }
      }
    ]
  }
}

function createRankingOption(data: Array<{ label: string, value: number }>, accent: string, unit: string) {
  const reversedData = [...data].reverse()
  const maxValue = Math.max(...data.map(item => item.value), 0)
  const colors = reversedData.map((_, index) => {
    const opacity = Math.max(0.38, 0.92 - index * 0.08)
    const channel = accent === "blue" ? "37, 99, 235" : "15, 23, 42"
    return `rgba(${channel}, ${opacity})`
  })

  return {
    animationDuration: 650,
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: "rgba(255, 255, 255, 0.98)",
      borderColor: "#E2E8F0",
      borderWidth: 1,
      textStyle: { color: "#0f172a", fontSize: 12 },
      extraCssText: "border-radius: 14px; box-shadow: 0 12px 30px rgba(15, 23, 42, 0.10);",
      formatter: (params: Array<{ dataIndex: number, name: string, value: number }>) => {
        const [param] = params
        const rank = data.length - param.dataIndex
        return buildTooltip(`${String(rank).padStart(2, "0")} · ${param.name}`, param.value.toLocaleString(), ` ${unit}`, accent === "blue" ? "#2563EB" : "#0F172A")
      }
    },
    grid: {
      left: "2%",
      right: "6%",
      top: 10,
      bottom: 4,
      containLabel: true
    },
    xAxis: {
      type: "value",
      max: maxValue === 0 ? 1 : undefined,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: "#94A3B8",
        fontSize: 11,
        margin: 10
      },
      splitLine: {
        lineStyle: {
          color: "#EEF2F7"
        }
      }
    },
    yAxis: {
      type: "category",
      data: reversedData.map(item => item.label),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: "#334155",
        fontSize: 12,
        width: 118,
        overflow: "truncate",
        margin: 18
      }
    },
    series: [
      {
        type: "bar",
        data: reversedData.map((item, index) => ({
          value: item.value,
          itemStyle: {
            color: colors[index],
            borderRadius: 999
          }
        })),
        barWidth: 12,
        label: {
          show: true,
          position: "right",
          distance: 10,
          color: "#0F172A",
          fontSize: 12,
          fontWeight: 600,
          formatter: (params: { value: number }) => params.value.toLocaleString()
        }
      }
    ]
  }
}

const activeStudentsOption = computed(() => createLineOption({
  data: activeStudentsData.value,
  lineColor: "#2563EB",
  fillColor: "rgba(37, 99, 235, 0.16)",
  yAxisName: "人数",
  seriesName: "活跃学生",
  valueSuffix: " 人"
}))

const conversationTrendOption = computed(() => createLineOption({
  data: conversationTrendData.value,
  lineColor: "#0F172A",
  fillColor: "rgba(15, 23, 42, 0.10)",
  yAxisName: "会话数",
  seriesName: "会话数",
  valueSuffix: " 次"
}))

const assistantRankingOption = computed(() => createRankingOption(assistantRankingList.value, "blue", "次调用"))

const classRankingOption = computed(() => createRankingOption(classRankingList.value, "slate", "次会话"))

async function fetchOverviewData() {
  try {
    const res = await getOverviewApi()
    if (res.code === 0 && res.data) {
      overviewData.value = res.data
      await nextTick()
      overviewCards.value.forEach(card => {
        animateValue(card.key, card.value)
      })
    }
  } catch (error) {
    console.error("获取基础指标失败:", error)
  }
}

async function fetchTrendData() {
  loading.value = true
  try {
    const [activeStudentsRes, conversationTrendRes, assistantRankingRes, classRankingRes] = await Promise.all([
      getActiveStudentsApi({ range: timeRange.value }),
      getConversationTrendApi({ range: timeRange.value }),
      getAssistantRankingApi({ range: timeRange.value, limit: 10 }),
      getClassRankingApi({ range: timeRange.value, limit: 10 })
    ])

    if (activeStudentsRes.code === 0 && activeStudentsRes.data) {
      activeStudentsData.value = activeStudentsRes.data
    }
    if (conversationTrendRes.code === 0 && conversationTrendRes.data) {
      conversationTrendData.value = conversationTrendRes.data
    }
    if (assistantRankingRes.code === 0 && assistantRankingRes.data) {
      assistantRankingData.value = assistantRankingRes.data
    }
    if (classRankingRes.code === 0 && classRankingRes.data) {
      classRankingData.value = classRankingRes.data
    }
    lastUpdatedAt.value = dayjs().format("YYYY.MM.DD HH:mm")
  } catch (error) {
    console.error("获取趋势数据失败:", error)
  } finally {
    loading.value = false
  }
}

function handleTimeRangeChange(range: "24h" | "7d" | "30d") {
  timeRange.value = range
  fetchTrendData()
}

onMounted(() => {
  fetchOverviewData()
  fetchTrendData()
})
</script>

<template>
  <div v-loading="loading" class="teacher-dashboard app-container">
    <div class="dashboard-content">
      <section class="hero-panel panel-card">
        <div class="hero-copy">
          <span class="hero-kicker">Dashboard</span>
          <h1 class="hero-title">欢迎回来，{{ username || '老师' }}</h1>
          <p class="hero-description">
            集中查看学生活跃、会话趋势与教学资源运行情况，让日常教学判断更快、更清晰。
          </p>
          <div class="hero-footnote">
            <span class="hero-footnote-item">{{ timeRangeSummary }}</span>
            <span class="hero-footnote-dot" />
            <span class="hero-footnote-item">最近更新 · {{ lastUpdatedAt }}</span>
          </div>
        </div>

        <div class="hero-illustration">
          <SvgDashboard class="hero-graphic" />
        </div>

        <div class="hero-actions">
          <div class="time-range-selector">
            <el-radio-group v-model="timeRange">
              <el-radio-button label="24h" @click="handleTimeRangeChange('24h')">24 小时</el-radio-button>
              <el-radio-button label="7d" @click="handleTimeRangeChange('7d')">7 天</el-radio-button>
              <el-radio-button label="30d" @click="handleTimeRangeChange('30d')">30 天</el-radio-button>
            </el-radio-group>
          </div>
        </div>
      </section>

      <section class="metrics-grid">
        <article
          v-for="card in overviewCards"
          :key="card.key"
          class="metric-card panel-card"
        >
          <div class="metric-card-top">
            <div :class="['metric-icon', `is-${card.tone}`]">
              <component :is="card.icon" />
            </div>
            <span class="metric-label">{{ card.label }}</span>
          </div>
          <div class="metric-value">{{ formatMetric(displayedValues[card.key] ?? 0) }}</div>
          <p class="metric-caption">{{ card.caption }}</p>
        </article>
      </section>

      <section class="chart-grid two-columns">
        <article class="chart-card panel-card">
          <header class="section-header">
            <div>
              <p class="section-eyebrow">Students</p>
              <h3 class="section-title">活跃学生趋势</h3>
            </div>
            <span class="section-meta">{{ rangeLabelMap[timeRange] }}</span>
          </header>
          <v-chart class="chart-view" :option="activeStudentsOption" autoresize />
        </article>

        <article class="chart-card panel-card">
          <header class="section-header">
            <div>
              <p class="section-eyebrow">Conversations</p>
              <h3 class="section-title">会话趋势</h3>
            </div>
            <span class="section-meta">{{ rangeLabelMap[timeRange] }}</span>
          </header>
          <v-chart class="chart-view" :option="conversationTrendOption" autoresize />
        </article>
      </section>

      <section class="chart-grid two-columns ranking-grid">
        <article class="chart-card panel-card ranking-card">
          <header class="section-header">
            <div>
              <p class="section-eyebrow">Assistants</p>
              <h3 class="section-title">助教调用排行</h3>
            </div>
            <span class="section-meta">Top 10</span>
          </header>
          <v-chart class="chart-view ranking-view" :option="assistantRankingOption" autoresize />
        </article>

        <article class="chart-card panel-card ranking-card">
          <header class="section-header">
            <div>
              <p class="section-eyebrow">Classes</p>
              <h3 class="section-title">班级活跃排行</h3>
            </div>
            <span class="section-meta">Top 10</span>
          </header>
          <v-chart class="chart-view ranking-view" :option="classRankingOption" autoresize />
        </article>
      </section>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.teacher-dashboard {
  color: var(--color-text-primary);
}

.dashboard-content {
  width: 100%;
  max-width: 1540px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}

.panel-card {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(226, 232, 240, 0.7);
  border-radius: 24px;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.04);
}

.hero-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(240px, 0.7fr);
  gap: 32px;
  padding: 32px;
  align-items: center;
}

.hero-copy {
  min-width: 0;
}

.hero-kicker {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.04);
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-title {
  margin: 18px 0 10px;
  color: var(--color-text-primary);
  font-size: clamp(30px, 4vw, 40px);
  line-height: 1.05;
  font-weight: 700;
  letter-spacing: -0.04em;
}

.hero-description {
  max-width: 620px;
  margin: 0;
  color: var(--color-text-tertiary);
  font-size: 15px;
  line-height: 1.7;
}

.hero-footnote {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 20px;
  color: #64748b;
  font-size: 13px;
}

.hero-footnote-dot {
  width: 4px;
  height: 4px;
  border-radius: 999px;
  background: #cbd5e1;
}

.hero-illustration {
  display: flex;
  justify-content: center;
  margin-bottom: 16px;
}

.hero-graphic {
  width: min(100%, 280px);
  height: auto;
  opacity: 0.92;
}

.hero-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 16px;
}

.time-range-selector {
  width: 100%;

  :deep(.el-radio-group) {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 6px;
    width: 100%;
    padding: 6px;
    border-radius: 18px;
    background: rgba(15, 23, 42, 0.04);

    .el-radio-button__inner {
      width: 100%;
      padding: 11px 14px;
      border: none;
      border-radius: 14px;
      background: transparent;
      box-shadow: none;
      color: var(--color-text-tertiary);
      font-size: 13px;
      font-weight: 600;
      transition: all var(--transition-base) var(--ease-out);
    }

    .el-radio-button:first-child .el-radio-button__inner,
    .el-radio-button:last-child .el-radio-button__inner {
      border-radius: 14px;
    }

    .el-radio-button__original-radio:checked + .el-radio-button__inner {
      background: #ffffff;
      color: var(--color-text-primary);
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06), inset 0 0 0 1px rgba(226, 232, 240, 0.9);
    }
  }
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 18px;
}

.metric-card {
  padding: 20px;
}

.metric-card-top {
  display: flex;
  align-items: center;
  gap: 14px;
}

.metric-icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  :deep(svg) {
    width: 20px;
    height: 20px;
  }

  &.is-blue {
    background: rgba(37, 99, 235, 0.10);
    color: #2563eb;
  }

  &.is-slate {
    background: rgba(15, 23, 42, 0.08);
    color: #0f172a;
  }

  &.is-amber {
    background: rgba(245, 158, 11, 0.12);
    color: #b45309;
  }

  &.is-violet {
    background: rgba(124, 58, 237, 0.10);
    color: #7c3aed;
  }

  &.is-rose {
    background: rgba(225, 29, 72, 0.10);
    color: #be123c;
  }

  &.is-emerald {
    background: rgba(16, 185, 129, 0.10);
    color: #059669;
  }
}

.metric-label {
  color: var(--color-text-secondary);
  font-size: 14px;
  font-weight: 600;
}

.metric-value {
  margin-top: 24px;
  color: var(--color-text-primary);
  font-size: clamp(28px, 2.6vw, 36px);
  line-height: 1;
  font-weight: 700;
  letter-spacing: -0.04em;
  font-feature-settings: "tnum";
}

.metric-caption {
  margin: 12px 0 0;
  color: var(--color-text-tertiary);
  font-size: 13px;
  line-height: 1.6;
}

.chart-grid {
  display: grid;
  gap: 20px;
}

.two-columns {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.chart-card {
  padding: 24px;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.section-eyebrow {
  margin: 0 0 6px;
  color: var(--color-text-disabled);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.section-title {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.section-meta {
  flex-shrink: 0;
  padding: 7px 10px;
  border-radius: 999px;
  background: rgba(248, 250, 252, 0.92);
  color: var(--color-text-tertiary);
  font-size: 12px;
  font-weight: 600;
}

.chart-view {
  height: 304px;
}

.ranking-grid {
  margin-top: -4px;
}

.ranking-view {
  height: 360px;
}

@media (max-width: 1440px) {
  .metrics-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1120px) {
  .hero-panel,
  .two-columns {
    grid-template-columns: 1fr;
  }

  .hero-actions {
    align-items: stretch;
  }
}

@media (max-width: 768px) {
  .hero-panel,
  .chart-card,
  .metric-card {
    padding: 20px;
  }

  .metrics-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
  }

  .chart-view {
    height: 260px;
  }

  .ranking-view {
    height: 320px;
  }
}

@media (max-width: 560px) {
  .dashboard-content {
    gap: 16px;
  }

  .hero-panel {
    gap: 20px;
  }

  .hero-title {
    font-size: 28px;
  }

  .metrics-grid {
    grid-template-columns: 1fr;
  }

  .section-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
