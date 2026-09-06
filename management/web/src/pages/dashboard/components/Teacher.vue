<script lang="ts" setup>
import { computed, markRaw, nextTick, onMounted, ref } from "vue"
import {
  ArrowRight,
  ChatDotRound,
  CircleCheck,
  CircleClose,
  Collection,
  DataAnalysis,
  Files,
  MagicStick,
  QuestionFilled,
  School,
  UserFilled,
  WarningFilled
} from "@element-plus/icons-vue"
import SvgDashboard from "../images/dashboard.svg?component"
import { useUserStore } from "@/pinia/stores/user"
import {
  getActiveStudentsApi,
  getAssistantRankingApi,
  getClassRankingApi,
  getConversationTrendApi,
  getLearningInsightsApi,
  getOverviewApi,
  getStudentLearningDetailApi
} from "@/common/apis/dashboard"
import type {
  LearningInsightsData,
  LearningInsightStudent,
  StudentLearningDetailData
} from "@/common/apis/dashboard"
import type {
  AssistantRankingItem,
  ChartDataPoint,
  ClassRankingItem,
  OverviewData
} from "@/common/apis/dashboard/type"
import { getTeacherProgressRemindersApi } from "@/common/apis/progress"
import type { TeacherProgressReminderItem, TeacherProgressReminderResult } from "@/common/apis/progress/type"
import { use } from "echarts/core"
import { BarChart, LineChart } from "echarts/charts"
import { GridComponent, TooltipComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"
import dayjs from "dayjs"
import VChart from "vue-echarts"
import { useRouter } from "vue-router"

use([CanvasRenderer, LineChart, BarChart, TooltipComponent, GridComponent])

const userStore = useUserStore()
const username = userStore.username
const router = useRouter()

const loading = ref(true)
const timeRange = ref<"24h" | "7d" | "30d">("7d")
const overviewData = ref<OverviewData | null>(null)
const activeStudentsData = ref<ChartDataPoint[]>([])
const conversationTrendData = ref<ChartDataPoint[]>([])
const assistantRankingData = ref<AssistantRankingItem[]>([])
const classRankingData = ref<ClassRankingItem[]>([])
const displayedValues = ref<Record<string, number>>({})
const lastUpdatedAt = ref("--")
const progressReminderData = ref<TeacherProgressReminderResult | null>(null)
const progressReminderLoading = ref(false)
const learningInsights = ref<LearningInsightsData | null>(null)
const learningInsightsLoading = ref(false)
const insightClassId = ref("")
const insightSection = ref<HTMLElement | null>(null)
const studentDetailVisible = ref(false)
const studentDetailLoading = ref(false)
const selectedStudentDetail = ref<StudentLearningDetailData | null>(null)
const detailActiveTab = ref<"quiz" | "questions">("quiz")

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

async function fetchProgressReminders() {
  progressReminderLoading.value = true
  try {
    const res = await getTeacherProgressRemindersApi()
    if (res.code === 0 && res.data) {
      progressReminderData.value = res.data
    }
  } catch (error) {
    console.error("获取周进度提醒失败:", error)
  } finally {
    progressReminderLoading.value = false
  }
}

async function fetchLearningInsights() {
  learningInsightsLoading.value = true
  try {
    const res = await getLearningInsightsApi({
      range: timeRange.value,
      class_id: insightClassId.value || undefined,
      limit: 10
    })
    if (res.code === 0 && res.data) {
      learningInsights.value = res.data
    }
  } catch (error) {
    console.error("获取学习洞察失败:", error)
  } finally {
    learningInsightsLoading.value = false
  }
}

async function openStudentDetail(student: LearningInsightStudent, tab: "quiz" | "questions" = "quiz") {
  detailActiveTab.value = tab
  studentDetailVisible.value = true
  studentDetailLoading.value = true
  selectedStudentDetail.value = null
  try {
    const res = await getStudentLearningDetailApi(student.student_id, { range: timeRange.value })
    if (res.code === 0 && res.data) {
      selectedStudentDetail.value = res.data
    }
  } catch (error) {
    console.error("获取学生学习明细失败:", error)
  } finally {
    studentDetailLoading.value = false
  }
}

function focusLearningInsights() {
  insightSection.value?.scrollIntoView({ behavior: "smooth", block: "start" })
}

function openConversationManagement() {
  router.push("/conversation/index")
}

function accuracyTone(accuracy: number) {
  if (accuracy >= 80) return "is-good"
  if (accuracy >= 60) return "is-medium"
  return "is-risk"
}

function progressStateLabel(item: TeacherProgressReminderItem) {
  if (item.state === "overdue") return `逾期 ${item.day_count} 天`
  if (item.state === "upcoming") return `${item.day_count} 天后开始`
  if (item.day_count === 0) return "今天截止"
  return `剩余 ${item.day_count} 天`
}

function openProgressDetail(item?: TeacherProgressReminderItem) {
  if (!item) {
    router.push("/progress/index")
    return
  }
  router.push({
    path: "/progress/index",
    query: { class_id: item.class_id, progress_id: item.id }
  })
}

function handleTimeRangeChange(range: "24h" | "7d" | "30d") {
  timeRange.value = range
  fetchTrendData()
  fetchLearningInsights()
}

onMounted(() => {
  fetchOverviewData()
  fetchTrendData()
  fetchProgressReminders()
  fetchLearningInsights()
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

      <section v-loading="progressReminderLoading" class="progress-reminder-panel panel-card">
        <header class="progress-reminder-header">
          <div>
            <p class="section-eyebrow progress-eyebrow">Weekly progress</p>
            <h2 class="progress-reminder-title">周进度提醒</h2>
            <p class="progress-reminder-description">
              及时查看哪些学生已经跟上节奏，哪些学生还需要提醒。
            </p>
          </div>
          <div class="progress-reminder-actions">
            <div class="reminder-summary-chip is-attention">
              <strong>{{ progressReminderData?.summary.total_incomplete_students ?? 0 }}</strong>
              <span>人次未完成</span>
            </div>
            <div class="reminder-summary-chip">
              <strong>{{ progressReminderData?.summary.overdue_progresses ?? 0 }}</strong>
              <span>项已逾期</span>
            </div>
            <el-button type="primary" plain :icon="ArrowRight" @click="openProgressDetail()">
              全部进度
            </el-button>
          </div>
        </header>

        <div v-if="progressReminderData?.items.length" class="progress-reminder-grid">
          <article
            v-for="item in progressReminderData.items.slice(0, 4)"
            :key="item.id"
            :class="['progress-reminder-card', `is-${item.state}`]"
          >
            <div class="progress-card-head">
              <div class="progress-class-copy">
                <span class="progress-class-name">{{ item.class_name }}</span>
                <h3>{{ item.name }}</h3>
              </div>
              <el-tag
                :type="item.state === 'overdue' ? 'danger' : item.state === 'active' ? 'warning' : 'info'"
                effect="light"
                round
              >
                {{ progressStateLabel(item) }}
              </el-tag>
            </div>

            <div class="progress-rate-row">
              <el-progress
                :percentage="item.completion_rate"
                :stroke-width="8"
                :color="item.incomplete_count === 0 ? '#16a36a' : item.state === 'overdue' ? '#dc5a3a' : '#d89920'"
              />
              <span>{{ item.completed_count }}/{{ item.total_students }} 人</span>
            </div>

            <div class="student-status-list">
              <div class="student-status-row is-completed">
                <CircleCheck />
                <span class="status-label">已完成</span>
                <span class="student-names">
                  {{ item.completed_students.slice(0, 3).map(s => s.student_name).join('、') || '暂无' }}
                  <template v-if="item.completed_students.length > 3">等 {{ item.completed_students.length }} 人</template>
                </span>
              </div>
              <div class="student-status-row is-incomplete">
                <CircleClose />
                <span class="status-label">未完成</span>
                <span class="student-names">
                  {{ item.incomplete_students.slice(0, 3).map(s => s.student_name).join('、') || '暂无' }}
                  <template v-if="item.incomplete_students.length > 3">等 {{ item.incomplete_students.length }} 人</template>
                </span>
              </div>
            </div>

            <button class="progress-detail-link" type="button" @click="openProgressDetail(item)">
              查看每个文档完成情况
              <ArrowRight />
            </button>
          </article>
        </div>
        <el-empty v-else description="暂时没有已发布的周进度" :image-size="88" />
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

      <section ref="insightSection" v-loading="learningInsightsLoading" class="learning-insight-panel panel-card">
        <header class="learning-insight-header">
          <div>
            <p class="section-eyebrow insight-eyebrow">Learning intelligence</p>
            <h2 class="learning-insight-title">学生学习洞察</h2>
            <p class="learning-insight-description">
              查看每名学生做过的题、答错记录和实际提问，快速定位全班共性难点。
            </p>
          </div>
          <el-select
            v-model="insightClassId"
            class="insight-class-select"
            placeholder="全部班级"
            clearable
            @change="fetchLearningInsights"
          >
            <el-option label="全部班级" value="" />
            <el-option
              v-for="classItem in learningInsights?.classes || []"
              :key="classItem.id"
              :label="classItem.name"
              :value="classItem.id"
            />
          </el-select>
        </header>

        <div class="insight-summary-grid">
          <div class="insight-summary-item is-blue">
            <el-icon><UserFilled /></el-icon>
            <span>活跃学生</span>
            <strong>{{ learningInsights?.summary.active_student_count ?? 0 }}</strong>
            <small>/ {{ learningInsights?.summary.student_count ?? 0 }} 人</small>
          </div>
          <div class="insight-summary-item is-slate">
            <el-icon><DataAnalysis /></el-icon>
            <span>累计答题</span>
            <strong>{{ learningInsights?.summary.quiz_attempt_count ?? 0 }}</strong>
            <small>次</small>
          </div>
          <div class="insight-summary-item is-red">
            <el-icon><WarningFilled /></el-icon>
            <span>错误作答</span>
            <strong>{{ learningInsights?.summary.wrong_answer_count ?? 0 }}</strong>
            <small>次</small>
          </div>
          <button class="insight-summary-item is-amber is-action" type="button" @click="openConversationManagement">
            <el-icon><QuestionFilled /></el-icon>
            <span>学生提问</span>
            <strong>{{ learningInsights?.summary.question_count ?? 0 }}</strong>
            <small>次 · 查看会话</small>
          </button>
        </div>

        <div class="learning-insight-grid">
          <article class="student-activity-card">
            <div class="insight-card-heading">
              <div>
                <span class="insight-card-index">01</span>
                <h3>每个学生做了什么</h3>
              </div>
              <span class="section-meta">{{ rangeLabelMap[timeRange] }}</span>
            </div>
            <el-table
              :data="learningInsights?.students || []"
              class="student-insight-table"
              height="430"
              empty-text="当前时间范围内还没有学生数据"
              @row-click="row => openStudentDetail(row)"
            >
              <el-table-column label="学生" min-width="170" fixed>
                <template #default="{ row }">
                  <div class="student-identity">
                    <span class="student-avatar">{{ row.student_name.slice(0, 1) }}</span>
                    <span>
                      <strong>{{ row.student_name }}</strong>
                      <small>{{ row.student_email }}</small>
                    </span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="class_names" label="班级" min-width="120" show-overflow-tooltip />
              <el-table-column prop="quiz_attempts" label="答题" width="70" align="center" />
              <el-table-column prop="wrong_answers" label="答错" width="70" align="center">
                <template #default="{ row }">
                  <span :class="{ 'wrong-number': row.wrong_answers > 0 }">{{ row.wrong_answers }}</span>
                </template>
              </el-table-column>
              <el-table-column label="正确率" width="104">
                <template #default="{ row }">
                  <span :class="['accuracy-pill', accuracyTone(row.accuracy)]">{{ row.accuracy }}%</span>
                </template>
              </el-table-column>
              <el-table-column label="提问" width="70" align="center">
                <template #default="{ row }">
                  <el-button link type="primary" @click.stop="openStudentDetail(row, 'questions')">
                    {{ row.question_count }}
                  </el-button>
                </template>
              </el-table-column>
              <el-table-column label="最近活跃" width="145">
                <template #default="{ row }">
                  <span class="last-active-text">{{ row.last_active_at ? formatTime(row.last_active_at, timeRange) : '暂无活动' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="明细" width="82" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click.stop="openStudentDetail(row)">查看</el-button>
                </template>
              </el-table-column>
            </el-table>
          </article>

          <article class="wrong-question-card">
            <div class="insight-card-heading">
              <div>
                <span class="insight-card-index is-red">02</span>
                <h3>全班高频错题</h3>
              </div>
              <span class="section-meta">Top 10</span>
            </div>
            <div v-if="learningInsights?.wrong_questions.length" class="wrong-question-list">
              <div
                v-for="(question, index) in learningInsights.wrong_questions"
                :key="`${question.doc_id}-${question.question_index}`"
                class="wrong-question-item"
              >
                <span class="wrong-question-rank">{{ String(index + 1).padStart(2, '0') }}</span>
                <div class="wrong-question-copy">
                  <strong>{{ question.question }}</strong>
                  <span>{{ question.document_name }}</span>
                  <small>正确答案：{{ question.correct_answer }}</small>
                </div>
                <div class="wrong-question-score">
                  <strong>{{ question.wrong_rate }}%</strong>
                  <span>{{ question.wrong_count }}/{{ question.attempt_count }} 次答错</span>
                  <small>{{ question.wrong_student_count }} 名学生</small>
                </div>
              </div>
            </div>
            <el-empty v-else :image-size="82" description="当前时间范围内还没有错题记录" />
          </article>
        </div>
      </section>

      <section class="chart-grid two-columns">
        <article class="chart-card panel-card">
          <header class="section-header">
            <div>
              <p class="section-eyebrow">Students</p>
              <h3 class="section-title">活跃学生趋势</h3>
            </div>
            <el-button link type="primary" :icon="ArrowRight" @click="focusLearningInsights">查看学生明细</el-button>
          </header>
          <v-chart class="chart-view" :option="activeStudentsOption" autoresize />
        </article>

        <article class="chart-card panel-card">
          <header class="section-header">
            <div>
              <p class="section-eyebrow">Conversations</p>
              <h3 class="section-title">会话趋势</h3>
            </div>
            <el-button link type="primary" :icon="ArrowRight" @click="openConversationManagement">查看提问内容</el-button>
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

    <el-drawer
      v-model="studentDetailVisible"
      class="student-detail-drawer"
      size="min(760px, 94vw)"
      :with-header="false"
      destroy-on-close
    >
      <div v-loading="studentDetailLoading" class="student-detail-shell">
        <template v-if="selectedStudentDetail">
          <header class="student-detail-header">
            <div class="detail-student-avatar">{{ selectedStudentDetail.student.student_name.slice(0, 1) }}</div>
            <div class="detail-student-copy">
              <p>{{ selectedStudentDetail.student.class_names }}</p>
              <h2>{{ selectedStudentDetail.student.student_name }}</h2>
              <span>{{ selectedStudentDetail.student.student_email }}</span>
            </div>
            <el-button text @click="studentDetailVisible = false">关闭</el-button>
          </header>

          <div class="student-detail-summary">
            <div><strong>{{ selectedStudentDetail.summary.quiz_attempt_count }}</strong><span>答题次数</span></div>
            <div><strong>{{ selectedStudentDetail.summary.correct_answer_count }}</strong><span>答对</span></div>
            <div class="is-wrong"><strong>{{ selectedStudentDetail.summary.wrong_answer_count }}</strong><span>答错</span></div>
            <div><strong>{{ selectedStudentDetail.summary.accuracy }}%</strong><span>正确率</span></div>
            <div><strong>{{ selectedStudentDetail.summary.question_count }}</strong><span>提问次数</span></div>
          </div>

          <el-tabs v-model="detailActiveTab" class="student-detail-tabs">
            <el-tab-pane :label="`答题明细 ${selectedStudentDetail.quiz_attempts.length}`" name="quiz">
              <div v-if="selectedStudentDetail.quiz_attempts.length" class="detail-record-list">
                <article
                  v-for="(attempt, index) in selectedStudentDetail.quiz_attempts"
                  :key="attempt.id"
                  :class="['quiz-attempt-item', attempt.is_correct ? 'is-correct' : 'is-wrong']"
                >
                  <div class="record-marker">
                    <CircleCheck v-if="attempt.is_correct" />
                    <CircleClose v-else />
                  </div>
                  <div class="record-main">
                    <div class="record-meta">
                      <span>{{ attempt.document_name }}</span>
                      <small>{{ formatTime(attempt.answered_at, timeRange) }} · 第 {{ index + 1 }} 条</small>
                    </div>
                    <h4>{{ attempt.question }}</h4>
                    <div class="answer-comparison">
                      <span>学生作答 <strong>{{ attempt.student_answer }}</strong></span>
                      <span v-if="!attempt.is_correct">正确答案 <strong>{{ attempt.correct_answer }}</strong></span>
                    </div>
                  </div>
                </article>
              </div>
              <el-empty v-else :image-size="96" description="该学生暂时没有答题记录" />
            </el-tab-pane>
            <el-tab-pane :label="`提问记录 ${selectedStudentDetail.questions.length}`" name="questions">
              <div v-if="selectedStudentDetail.questions.length" class="detail-question-list">
                <article v-for="question in selectedStudentDetail.questions" :key="question.id" class="detail-question-item">
                  <div class="question-bubble-icon"><QuestionFilled /></div>
                  <div>
                    <p>{{ question.content }}</p>
                    <span>{{ question.assistant_name }} · {{ question.conversation_name }}</span>
                    <small>{{ formatTime(question.asked_at, timeRange) }}</small>
                  </div>
                </article>
              </div>
              <el-empty v-else :image-size="96" description="该学生暂时没有提问记录" />
            </el-tab-pane>
          </el-tabs>
        </template>
      </div>
    </el-drawer>
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

.progress-reminder-panel {
  padding: 26px;
  overflow: hidden;
  background:
    radial-gradient(circle at 100% 0, rgba(245, 158, 11, 0.08), transparent 32%),
    rgba(255, 255, 255, 0.94);
}

.progress-reminder-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 22px;
}

.progress-eyebrow {
  color: #b77914;
}

.progress-reminder-title {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.025em;
}

.progress-reminder-description {
  margin: 8px 0 0;
  color: var(--color-text-tertiary);
  font-size: 13px;
}

.progress-reminder-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.reminder-summary-chip {
  min-width: 96px;
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 9px 12px;
  border-radius: 13px;
  color: #64748b;
  background: #f8fafc;

  strong {
    color: #334155;
    font-size: 18px;
    font-variant-numeric: tabular-nums;
  }

  span {
    font-size: 11px;
  }

  &.is-attention {
    color: #9a6510;
    background: #fff7e2;

    strong {
      color: #b36f08;
    }
  }
}

.progress-reminder-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.progress-reminder-card {
  position: relative;
  overflow: hidden;
  padding: 18px;
  border: 1px solid #e5eaf0;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.88);

  &::before {
    content: "";
    position: absolute;
    inset: 0 auto 0 0;
    width: 3px;
    background: #d89920;
  }

  &.is-overdue::before {
    background: #dc5a3a;
  }

  &.is-upcoming::before {
    background: #7890ad;
  }
}

.progress-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.progress-class-copy {
  min-width: 0;

  h3 {
    overflow: hidden;
    margin: 5px 0 0;
    color: #1e293b;
    font-size: 16px;
    font-weight: 650;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.progress-class-name {
  color: #94a3b8;
  font-size: 11px;
  font-weight: 650;
}

.progress-rate-row {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 14px;
  margin: 18px 0 14px;

  > span {
    color: #64748b;
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }

  :deep(.el-progress__text) {
    min-width: 38px;
    color: #475569;
    font-size: 11px !important;
  }
}

.student-status-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.student-status-row {
  display: grid;
  grid-template-columns: 18px 46px 1fr;
  align-items: center;
  gap: 5px;
  min-width: 0;
  color: #64748b;
  font-size: 11px;

  > svg {
    width: 15px;
    height: 15px;
  }

  &.is-completed > svg {
    color: #16a36a;
  }

  &.is-incomplete > svg {
    color: #dc5a3a;
  }
}

.status-label {
  font-weight: 650;
}

.student-names {
  overflow: hidden;
  color: #475569;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-detail-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 15px;
  padding: 0;
  border: 0;
  color: #8a641b;
  background: transparent;
  cursor: pointer;
  font-size: 11px;
  font-weight: 650;

  > svg {
    width: 13px;
  }
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

.learning-insight-panel {
  padding: 28px;
  overflow: hidden;
  background:
    radial-gradient(circle at 96% 0, rgba(37, 99, 235, 0.07), transparent 30%),
    rgba(255, 255, 255, 0.96);
  scroll-margin-top: 92px;
}

.learning-insight-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

.insight-eyebrow {
  color: #2563eb;
}

.learning-insight-title {
  margin: 0;
  color: #172033;
  font-size: 24px;
  font-weight: 720;
  letter-spacing: -0.03em;
}

.learning-insight-description {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.insight-class-select {
  width: 210px;

  :deep(.el-select__wrapper) {
    min-height: 42px;
    border-radius: 13px;
  }
}

.insight-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 24px 0 20px;
}

.insight-summary-item {
  display: grid;
  grid-template-columns: 36px 1fr auto auto;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 14px 16px;
  border: 1px solid #e8edf4;
  border-radius: 16px;
  color: #475569;
  background: #fbfcfe;
  text-align: left;

  .el-icon {
    width: 34px;
    height: 34px;
    border-radius: 11px;
    background: #edf4ff;
    color: #2563eb;
    font-size: 17px;
  }

  > span {
    overflow: hidden;
    font-size: 12px;
    font-weight: 650;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  strong {
    color: #172033;
    font-size: 23px;
    font-variant-numeric: tabular-nums;
  }

  small {
    color: #94a3b8;
    font-size: 11px;
  }

  &.is-slate .el-icon {
    color: #334155;
    background: #eef1f5;
  }

  &.is-red .el-icon {
    color: #c24135;
    background: #fff0ed;
  }

  &.is-amber .el-icon {
    color: #b77914;
    background: #fff7e2;
  }

  &.is-action {
    appearance: none;
    cursor: pointer;
    transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;

    &:hover {
      border-color: #f1cf83;
      box-shadow: 0 10px 24px rgba(151, 103, 17, 0.09);
      transform: translateY(-1px);
    }
  }
}

.learning-insight-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(330px, 0.8fr);
  gap: 18px;
}

.student-activity-card,
.wrong-question-card {
  min-width: 0;
  padding: 18px;
  border: 1px solid #e8edf4;
  border-radius: 19px;
  background: rgba(251, 252, 254, 0.86);
}

.insight-card-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;

  > div {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  h3 {
    margin: 0;
    color: #25324a;
    font-size: 15px;
    font-weight: 680;
  }
}

.insight-card-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 9px;
  color: #2563eb;
  background: #eaf2ff;
  font-size: 10px;
  font-weight: 800;

  &.is-red {
    color: #c24135;
    background: #fff0ed;
  }
}

.student-insight-table {
  --el-table-border-color: #edf0f5;
  --el-table-header-bg-color: #f5f7fa;
  --el-table-row-hover-bg-color: #f2f7ff;
  border-radius: 13px;
  cursor: pointer;

  :deep(th.el-table__cell) {
    height: 42px;
    color: #64748b;
    font-size: 11px;
    font-weight: 700;
  }

  :deep(td.el-table__cell) {
    padding: 10px 0;
  }
}

.student-identity {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;

  > span:last-child {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  strong,
  small {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  strong {
    color: #273349;
    font-size: 13px;
  }

  small {
    margin-top: 2px;
    color: #94a3b8;
    font-size: 10px;
  }
}

.student-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 31px;
  height: 31px;
  flex: 0 0 31px;
  border-radius: 10px;
  color: #215cc5;
  background: #e8f0ff;
  font-size: 12px;
  font-weight: 800;
}

.wrong-number {
  color: #c24135;
  font-weight: 750;
}

.accuracy-pill {
  display: inline-flex;
  min-width: 50px;
  justify-content: center;
  padding: 4px 7px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 750;

  &.is-good {
    color: #14754d;
    background: #e9f8f0;
  }

  &.is-medium {
    color: #9a6510;
    background: #fff5db;
  }

  &.is-risk {
    color: #b13b31;
    background: #ffefec;
  }
}

.last-active-text {
  color: #64748b;
  font-size: 11px;
}

.wrong-question-list {
  display: flex;
  height: 430px;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  padding-right: 3px;
}

.wrong-question-item {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: flex-start;
  padding: 13px;
  border: 1px solid #edf0f5;
  border-radius: 13px;
  background: #fff;
}

.wrong-question-rank {
  padding-top: 2px;
  color: #c24135;
  font-size: 11px;
  font-weight: 800;
}

.wrong-question-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;

  strong {
    display: -webkit-box;
    overflow: hidden;
    color: #273349;
    font-size: 12px;
    line-height: 1.45;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }

  span,
  small {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  span {
    margin-top: 6px;
    color: #8491a5;
    font-size: 10px;
  }

  small {
    margin-top: 3px;
    color: #64748b;
    font-size: 10px;
  }
}

.wrong-question-score {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  min-width: 72px;

  strong {
    color: #c24135;
    font-size: 17px;
    font-variant-numeric: tabular-nums;
  }

  span,
  small {
    margin-top: 3px;
    color: #94a3b8;
    font-size: 9px;
    white-space: nowrap;
  }
}

.student-detail-shell {
  min-height: 100%;
  color: #172033;
}

.student-detail-header {
  display: grid;
  grid-template-columns: 52px 1fr auto;
  align-items: center;
  gap: 14px;
  padding-bottom: 20px;
  border-bottom: 1px solid #edf0f5;
}

.detail-student-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 17px;
  color: #fff;
  background: #2563eb;
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.22);
  font-size: 20px;
  font-weight: 800;
}

.detail-student-copy {
  min-width: 0;

  p,
  h2 {
    margin: 0;
  }

  p {
    color: #2563eb;
    font-size: 10px;
    font-weight: 750;
    letter-spacing: 0.08em;
  }

  h2 {
    margin-top: 3px;
    font-size: 22px;
    letter-spacing: -0.02em;
  }

  span {
    display: block;
    overflow: hidden;
    margin-top: 3px;
    color: #94a3b8;
    font-size: 11px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.student-detail-summary {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
  margin: 20px 0 10px;

  > div {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 12px 8px;
    border-radius: 13px;
    background: #f5f7fa;
  }

  strong {
    font-size: 18px;
    font-variant-numeric: tabular-nums;
  }

  span {
    margin-top: 4px;
    color: #8491a5;
    font-size: 10px;
  }

  .is-wrong strong {
    color: #c24135;
  }
}

.student-detail-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 14px;
  }
}

.detail-record-list,
.detail-question-list {
  display: flex;
  max-height: calc(100vh - 250px);
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
  padding: 2px 4px 18px 1px;
}

.quiz-attempt-item {
  display: grid;
  grid-template-columns: 32px 1fr;
  gap: 11px;
  padding: 14px;
  border: 1px solid #e7edf4;
  border-radius: 15px;
  background: #fbfcfe;

  &.is-wrong {
    border-color: #f3d4ce;
    background: #fff9f7;
  }
}

.record-marker {
  padding-top: 2px;

  svg {
    width: 20px;
    height: 20px;
    color: #16a36a;
  }

  .is-wrong & svg {
    color: #c24135;
  }
}

.record-main {
  min-width: 0;

  h4 {
    margin: 8px 0 10px;
    color: #273349;
    font-size: 13px;
    line-height: 1.55;
  }
}

.record-meta,
.answer-comparison {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.record-meta {
  color: #2563eb;
  font-size: 10px;
  font-weight: 700;

  small {
    color: #94a3b8;
    font-weight: 500;
  }
}

.answer-comparison {
  justify-content: flex-start;
  flex-wrap: wrap;

  span {
    padding: 6px 9px;
    border-radius: 9px;
    color: #64748b;
    background: #eef2f7;
    font-size: 10px;
  }

  strong {
    margin-left: 4px;
    color: #273349;
  }
}

.detail-question-item {
  display: grid;
  grid-template-columns: 34px 1fr;
  gap: 12px;
  padding: 15px;
  border: 1px solid #e5ebf3;
  border-radius: 15px;
  background: #fbfcfe;

  p {
    margin: 0 0 9px;
    color: #273349;
    font-size: 13px;
    line-height: 1.65;
    white-space: pre-wrap;
  }

  span,
  small {
    display: block;
    color: #7b8799;
    font-size: 10px;
  }

  small {
    margin-top: 4px;
    color: #a0aabb;
  }
}

.question-bubble-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 11px;
  color: #b77914;
  background: #fff5db;

  svg {
    width: 17px;
    height: 17px;
  }
}

@media (max-width: 1440px) {
  .metrics-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .learning-insight-grid {
    grid-template-columns: 1fr;
  }

  .wrong-question-list {
    height: auto;
    max-height: 430px;
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

  .progress-reminder-header {
    flex-direction: column;
  }

  .progress-reminder-actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .insight-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
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

  .progress-reminder-grid {
    grid-template-columns: 1fr;
  }

  .learning-insight-panel {
    padding: 20px;
  }

  .learning-insight-header {
    flex-direction: column;
  }

  .insight-class-select {
    width: 100%;
  }

  .student-detail-summary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
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

  .insight-summary-grid {
    grid-template-columns: 1fr;
  }

  .insight-summary-item {
    grid-template-columns: 36px 1fr auto auto;
  }

  .section-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
