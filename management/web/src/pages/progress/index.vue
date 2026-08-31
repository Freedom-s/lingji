<script lang="ts" setup>
import type {
  ClassDocument,
  CreateProgressData,
  ProgressStatusResult,
  StudentProgressStatus,
  WeeklyProgressItem
} from "@@/apis/progress/type"
import type { FormInstance } from "element-plus"
import {
  createWeeklyProgressApi,
  deleteWeeklyProgressApi,
  getClassDocumentsApi,
  getProgressStatusApi,
  getWeeklyProgressListApi,
  updateWeeklyProgressApi
} from "@@/apis/progress"
import { getTableDataApi } from "@@/apis/teams"
import {
  Calendar,
  CircleCheck,
  Clock,
  Delete,
  Document,
  Edit,
  Plus,
  Search,
  VideoPlay,
  View
} from "@element-plus/icons-vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { computed, onMounted, reactive, ref, watch } from "vue"
import { useRoute } from "vue-router"
import "element-plus/theme-chalk/el-message-box.css"

defineOptions({ name: "ProgressManagement" })

const loading = ref(false)
const activeTab = ref("list")
const route = useRoute()

// ============ 班级选择 ============
interface ClassOption {
  id: string
  name: string
}
const classOptions = ref<ClassOption[]>([])
const selectedClassId = ref("")

async function loadClasses() {
  const { data } = await getTableDataApi({
    currentPage: 1,
    size: 1000,
    sort_by: "id",
    sort_order: "desc"
  })
  classOptions.value = data.list.map((c: any) => ({ id: c.id, name: c.name }))
}

// ============ Tab 1: 进度列表 ============
const progressList = ref<WeeklyProgressItem[]>([])

function loadProgressList() {
  if (!selectedClassId.value) return
  loading.value = true
  getWeeklyProgressListApi(selectedClassId.value)
    .then(({ data }) => {
      progressList.value = data || []
    })
    .finally(() => (loading.value = false))
}
watch(selectedClassId, () => {
  selectedProgressId.value = ""
  statusResult.value = null
  if (activeTab.value === "list") loadProgressList()
})

// 新建/编辑弹窗
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref("")
const formRef = ref<FormInstance | null>(null)
const formData = reactive<CreateProgressData>({
  name: "",
  week_start: "",
  week_end: "",
  doc_ids: [],
  quiz_thresholds: {}
})

// 文档列表
const availableDocs = ref<ClassDocument[]>([])
const docSelection = reactive<Record<string, boolean>>({})
const docThresholds = reactive<Record<string, number>>({})
const selectedDocCount = computed(
  () => availableDocs.value.filter(doc => docSelection[doc.id]).length
)

function openCreate() {
  isEditing.value = false
  editingId.value = ""
  formData.name = ""
  formData.week_start = ""
  formData.week_end = ""
  formData.doc_ids = []
  formData.quiz_thresholds = {}
  // 重置选择
  availableDocs.value.forEach((d) => {
    docSelection[d.id] = false
    docThresholds[d.id] = 0
  })
  dialogVisible.value = true
  if (selectedClassId.value) loadDocs()
}

async function openEdit(row: WeeklyProgressItem) {
  isEditing.value = true
  editingId.value = row.id
  formData.name = row.name
  formData.week_start = row.week_start
  formData.week_end = row.week_end
  dialogVisible.value = true
  // 先加载文档列表，再根据已有进度设置选中状态
  await loadDocsAsync()
  try {
    const { data: statusData } = await getProgressStatusApi(row.id)
    const pDocs = statusData.progress.docs
    availableDocs.value.forEach((d) => {
      docSelection[d.id] = false
      docThresholds[d.id] = 0
    })
    pDocs.forEach((pd: any) => {
      docSelection[pd.doc_id] = true
      docThresholds[pd.doc_id] = pd.quiz_threshold
    })
  } catch {
    /* ignore — docs will be unselected */
  }
}

function loadDocs() {
  if (!selectedClassId.value) return
  getClassDocumentsApi(selectedClassId.value).then(({ data }) => {
    availableDocs.value = data || []
    availableDocs.value.forEach((d) => {
      if (!(d.id in docSelection)) {
        docSelection[d.id] = false
        docThresholds[d.id] = 0
      }
    })
  })
}

async function loadDocsAsync() {
  if (!selectedClassId.value) return
  const { data } = await getClassDocumentsApi(selectedClassId.value)
  availableDocs.value = data || []
  availableDocs.value.forEach((d) => {
    if (!(d.id in docSelection)) {
      docSelection[d.id] = false
      docThresholds[d.id] = 0
    }
  })
}

function buildFormFromSelection() {
  formData.doc_ids = []
  formData.quiz_thresholds = {}
  availableDocs.value.forEach((d) => {
    if (docSelection[d.id]) {
      formData.doc_ids.push(d.id)
      formData.quiz_thresholds[d.id] = d.has_quiz ? docThresholds[d.id] : 0
    }
  })
}

function handleSave() {
  if (!formData.name.trim()) {
    ElMessage.warning("请输入名称")
    return
  }
  if (!formData.week_start || !formData.week_end) {
    ElMessage.warning("请选择时间范围")
    return
  }

  buildFormFromSelection()
  if (formData.doc_ids.length === 0) {
    ElMessage.warning("至少选择1个文档")
    return
  }

  loading.value = true
  const api = isEditing.value
    ? updateWeeklyProgressApi(editingId.value, { ...formData })
    : createWeeklyProgressApi(selectedClassId.value, { ...formData })

  api
    .then(() => {
      ElMessage.success(isEditing.value ? "修改成功" : "创建成功")
      dialogVisible.value = false
      loadProgressList()
    })
    .finally(() => (loading.value = false))
}

function handleDelete(row: WeeklyProgressItem) {
  ElMessageBox.confirm(`确认删除「${row.name}」？`, "提示", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning"
  }).then(() => {
    deleteWeeklyProgressApi(row.id).then(() => {
      ElMessage.success("删除成功")
      loadProgressList()
    })
  })
}

// ============ Tab 2: 完成情况 ============
const progressOptions = ref<WeeklyProgressItem[]>([])
const selectedProgressId = ref("")
const statusResult = ref<ProgressStatusResult | null>(null)
const statusFilter = ref("all") // all | completed | incomplete

async function loadProgressOptions() {
  if (!selectedClassId.value) return
  const { data } = await getWeeklyProgressListApi(selectedClassId.value)
  progressOptions.value = data || []
}
watch(selectedClassId, () => {
  if (activeTab.value === "status") loadProgressOptions()
})

async function loadStatus() {
  if (!selectedProgressId.value) {
    statusResult.value = null
    return
  }
  loading.value = true
  try {
    const { data } = await getProgressStatusApi(selectedProgressId.value)
    statusResult.value = data
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadClasses()
  const classId
    = typeof route.query.class_id === "string" ? route.query.class_id : ""
  const progressId
    = typeof route.query.progress_id === "string" ? route.query.progress_id : ""
  const hasRequestedClass = classOptions.value.some(
    item => item.id === classId
  )
  const initialClassId = hasRequestedClass
    ? classId
    : (classOptions.value[0]?.id ?? "")
  if (!initialClassId) return

  if (!hasRequestedClass || !progressId) {
    selectedClassId.value = initialClassId
    return
  }

  activeTab.value = "status"
  selectedClassId.value = initialClassId
  await loadProgressOptions()
  if (!progressOptions.value.some(item => item.id === progressId)) return
  selectedProgressId.value = progressId
  await loadStatus()
})

const filteredStudents = ref<StudentProgressStatus[]>([])
watch(
  [statusResult, statusFilter],
  () => {
    if (!statusResult.value) {
      filteredStudents.value = []
      return
    }
    const all = statusResult.value.students
    if (statusFilter.value === "completed")
      filteredStudents.value = all.filter(s => s.is_all_completed)
    else if (statusFilter.value === "incomplete")
      filteredStudents.value = all.filter(s => !s.is_all_completed)
    else filteredStudents.value = all
  },
  { deep: true }
)

function getDocTypeTag(docType: string) {
  return docType === "video" ? "success" : "primary"
}

function getDocStatus(student: StudentProgressStatus, docId: string) {
  return student.doc_statuses?.find((d: any) => d.doc_id === docId)
}

function getDurationDays(start: string, end: string) {
  const startAt = new Date(`${start}T00:00:00`).getTime()
  const endAt = new Date(`${end}T00:00:00`).getTime()
  if (Number.isNaN(startAt) || Number.isNaN(endAt)) return 0
  return Math.max(1, Math.round((endAt - startAt) / 86400000) + 1)
}

function getStudentCompletionRate(student: StudentProgressStatus) {
  if (!student.total_docs) return 0
  return Math.round((student.total_completed / student.total_docs) * 100)
}

function getStudentInitial(name: string) {
  return Array.from(name.trim())[0]?.toUpperCase() || "学"
}
</script>

<template>
  <div class="app-container">
    <!-- 班级选择器 -->
    <el-card shadow="never" class="class-selector-card">
      <div class="class-selector-row">
        <span class="selector-label">班级：</span>
        <el-select
          v-model="selectedClassId"
          placeholder="请选择班级"
          style="width: 280px"
          clearable
        >
          <el-option
            v-for="c in classOptions"
            :key="c.id"
            :label="c.name"
            :value="c.id"
          />
        </el-select>
      </div>
    </el-card>

    <el-card v-loading="loading" shadow="never" class="main-card">
      <el-tabs
        v-model="activeTab"
        @tab-change="
          (tab) => {
            if (tab === 'list') loadProgressList();
            if (tab === 'status') loadProgressOptions();
          }
        "
      >
        <!-- Tab 1: 进度列表 -->
        <el-tab-pane label="进度列表" name="list">
          <div v-if="!selectedClassId" class="empty-hint">
            请先选择班级
          </div>
          <template v-else>
            <div class="table-toolbar">
              <div class="section-heading">
                <span class="section-kicker">PLAN LIBRARY</span>
                <div class="section-title-row">
                  <h3>进度计划</h3>
                  <span class="record-count">{{ progressList.length }} 项</span>
                </div>
                <p>统一安排每周课件、测验与学习截止时间</p>
              </div>
              <el-button
                class="create-button"
                type="primary"
                :icon="Plus"
                @click="openCreate"
              >
                新建周进度
              </el-button>
            </div>

            <div class="table-frame">
              <el-table
                class="progress-data-table"
                :data="progressList"
                empty-text="当前班级暂无进度计划"
              >
                <el-table-column prop="name" label="进度名称" min-width="220">
                  <template #default="scope">
                    <div class="plan-name-cell">
                      <span class="plan-icon"><Calendar /></span>
                      <div>
                        <strong>{{ scope.row.name }}</strong>
                        <small>周学习进度</small>
                      </div>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="学习周期" min-width="250">
                  <template #default="scope">
                    <div class="date-range-cell">
                      <div>
                        <small>开始</small>
                        <strong>{{ scope.row.week_start }}</strong>
                      </div>
                      <span class="date-connector" />
                      <div>
                        <small>截止</small>
                        <strong>{{ scope.row.week_end }}</strong>
                      </div>
                      <span class="duration-chip">
                        {{
                          getDurationDays(
                            scope.row.week_start,
                            scope.row.week_end,
                          )
                        }}
                        天
                      </span>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column
                  prop="status"
                  label="执行状态"
                  width="130"
                  align="center"
                >
                  <template #default="scope">
                    <span
                      class="status-pill" :class="[
                        scope.row.status === '1' ? 'is-active' : 'is-ended',
                      ]"
                    >
                      <i />
                      {{ scope.row.status === "1" ? "进行中" : "已结束" }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="270" align="right">
                  <template #default="scope">
                    <div class="row-actions">
                      <el-button
                        class="action-button view-action"
                        text
                        size="small"
                        :icon="View"
                        @click="
                          selectedProgressId = scope.row.id;
                          activeTab = 'status';
                          loadStatus();
                        "
                      >
                        完成情况
                      </el-button>
                      <el-button
                        class="action-button"
                        text
                        size="small"
                        :icon="Edit"
                        @click="openEdit(scope.row)"
                      >
                        编辑
                      </el-button>
                      <el-button
                        class="action-button danger-action"
                        text
                        size="small"
                        :icon="Delete"
                        @click="handleDelete(scope.row)"
                      >
                        删除
                      </el-button>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </template>
        </el-tab-pane>

        <!-- Tab 2: 完成情况 -->
        <el-tab-pane label="完成情况" name="status">
          <div v-if="!selectedClassId" class="empty-hint">
            请先选择班级
          </div>
          <template v-else>
            <div class="progress-selector-bar">
              <div class="selector-copy">
                <span class="selector-icon"><Search /></span>
                <div>
                  <strong>查看完成情况</strong>
                  <small>选择一项进度，查看学生学习明细</small>
                </div>
              </div>
              <el-select
                v-model="selectedProgressId"
                placeholder="请选择周进度"
                class="progress-select"
                @change="loadStatus"
              >
                <el-option
                  v-for="p in progressOptions"
                  :key="p.id"
                  :label="`${p.name} (${p.week_start} ~ ${p.week_end})`"
                  :value="p.id"
                />
              </el-select>
            </div>

            <template v-if="statusResult">
              <!-- 概览卡片 -->
              <section class="status-overview">
                <div class="overview-metric total-metric">
                  <span>学生总数</span>
                  <strong>{{ statusResult.summary.total_students }}</strong>
                  <small>本班参与学生</small>
                </div>
                <div class="overview-metric completed-metric">
                  <span>已完成</span>
                  <strong>{{ statusResult.summary.completed_count }}</strong>
                  <small>已达到全部要求</small>
                </div>
                <div class="overview-metric incomplete-metric">
                  <span>未完成</span>
                  <strong>{{ statusResult.summary.incomplete_count }}</strong>
                  <small>{{
                    statusResult.summary.incomplete_count > 0
                      ? "需要继续跟进"
                      : "全部按时完成"
                  }}</small>
                </div>
                <div class="completion-meter">
                  <div class="meter-copy">
                    <div>
                      <span>班级完成率</span>
                      <small>{{ statusResult.progress.name }}</small>
                    </div>
                    <strong>{{ statusResult.summary.completion_rate
                    }}<em>%</em></strong>
                  </div>
                  <el-progress
                    :percentage="statusResult.summary.completion_rate"
                    :show-text="false"
                    :stroke-width="9"
                    :color="
                      statusResult.summary.completion_rate >= 80
                        ? '#20a66a'
                        : statusResult.summary.completion_rate >= 50
                          ? '#d89920'
                          : '#e4572e'
                    "
                  />
                </div>
              </section>

              <!-- 筛选 -->
              <div class="student-table-toolbar">
                <div class="section-heading compact-heading">
                  <span class="section-kicker">STUDENT DETAILS</span>
                  <div class="section-title-row">
                    <h3>学生明细</h3>
                    <span class="record-count">{{ filteredStudents.length }} 人</span>
                  </div>
                </div>
                <el-radio-group
                  v-model="statusFilter"
                  class="status-filter"
                  size="small"
                >
                  <el-radio-button value="all">
                    全部
                  </el-radio-button>
                  <el-radio-button value="completed">
                    已完成
                  </el-radio-button>
                  <el-radio-button value="incomplete">
                    未完成
                  </el-radio-button>
                </el-radio-group>
              </div>

              <!-- 学生明细表 -->
              <div class="table-frame student-table-frame">
                <el-table
                  class="progress-data-table student-progress-table"
                  :data="filteredStudents"
                  empty-text="当前筛选条件下暂无学生"
                >
                  <el-table-column
                    prop="student_name"
                    label="学生"
                    min-width="170"
                    fixed
                  >
                    <template #default="scope">
                      <div class="student-cell">
                        <span class="student-avatar">{{
                          getStudentInitial(scope.row.student_name)
                        }}</span>
                        <div>
                          <strong>{{ scope.row.student_name }}</strong>
                          <small>{{ scope.row.total_completed }}/{{
                            scope.row.total_docs
                          }}
                            项已完成</small>
                        </div>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column
                    label="总体进度"
                    min-width="180"
                    align="center"
                  >
                    <template #default="scope">
                      <div class="student-rate-cell">
                        <el-progress
                          :percentage="getStudentCompletionRate(scope.row)"
                          :show-text="false"
                          :stroke-width="7"
                          :color="
                            scope.row.is_all_completed ? '#20a66a' : '#d89920'
                          "
                        />
                        <strong>{{ getStudentCompletionRate(scope.row) }}%</strong>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column
                    v-for="doc in statusResult.progress.docs"
                    :key="doc.doc_id"
                    min-width="150"
                    align="center"
                  >
                    <template #header>
                      <div class="document-column-header">
                        <el-tag
                          :type="getDocTypeTag(doc.doc_type)"
                          size="small"
                          effect="light"
                        >
                          {{ doc.doc_type === "video" ? "视频" : "文档" }}
                        </el-tag>
                        <span>{{ doc.doc_name }}</span>
                      </div>
                    </template>
                    <template #default="scope">
                      <span
                        v-if="getDocStatus(scope.row, doc.doc_id)?.is_completed"
                        class="document-status is-done"
                      >
                        <el-icon><CircleCheck /></el-icon>
                        已完成
                      </span>
                      <span v-else class="document-status is-pending">
                        <el-icon><Clock /></el-icon>
                        待完成
                      </span>
                    </template>
                  </el-table-column>
                  <el-table-column
                    label="最终状态"
                    width="125"
                    align="center"
                    fixed="right"
                  >
                    <template #default="scope">
                      <span
                        class="result-pill" :class="[
                          scope.row.is_all_completed
                            ? 'is-complete'
                            : 'is-incomplete',
                        ]"
                      >
                        {{ scope.row.is_all_completed ? "已完成" : "未完成" }}
                      </span>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </template>
            <div v-else class="empty-hint">
              请选择要查看的周进度
            </div>
          </template>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新建/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      class="progress-editor-dialog"
      width="min(760px, calc(100vw - 32px))"
      :close-on-click-modal="false"
      @closed="formRef?.resetFields()"
    >
      <template #header>
        <div class="editor-dialog-heading">
          <span class="editor-heading-icon"><Calendar /></span>
          <div>
            <small>{{ isEditing ? "EDIT WEEKLY PLAN" : "NEW WEEKLY PLAN" }}</small>
            <h3>{{ isEditing ? "编辑周进度" : "新建周进度" }}</h3>
            <p>设置学习周期，并选择本周需要学生完成的资料。</p>
          </div>
        </div>
      </template>

      <el-form
        ref="formRef"
        :model="formData"
        label-position="top"
        class="editor-form"
      >
        <div class="editor-form-grid">
          <el-form-item label="进度名称" required>
            <el-input
              v-model="formData.name"
              placeholder="例如：第4周学习任务"
            />
          </el-form-item>
          <el-form-item label="学习周期" required>
            <div class="date-picker-row">
              <el-date-picker
                v-model="formData.week_start"
                type="date"
                placeholder="开始日期"
                value-format="YYYY-MM-DD"
              />
              <span class="date-separator">至</span>
              <el-date-picker
                v-model="formData.week_end"
                type="date"
                placeholder="截止日期"
                value-format="YYYY-MM-DD"
              />
            </div>
          </el-form-item>
        </div>

        <el-form-item label="选择文档" required class="document-form-item">
          <div class="doc-picker">
            <header class="doc-picker-header">
              <div>
                <strong>本周学习资料</strong>
                <small>勾选资料后，可为包含测验的文档设置达标分数</small>
              </div>
              <span>{{ selectedDocCount }} / {{ availableDocs.length }} 已选</span>
            </header>

            <div class="doc-selection-list">
              <div v-if="availableDocs.length === 0" class="docs-empty">
                当前班级暂无可选择的教学资料
              </div>
              <template v-else>
                <div
                  v-for="doc in availableDocs"
                  :key="doc.id"
                  class="doc-row" :class="[{ 'is-selected': docSelection[doc.id] }]"
                >
                  <el-checkbox
                    v-model="docSelection[doc.id]"
                    class="doc-checkbox"
                  >
                    <div class="doc-identity">
                      <span
                        class="doc-kind-icon" :class="[
                          doc.type === 'video' ? 'is-video' : 'is-document',
                        ]"
                      >
                        <el-icon>
                          <VideoPlay v-if="doc.type === 'video'" />
                          <Document v-else />
                        </el-icon>
                      </span>
                      <div class="doc-copy">
                        <strong>{{ doc.name }}</strong>
                        <small>
                          {{
                            doc.type === "video"
                              ? "完成视频学习"
                              : doc.has_quiz
                                ? "完成阅读并通过测验"
                                : "完成阅读并记录笔记"
                          }}
                        </small>
                      </div>
                    </div>
                  </el-checkbox>

                  <div v-if="doc.has_quiz" class="threshold-input">
                    <span>测验达标</span>
                    <el-input-number
                      v-model="docThresholds[doc.id]"
                      :min="0"
                      :max="100"
                      :step="5"
                      controls-position="right"
                      size="small"
                    />
                    <b>%</b>
                  </div>
                  <span v-else class="completion-rule">
                    {{ doc.type === "video" ? "看完即完成" : "阅读完成" }}
                  </span>
                </div>
              </template>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="editor-dialog-footer">
          <p>已选择 <strong>{{ selectedDocCount }}</strong> 项学习资料</p>
          <div>
            <el-button @click="dialogVisible = false">
              取消
            </el-button>
            <el-button
              class="save-plan-button"
              type="primary"
              :loading="loading"
              @click="handleSave"
            >
              {{ isEditing ? "保存修改" : "创建进度" }}
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.class-selector-card {
  margin-bottom: 18px;

  :deep(.el-card__body) {
    padding: 18px 22px !important;
  }

  .class-selector-row {
    display: flex;
    align-items: center;
    gap: 14px;

    .selector-label {
      color: #334155;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.02em;
    }
  }
}

.main-card {
  :deep(.el-card__body) {
    padding: 22px 26px 28px !important;
  }

  :deep(.el-tabs__header) {
    margin-bottom: 24px;
  }

  :deep(.el-tabs__item) {
    height: 46px;
    padding: 0 22px;
    color: #64748b;
    font-weight: 650;
  }

  :deep(.el-tabs__item.is-active) {
    color: #172033;
  }

  :deep(.el-tabs__active-bar) {
    height: 3px;
    border-radius: 999px;
    background: #d89920;
  }
}

.table-toolbar,
.student-table-toolbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
}

.section-heading {
  min-width: 0;

  h3,
  p {
    margin: 0;
  }

  h3 {
    color: #172033;
    font-size: 20px;
    font-weight: 750;
    line-height: 1.3;
    letter-spacing: -0.02em;
  }

  p {
    margin-top: 5px;
    color: #94a3b8;
    font-size: 12px;
  }
}

.section-kicker {
  display: block;
  margin-bottom: 5px;
  color: #b77914;
  font-size: 9px;
  font-weight: 850;
  letter-spacing: 0.18em;
}

.section-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.record-count {
  padding: 3px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  color: #64748b;
  background: #f8fafc;
  font-size: 10px;
  font-weight: 700;
}

.create-button {
  min-height: 42px;
  padding: 0 18px !important;
  border-color: #172033 !important;
  color: white !important;
  background: #172033 !important;
  box-shadow: 0 10px 24px rgba(23, 32, 51, 0.16) !important;

  &:hover {
    border-color: #2b3b57 !important;
    background: #2b3b57 !important;
  }
}

.table-frame {
  overflow: hidden;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 18px;
  background: white;
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.045);
}

.progress-data-table {
  width: 100%;
  border: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;

  :deep(.el-table__inner-wrapper::before) {
    display: none;
  }

  :deep(th.el-table__cell) {
    height: 52px;
    padding: 0 18px !important;
    border-bottom: 1px solid #e8edf3 !important;
    color: #64748b !important;
    background: linear-gradient(180deg, #fbfcfd 0%, #f6f8fa 100%) !important;
    font-size: 11px !important;
    font-weight: 800 !important;
    letter-spacing: 0.06em;
  }

  :deep(td.el-table__cell) {
    height: 74px;
    padding: 12px 18px !important;
    border-bottom: 1px solid #eef2f6 !important;
    background: rgba(255, 255, 255, 0.96) !important;
  }

  :deep(.el-table__row:last-child td.el-table__cell) {
    border-bottom: 0 !important;
  }

  :deep(.el-table__row:hover td.el-table__cell),
  :deep(.el-table__body tr.hover-row > td.el-table__cell) {
    background: #fffdf7 !important;
  }

  :deep(.el-table__empty-block) {
    min-height: 220px;
  }

  :deep(.el-table__empty-text) {
    color: #94a3b8;
    font-size: 13px;
  }
}

.plan-name-cell,
.student-cell {
  display: flex;
  align-items: center;
  gap: 12px;

  > div {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  strong {
    overflow: hidden;
    color: #243149;
    font-size: 13px;
    font-weight: 750;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  small {
    color: #94a3b8;
    font-size: 10px;
  }
}

.plan-icon {
  flex: 0 0 auto;
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(216, 153, 32, 0.2);
  border-radius: 12px;
  color: #a66c08;
  background: linear-gradient(145deg, #fff8e7, #fffdf8);

  svg {
    width: 17px;
    height: 17px;
  }
}

.date-range-cell {
  display: flex;
  align-items: center;
  gap: 10px;

  > div {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  small {
    color: #a3afbf;
    font-size: 9px;
  }

  strong {
    color: #475569;
    font-size: 11px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }
}

.date-connector {
  position: relative;
  width: 24px;
  height: 1px;
  background: #cbd5e1;

  &::after {
    position: absolute;
    top: -2px;
    right: 0;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #d89920;
    content: "";
  }
}

.duration-chip {
  margin-left: 3px;
  padding: 4px 8px;
  border-radius: 8px;
  color: #64748b;
  background: #f1f5f9;
  font-size: 9px;
  font-weight: 750;
}

.status-pill,
.result-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-width: 76px;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 800;

  i {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }
}

.status-pill.is-active {
  color: #16764b;
  background: #eaf8f1;

  i {
    background: #20a66a;
    box-shadow: 0 0 0 4px rgba(32, 166, 106, 0.12);
  }
}

.status-pill.is-ended {
  color: #64748b;
  background: #f1f5f9;

  i {
    background: #94a3b8;
  }
}

.row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 5px;

  :deep(.el-button + .el-button) {
    margin-left: 0;
  }
}

.action-button {
  min-height: 32px !important;
  padding: 6px 9px !important;
  color: #64748b !important;
  background: transparent !important;

  &:hover {
    color: #172033 !important;
    background: #f1f5f9 !important;
  }
}

.view-action {
  color: #315b9b !important;
  background: #edf4ff !important;

  &:hover {
    color: #23487f !important;
    background: #dfebfb !important;
  }
}

.danger-action:hover {
  color: #c74325 !important;
  background: #fff0eb !important;
}

.progress-selector-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
  padding: 16px 18px;
  border: 1px solid #e5eaf0;
  border-radius: 16px;
  background: radial-gradient(circle at 0 0, rgba(216, 153, 32, 0.08), transparent 32%), #fbfcfd;
}

.selector-copy {
  display: flex;
  align-items: center;
  gap: 12px;

  > div {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  strong {
    color: #243149;
    font-size: 13px;
  }

  small {
    color: #94a3b8;
    font-size: 10px;
  }
}

.selector-icon {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  color: #a66c08;
  background: #fff4d8;

  svg {
    width: 16px;
  }
}

.progress-select {
  width: min(420px, 46%);
}

.status-overview {
  display: grid;
  grid-template-columns: repeat(3, minmax(125px, 0.72fr)) minmax(280px, 1.8fr);
  gap: 12px;
  margin-bottom: 28px;
}

.overview-metric,
.completion-meter {
  min-height: 112px;
  padding: 17px 18px;
  border: 1px solid #e6ebf1;
  border-radius: 16px;
  background: #fbfcfd;
}

.overview-metric {
  display: flex;
  flex-direction: column;

  > span {
    color: #64748b;
    font-size: 10px;
    font-weight: 750;
  }

  > strong {
    margin: 7px 0 3px;
    color: #243149;
    font-size: 29px;
    line-height: 1;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.04em;
  }

  > small {
    margin-top: auto;
    color: #a3afbf;
    font-size: 9px;
  }
}

.completed-metric {
  border-color: rgba(32, 166, 106, 0.18);
  background: linear-gradient(145deg, #f5fcf8, #fbfefd);

  > strong {
    color: #178054;
  }
}

.incomplete-metric {
  border-color: rgba(228, 87, 46, 0.16);
  background: linear-gradient(145deg, #fff8f5, #fffdfc);

  > strong {
    color: #ca4728;
  }
}

.completion-meter {
  display: flex;
  flex-direction: column;
  justify-content: center;
  color: white;
  border-color: transparent;
  background:
    radial-gradient(circle at 92% 15%, rgba(251, 191, 36, 0.2), transparent 28%),
    linear-gradient(135deg, #172033, #2c3b55);

  :deep(.el-progress-bar__outer) {
    background: rgba(255, 255, 255, 0.14);
  }
}

.meter-copy {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 13px;

  > div {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  span {
    color: #e2e8f0;
    font-size: 11px;
    font-weight: 750;
  }

  small {
    overflow: hidden;
    color: #94a3b8;
    font-size: 9px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  strong {
    flex: 0 0 auto;
    color: #fbbf24;
    font-size: 30px;
    line-height: 1;
    letter-spacing: -0.05em;

    em {
      margin-left: 2px;
      font-size: 13px;
      font-style: normal;
    }
  }
}

.student-table-toolbar {
  align-items: center;
}

.compact-heading .section-kicker {
  margin-bottom: 3px;
}

.status-filter {
  padding: 4px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #f8fafc;

  :deep(.el-radio-button__inner) {
    min-width: 72px;
    padding: 7px 12px;
    border: 0 !important;
    border-radius: 9px !important;
    color: #64748b;
    background: transparent;
    box-shadow: none !important;
    font-size: 11px;
    font-weight: 650;
  }

  :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
    color: #172033;
    background: white;
    box-shadow: 0 3px 9px rgba(15, 23, 42, 0.08) !important;
  }
}

.student-progress-table {
  :deep(td.el-table__cell) {
    height: 78px;
  }
}

.student-avatar {
  flex: 0 0 auto;
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border: 1px solid #dbe5f0;
  border-radius: 12px;
  color: #315b9b;
  background: linear-gradient(145deg, #edf4ff, #f8fbff);
  font-size: 13px;
  font-weight: 800;
}

.student-rate-cell {
  display: grid;
  grid-template-columns: minmax(90px, 1fr) 38px;
  align-items: center;
  gap: 10px;

  strong {
    color: #475569;
    font-size: 10px;
    font-variant-numeric: tabular-nums;
  }

  :deep(.el-progress-bar__outer) {
    background: #edf1f5;
  }
}

.document-column-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;

  span {
    max-width: 130px;
    overflow: hidden;
    color: #64748b;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  :deep(.el-tag) {
    height: 18px;
    padding: 0 7px !important;
    font-size: 8px;
    letter-spacing: 0;
  }
}

.document-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  font-weight: 700;

  .el-icon {
    font-size: 14px;
  }
}

.document-status.is-done {
  color: #178054;
}

.document-status.is-pending {
  color: #b77914;
}

.result-pill.is-complete {
  color: #16764b;
  background: #eaf8f1;
}

.result-pill.is-incomplete {
  color: #bd4327;
  background: #fff0eb;
}

.empty-hint {
  padding: 76px 0;
  color: #a3afbf;
  font-size: 13px;
  text-align: center;
}

:global(.progress-editor-dialog) {
  max-width: calc(100vw - 32px);
  border-radius: 24px !important;
}

:global(.progress-editor-dialog .el-dialog__header) {
  margin: 0;
  padding: 23px 28px 20px !important;
  border-bottom: 1px solid #e7ecf2;
  background:
    radial-gradient(circle at 92% 4%, rgba(216, 153, 32, 0.12), transparent 30%),
    linear-gradient(135deg, #fbfcfd, #f7f9fb);
}

:global(.progress-editor-dialog .el-dialog__headerbtn) {
  top: 18px;
  right: 20px;
  width: 34px;
  height: 34px;
  border-radius: 10px;
}

:global(.progress-editor-dialog .el-dialog__headerbtn:hover) {
  background: rgba(148, 163, 184, 0.12);
}

:global(.progress-editor-dialog .el-dialog__body) {
  max-height: min(68vh, 680px);
  overflow-x: hidden;
  overflow-y: auto;
  padding: 24px 28px 8px !important;
}

:global(.progress-editor-dialog .el-dialog__footer) {
  padding: 16px 28px 22px !important;
  border-top: 1px solid #e7ecf2;
  background: #fbfcfd;
}

.editor-dialog-heading {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-right: 42px;

  > div {
    min-width: 0;
  }

  small {
    display: block;
    margin-bottom: 3px;
    color: #b77914;
    font-size: 8px;
    font-weight: 850;
    letter-spacing: 0.18em;
  }

  h3,
  p {
    margin: 0;
  }

  h3 {
    color: #172033;
    font-size: 20px;
    font-weight: 760;
    letter-spacing: -0.02em;
  }

  p {
    margin-top: 4px;
    color: #94a3b8;
    font-size: 11px;
    line-height: 1.5;
  }
}

.editor-heading-icon {
  flex: 0 0 auto;
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(216, 153, 32, 0.22);
  border-radius: 14px;
  color: #a66c08;
  background: #fff6df;
  box-shadow: 0 8px 20px rgba(180, 120, 20, 0.08);

  svg {
    width: 18px;
    height: 18px;
  }
}

.editor-form {
  width: 100%;

  :deep(.el-form-item__label) {
    height: auto;
    margin-bottom: 8px;
    color: #475569;
    font-size: 11px;
    font-weight: 750;
    line-height: 1.4;
  }

  :deep(.el-form-item) {
    min-width: 0;
    margin-bottom: 20px;
  }

  :deep(.el-form-item__content) {
    min-width: 0;
  }
}

.editor-form-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.35fr);
  gap: 18px;
}

.date-picker-row {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 9px;

  :deep(.el-date-editor.el-input) {
    width: 100%;
    min-width: 0;
  }
}

.date-separator {
  color: #94a3b8;
  font-size: 10px;
  font-weight: 700;
}

.document-form-item {
  margin-bottom: 12px !important;
}

.doc-picker {
  width: 100%;
  min-width: 0;
  overflow: hidden;
  border: 1px solid #dfe6ee;
  border-radius: 17px;
  background: #f8fafc;
}

.doc-picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid #e5eaf0;
  background: rgba(255, 255, 255, 0.82);

  > div {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  strong {
    color: #334155;
    font-size: 12px;
    font-weight: 750;
  }

  small {
    color: #94a3b8;
    font-size: 9px;
    line-height: 1.5;
  }

  > span {
    flex: 0 0 auto;
    padding: 4px 9px;
    border-radius: 999px;
    color: #8a5d09;
    background: #fff3d3;
    font-size: 9px;
    font-weight: 800;
  }
}

.doc-selection-list {
  width: 100%;
  max-height: 350px;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 8px;
  box-sizing: border-box;
  scrollbar-gutter: stable;
}

.doc-row {
  width: 100%;
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
  padding: 11px 12px;
  border: 1px solid transparent;
  border-radius: 13px;
  box-sizing: border-box;
  transition:
    border-color 160ms ease,
    background 160ms ease,
    box-shadow 160ms ease;

  & + & {
    margin-top: 6px;
  }

  &:hover {
    border-color: #dfe6ee;
    background: white;
  }

  &.is-selected {
    border-color: rgba(216, 153, 32, 0.28);
    background: #fffdf7;
    box-shadow: 0 5px 16px rgba(128, 86, 14, 0.045);
  }
}

.doc-checkbox {
  min-width: 0;
  width: 100%;
  height: auto;
  margin-right: 0;

  :deep(.el-checkbox__input) {
    flex: 0 0 auto;
  }

  :deep(.el-checkbox__label) {
    min-width: 0;
    width: 100%;
    padding-left: 10px;
    white-space: normal;
  }
}

.doc-identity {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 11px;
}

.doc-kind-icon {
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 10px;

  .el-icon {
    font-size: 15px;
  }

  &.is-video {
    color: #178054;
    background: #eaf8f1;
  }

  &.is-document {
    color: #315b9b;
    background: #edf4ff;
  }
}

.doc-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;

  strong {
    overflow-wrap: anywhere;
    color: #334155;
    font-size: 11px;
    font-weight: 720;
    line-height: 1.45;
  }

  small {
    color: #94a3b8;
    font-size: 9px;
    line-height: 1.45;
  }
}

.threshold-input {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 7px;
  padding-left: 13px;
  border-left: 1px solid #e2e8f0;
  color: #64748b;

  > span {
    font-size: 9px;
    font-weight: 700;
    white-space: nowrap;
  }

  > b {
    color: #94a3b8;
    font-size: 10px;
  }

  :deep(.el-input-number) {
    width: 92px;
  }

  :deep(.el-input__wrapper) {
    min-height: 32px;
    padding-left: 9px !important;
  }
}

.completion-rule {
  flex: 0 0 auto;
  padding: 4px 8px;
  border-radius: 8px;
  color: #7b8798;
  background: #eef2f6;
  font-size: 9px;
  font-weight: 700;
  white-space: nowrap;
}

.docs-empty {
  padding: 54px 20px;
  color: #94a3b8;
  font-size: 11px;
  text-align: center;
}

.editor-dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;

  p {
    margin: 0;
    color: #94a3b8;
    font-size: 10px;

    strong {
      color: #b77914;
      font-size: 13px;
    }
  }

  > div {
    display: flex;
    gap: 8px;
  }
}

.save-plan-button {
  min-width: 104px;
  border-color: #172033 !important;
  background: #172033 !important;

  &:hover {
    border-color: #2b3b57 !important;
    background: #2b3b57 !important;
  }
}

@media (max-width: 1180px) {
  .status-overview {
    grid-template-columns: repeat(3, 1fr);
  }

  .completion-meter {
    grid-column: 1 / -1;
  }
}

@media (max-width: 760px) {
  :global(.progress-editor-dialog .el-dialog__header),
  :global(.progress-editor-dialog .el-dialog__body),
  :global(.progress-editor-dialog .el-dialog__footer) {
    padding-right: 18px !important;
    padding-left: 18px !important;
  }

  .table-toolbar,
  .student-table-toolbar,
  .progress-selector-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .progress-select {
    width: 100%;
  }

  .status-overview {
    grid-template-columns: 1fr;
  }

  .completion-meter {
    grid-column: auto;
  }

  .status-filter {
    align-self: flex-start;
  }

  .editor-form-grid {
    grid-template-columns: 1fr;
    gap: 0;
  }

  .doc-picker-header,
  .editor-dialog-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .doc-row {
    grid-template-columns: minmax(0, 1fr);
    gap: 9px;
  }

  .threshold-input {
    width: 100%;
    justify-content: flex-end;
    padding-top: 9px;
    padding-left: 0;
    border-top: 1px solid #e7ecf2;
    border-left: 0;
    box-sizing: border-box;
  }

  .completion-rule {
    margin-left: 54px;
  }

  .editor-dialog-footer > div {
    width: 100%;

    .el-button {
      flex: 1;
    }
  }
}
</style>
