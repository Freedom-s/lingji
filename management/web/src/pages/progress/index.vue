<script lang="ts" setup>
import type { ClassDocument, CreateProgressData, WeeklyProgressItem, ProgressStatusResult } from "@@/apis/progress/type"
import type { FormInstance } from "element-plus"
import {
  getWeeklyProgressListApi, createWeeklyProgressApi, updateWeeklyProgressApi,
  deleteWeeklyProgressApi, getClassDocumentsApi, getProgressStatusApi
} from "@@/apis/progress"
import { getTableDataApi } from "@@/apis/teams"
import { ElMessage, ElMessageBox } from "element-plus"
import { Calendar, CircleCheck, Clock, Delete, Edit, Plus, RefreshRight, Search, View } from "@element-plus/icons-vue"
import { onMounted, reactive, ref, watch } from "vue"

defineOptions({ name: "ProgressManagement" })

const loading = ref(false)
const activeTab = ref("list")

// ============ 班级选择 ============
interface ClassOption { id: string; name: string }
const classOptions = ref<ClassOption[]>([])
const selectedClassId = ref("")

function loadClasses() {
  getTableDataApi({ currentPage: 1, size: 1000 }).then(({ data }) => {
    classOptions.value = data.list.map((c: any) => ({ id: c.id, name: c.name }))
  })
}
onMounted(() => loadClasses())

// ============ Tab 1: 进度列表 ============
const progressList = ref<WeeklyProgressItem[]>([])

function loadProgressList() {
  if (!selectedClassId.value) return
  loading.value = true
  getWeeklyProgressListApi(selectedClassId.value).then(({ data }) => {
    progressList.value = data || []
  }).finally(() => loading.value = false)
}
watch(selectedClassId, () => { if (activeTab.value === "list") loadProgressList() })

// 新建/编辑弹窗
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref("")
const formRef = ref<FormInstance | null>(null)
const formData = reactive<CreateProgressData>({ name: "", week_start: "", week_end: "", doc_ids: [], quiz_thresholds: {} })

// 文档列表
const availableDocs = ref<ClassDocument[]>([])
const docSelection = reactive<Record<string, boolean>>({})
const docThresholds = reactive<Record<string, number>>({})

function openCreate() {
  isEditing.value = false
  editingId.value = ""
  formData.name = ""
  formData.week_start = ""
  formData.week_end = ""
  formData.doc_ids = []
  formData.quiz_thresholds = {}
  // 重置选择
  availableDocs.value.forEach(d => { docSelection[d.id] = false; docThresholds[d.id] = 0 })
  dialogVisible.value = true
  if (selectedClassId.value) loadDocs()
}

function openEdit(row: WeeklyProgressItem) {
  isEditing.value = true
  editingId.value = row.id
  formData.name = row.name
  formData.week_start = row.week_start
  formData.week_end = row.week_end
  dialogVisible.value = true
  loadDocs()
  // 等文档数据加载后再设置选中状态——这里简化处理，从后端获取已有数据
  getProgressStatusApi(row.id).then(({ data: statusData }) => {
    const pDocs = statusData.progress.docs
    availableDocs.value.forEach(d => { docSelection[d.id] = false; docThresholds[d.id] = 0 })
    pDocs.forEach((pd: any) => {
      docSelection[pd.doc_id] = true
      docThresholds[pd.doc_id] = pd.quiz_threshold
    })
  })
}

function loadDocs() {
  if (!selectedClassId.value) return
  getClassDocumentsApi(selectedClassId.value).then(({ data }) => {
    availableDocs.value = data || []
    availableDocs.value.forEach(d => {
      if (!(d.id in docSelection)) { docSelection[d.id] = false; docThresholds[d.id] = 0 }
    })
  })
}

function buildFormFromSelection() {
  formData.doc_ids = []
  formData.quiz_thresholds = {}
  availableDocs.value.forEach(d => {
    if (docSelection[d.id]) {
      formData.doc_ids.push(d.id)
      formData.quiz_thresholds[d.id] = d.has_quiz ? docThresholds[d.id] : 0
    }
  })
}

function handleSave() {
  if (!formData.name.trim()) { ElMessage.warning("请输入名称"); return }
  if (!formData.week_start || !formData.week_end) { ElMessage.warning("请选择时间范围"); return }

  buildFormFromSelection()
  if (formData.doc_ids.length === 0) { ElMessage.warning("至少选择1个文档"); return }

  loading.value = true
  const api = isEditing.value
    ? updateWeeklyProgressApi(editingId.value, { ...formData })
    : createWeeklyProgressApi(selectedClassId.value, { ...formData })

  api.then(() => {
    ElMessage.success(isEditing.value ? "修改成功" : "创建成功")
    dialogVisible.value = false
    loadProgressList()
  }).finally(() => loading.value = false)
}

function handleDelete(row: WeeklyProgressItem) {
  ElMessageBox.confirm(`确认删除「${row.name}」？`, "提示", {
    confirmButtonText: "确定", cancelButtonText: "取消", type: "warning"
  }).then(() => {
    deleteWeeklyProgressApi(row.id).then(() => { ElMessage.success("删除成功"); loadProgressList() })
  })
}

// ============ Tab 2: 完成情况 ============
const progressOptions = ref<WeeklyProgressItem[]>([])
const selectedProgressId = ref("")
const statusResult = ref<ProgressStatusResult | null>(null)
const statusFilter = ref("all")  // all | completed | incomplete

function loadProgressOptions() {
  if (!selectedClassId.value) return
  getWeeklyProgressListApi(selectedClassId.value).then(({ data }) => {
    progressOptions.value = data || []
  })
}
watch(selectedClassId, () => { if (activeTab.value === "status") loadProgressOptions() })

function loadStatus() {
  if (!selectedProgressId.value) { statusResult.value = null; return }
  loading.value = true
  getProgressStatusApi(selectedProgressId.value).then(({ data }) => {
    statusResult.value = data
  }).finally(() => loading.value = false)
}

const filteredStudents = ref<any[]>([])
watch([statusResult, statusFilter], () => {
  if (!statusResult.value) { filteredStudents.value = []; return }
  const all = statusResult.value.students
  if (statusFilter.value === "completed") filteredStudents.value = all.filter(s => s.is_all_completed)
  else if (statusFilter.value === "incomplete") filteredStudents.value = all.filter(s => !s.is_all_completed)
  else filteredStudents.value = all
}, { deep: true })

function getDocTypeTag(docType: string) {
  return docType === "video" ? "success" : "primary"
}

function getDocStatus(student: any, docId: string) {
  return student.doc_statuses?.find((d: any) => d.doc_id === docId)
}
</script>

<template>
  <div class="app-container">
    <!-- 班级选择器 -->
    <el-card shadow="never" class="class-selector-card">
      <div class="class-selector-row">
        <span class="selector-label">班级：</span>
        <el-select v-model="selectedClassId" placeholder="请选择班级" style="width: 280px" clearable>
          <el-option v-for="c in classOptions" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </div>
    </el-card>

    <el-card v-loading="loading" shadow="never" class="main-card">
      <el-tabs v-model="activeTab" @tab-change="(tab: string) => { if (tab === 'list') loadProgressList(); if (tab === 'status') loadProgressOptions() }">
        <!-- Tab 1: 进度列表 -->
        <el-tab-pane label="进度列表" name="list">
          <div v-if="!selectedClassId" class="empty-hint">请先选择班级</div>
          <template v-else>
            <div style="margin-bottom: 16px">
              <el-button type="primary" :icon="Plus" @click="openCreate">新建周进度</el-button>
            </div>
            <el-table :data="progressList" border stripe size="small">
              <el-table-column prop="name" label="名称" min-width="160" />
              <el-table-column label="时间范围" min-width="180">
                <template #default="scope">
                  {{ scope.row.week_start }} ~ {{ scope.row.week_end }}
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="80" align="center">
                <template #default="scope">
                  <el-tag :type="scope.row.status === '1' ? 'success' : 'info'" size="small">
                    {{ scope.row.status === '1' ? '进行中' : '已结束' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="200" align="center">
                <template #default="scope">
                  <el-button type="primary" text size="small" :icon="View" @click="selectedProgressId = scope.row.id; activeTab = 'status'; loadStatus()">查看</el-button>
                  <el-button type="success" text size="small" :icon="Edit" @click="openEdit(scope.row)">编辑</el-button>
                  <el-button type="danger" text size="small" :icon="Delete" @click="handleDelete(scope.row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </template>
        </el-tab-pane>

        <!-- Tab 2: 完成情况 -->
        <el-tab-pane label="完成情况" name="status">
          <div v-if="!selectedClassId" class="empty-hint">请先选择班级</div>
          <template v-else>
            <div style="margin-bottom: 16px; display: flex; gap: 12px; align-items: center">
              <span style="font-weight: 500">选择进度：</span>
              <el-select v-model="selectedProgressId" placeholder="请选择周进度" style="width: 300px" @change="loadStatus">
                <el-option v-for="p in progressOptions" :key="p.id" :label="`${p.name} (${p.week_start} ~ ${p.week_end})`" :value="p.id" />
              </el-select>
            </div>

            <template v-if="statusResult">
              <!-- 概览卡片 -->
              <el-row :gutter="16" style="margin-bottom: 20px">
                <el-col :span="6">
                  <el-statistic title="学生总数" :value="statusResult.summary.total_students" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="已完成" :value="statusResult.summary.completed_count">
                    <template #suffix><span style="color: #67c23a">/ {{ statusResult.summary.total_students }}</span></template>
                  </el-statistic>
                </el-col>
                <el-col :span="6">
                  <el-statistic title="未完成" :value="statusResult.summary.incomplete_count">
                    <template #suffix>
                      <span :style="{ color: statusResult.summary.incomplete_count > 0 ? '#f56c6c' : '#67c23a' }">
                        ⚠ {{ statusResult.summary.incomplete_count }} 人
                      </span>
                    </template>
                  </el-statistic>
                </el-col>
                <el-col :span="6">
                  <el-statistic title="完成率" :value="statusResult.summary.completion_rate">
                    <template #suffix><span>%</span></template>
                  </el-statistic>
                </el-col>
              </el-row>

              <el-progress
                :percentage="statusResult.summary.completion_rate"
                :color="statusResult.summary.completion_rate >= 80 ? '#67c23a' : statusResult.summary.completion_rate >= 50 ? '#e6a23c' : '#f56c6c'"
                style="margin-bottom: 20px"
              />

              <!-- 筛选 -->
              <el-radio-group v-model="statusFilter" size="small" style="margin-bottom: 12px">
                <el-radio-button value="all">全部</el-radio-button>
                <el-radio-button value="completed">已完成</el-radio-button>
                <el-radio-button value="incomplete">未完成</el-radio-button>
              </el-radio-group>

              <!-- 学生明细表 -->
              <el-table :data="filteredStudents" border stripe size="small">
                <el-table-column prop="student_name" label="姓名" min-width="100" fixed />
                <el-table-column
                  v-for="doc in statusResult.progress.docs"
                  :key="doc.doc_id"
                  :label="doc.doc_name"
                  min-width="120"
                  align="center"
                >
                  <template #default="scope">
                    <span v-if="getDocStatus(scope.row, doc.doc_id)?.is_completed" style="color: #67c23a; font-size: 16px">✅</span>
                    <span v-else style="color: #f56c6c; font-size: 16px">❌</span>
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="100" align="center" fixed="right">
                  <template #default="scope">
                    <el-tag :type="scope.row.is_all_completed ? 'success' : 'danger'" size="small">
                      {{ scope.row.is_all_completed ? '已完成' : '未完成' }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </template>
            <div v-else class="empty-hint">请选择要查看的周进度</div>
          </template>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新建/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEditing ? '编辑周进度' : '新建周进度'" width="650px" @closed="formRef?.resetFields()">
      <el-form ref="formRef" :model="formData" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="formData.name" placeholder="如：第4周学习任务" />
        </el-form-item>
        <el-form-item label="时间范围" required>
          <el-date-picker v-model="formData.week_start" type="date" placeholder="开始日期" value-format="YYYY-MM-DD" style="width: 180px" />
          <span style="margin: 0 8px">至</span>
          <el-date-picker v-model="formData.week_end" type="date" placeholder="结束日期" value-format="YYYY-MM-DD" style="width: 180px" />
        </el-form-item>
        <el-form-item label="选择文档" required>
          <div class="doc-selection-list">
            <div v-for="doc in availableDocs" :key="doc.id" class="doc-row">
              <el-checkbox v-model="docSelection[doc.id]">
                {{ doc.name }}
                <el-tag :type="doc.type === 'video' ? 'success' : 'primary'" size="small" style="margin-left: 6px">
                  {{ doc.type === 'video' ? '视频' : doc.type }}
                </el-tag>
              </el-checkbox>
              <span v-if="doc.has_quiz" class="threshold-input">
                测验阈值:
                <el-input-number v-model="docThresholds[doc.id]" :min="0" :max="100" :step="5" size="small" style="width: 100px" /> %
              </span>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.class-selector-card {
  margin-bottom: 16px;
  .class-selector-row {
    display: flex; align-items: center; gap: 12px;
    .selector-label { font-weight: 500; font-size: 14px; }
  }
}
.main-card { :deep(.el-card__body) { padding: 20px 24px; } }
.empty-hint { text-align: center; padding: 60px 0; color: #c0c4cc; font-size: 15px; }
.doc-selection-list {
  max-height: 350px; overflow-y: auto; border: 1px solid #eee; border-radius: 4px; padding: 8px;
  .doc-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 8px 4px; border-bottom: 1px solid #f5f5f5;
    .threshold-input { font-size: 12px; color: #909399; display: flex; align-items: center; gap: 4px; }
  }
}
</style>
