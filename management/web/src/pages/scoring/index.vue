<script lang="ts" setup>
import type { ScoringConfig, ExternalScoreSource, ClassScoreResult } from "@@/apis/scores/type"
import type { FormInstance } from "element-plus"
import {
  getScoringConfigApi,
  saveScoringConfigApi,
  getExternalSourcesApi,
  createExternalSourceApi,
  updateExternalSourceApi,
  deleteExternalSourceApi,
  uploadExternalRecordsApi,
  getClassScoresApi
} from "@@/apis/scores"
import { getTableDataApi } from "@@/apis/teams"
import { ElMessage, ElMessageBox } from "element-plus"
import { Download, Plus, Refresh, Search, Upload } from "@element-plus/icons-vue"
import { onMounted, reactive, ref, watch } from "vue"

defineOptions({ name: "ScoringManagement" })

const loading = ref(false)
const activeTab = ref("config")

// ============ 班级选择 ============
interface ClassOption {
  id: string
  name: string
}
const classOptions = ref<ClassOption[]>([])
const selectedClassId = ref("")

function loadClasses() {
  getTableDataApi({
    currentPage: 1,
    size: 1000,
    sort_by: "id",
    sort_order: "desc"
  }).then(({ data }) => {
    classOptions.value = data.list.map((c: any) => ({ id: c.id, name: c.name }))
  })
}

onMounted(() => loadClasses())

// ============ Tab 1: 评分配置 ============
const DIMENSION_LABELS: Record<string, string> = {
  video: "视频",
  quiz: "测验",
  note: "笔记",
  flashcard: "概念速记",
  qa: "问答活跃度",
  external: "外部导入"
}

const DIMENSION_KEYS = ["video", "quiz", "note", "flashcard", "qa", "external"]

const dimensionEnabled = reactive<Record<string, boolean>>({})
const dimensionWeight = reactive<Record<string, number>>({})

function initDimensions() {
  DIMENSION_KEYS.forEach(key => {
    dimensionEnabled[key] = true
    dimensionWeight[key] = 20
  })
  dimensionEnabled["external"] = false
  dimensionWeight["external"] = 0
}
initDimensions()

const totalWeight = ref(100)

function recalcTotal() {
  totalWeight.value = DIMENSION_KEYS.reduce((sum, key) => {
    return sum + (dimensionEnabled[key] ? dimensionWeight[key] : 0)
  }, 0)
}

watch(dimensionWeight, () => recalcTotal(), { deep: true })
watch(dimensionEnabled, () => {
  DIMENSION_KEYS.forEach(key => {
    if (!dimensionEnabled[key]) dimensionWeight[key] = 0
  })
  recalcTotal()
}, { deep: true })

function loadConfig() {
  if (!selectedClassId.value) return
  loading.value = true
  getScoringConfigApi(selectedClassId.value).then(({ data: config }) => {
    DIMENSION_KEYS.forEach(key => {
      dimensionEnabled[key] = config[`${key}_enabled` as keyof ScoringConfig] as boolean
      dimensionWeight[key] = config[`${key}_weight` as keyof ScoringConfig] as number
    })
    recalcTotal()
  }).finally(() => { loading.value = false })
}

watch(selectedClassId, () => {
  if (activeTab.value === "config") loadConfig()
  if (activeTab.value === "result") loadScores()
})

function handleSaveConfig() {
  if (!selectedClassId.value) {
    ElMessage.warning("请先选择班级")
    return
  }
  if (totalWeight.value !== 100) {
    ElMessage.error("已启用维度权重之和必须等于 100")
    return
  }
  loading.value = true
  const data: any = {}
  DIMENSION_KEYS.forEach(key => {
    data[`${key}_enabled`] = dimensionEnabled[key]
    data[`${key}_weight`] = dimensionWeight[key]
  })
  saveScoringConfigApi(selectedClassId.value, data).then(() => {
    ElMessage.success("保存成功")
    loadConfig()
  }).finally(() => { loading.value = false })
}

// ============ 外部数据源管理 ============
const externalSources = ref<ExternalScoreSource[]>([])
const sourceDialogVisible = ref(false)
const sourceFormRef = ref<FormInstance | null>(null)
const sourceForm = reactive({ id: "" as string | undefined, source_name: "", max_score: 100 })
const isEditingSource = ref(false)

function loadExternalSources() {
  if (!selectedClassId.value) return
  getExternalSourcesApi(selectedClassId.value).then(({ data }) => {
    externalSources.value = data || []
  })
}

watch(() => dimensionEnabled["external"], (enabled) => {
  if (enabled) loadExternalSources()
})

function openAddSource() {
  isEditingSource.value = false
  sourceForm.id = undefined
  sourceForm.source_name = ""
  sourceForm.max_score = 100
  sourceDialogVisible.value = true
}

function openEditSource(source: ExternalScoreSource) {
  isEditingSource.value = true
  sourceForm.id = source.id
  sourceForm.source_name = source.source_name
  sourceForm.max_score = source.max_score
  sourceDialogVisible.value = true
}

function handleSaveSource() {
  if (!sourceForm.source_name.trim()) {
    ElMessage.warning("请输入数据源名称")
    return
  }
  if (sourceForm.max_score <= 0) {
    ElMessage.warning("满分值必须大于 0")
    return
  }
  if (isEditingSource.value && sourceForm.id) {
    updateExternalSourceApi(sourceForm.id, {
      source_name: sourceForm.source_name,
      max_score: sourceForm.max_score
    }).then(() => {
      ElMessage.success("修改成功")
      sourceDialogVisible.value = false
      loadExternalSources()
    })
  } else {
    createExternalSourceApi({
      class_id: selectedClassId.value,
      source_name: sourceForm.source_name,
      max_score: sourceForm.max_score
    }).then(() => {
      ElMessage.success("创建成功")
      sourceDialogVisible.value = false
      loadExternalSources()
    })
  }
}

function handleDeleteSource(source: ExternalScoreSource) {
  ElMessageBox.confirm(`确认删除数据源「${source.source_name}」？相关评分记录也将被删除。`, "提示", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning"
  }).then(() => {
    deleteExternalSourceApi(source.id).then(() => {
      ElMessage.success("删除成功")
      loadExternalSources()
    })
  })
}

// ============ 上传成绩 ============
const uploadSourceId = ref("")
const uploadRef = ref<any>(null)

function handleUploadChange(file: any) {
  if (!uploadSourceId.value) {
    ElMessage.warning("请先选择数据源")
    return
  }
  const rawFile = file.raw || file
  uploadExternalRecordsApi(uploadSourceId.value, rawFile).then(() => {
    ElMessage.success("导入成功")
  })
}

// ============ Tab 2: 评分结果 ============
const scoreResult = ref<ClassScoreResult | null>(null)
const searchName = ref("")

function loadScores() {
  if (!selectedClassId.value) return
  loading.value = true
  getClassScoresApi(selectedClassId.value).then(({ data }) => {
    scoreResult.value = data
  }).finally(() => { loading.value = false })
}

const filteredStudents = ref<any[]>([])
watch([scoreResult, searchName], () => {
  if (!scoreResult.value) {
    filteredStudents.value = []
    return
  }
  const kw = searchName.value.toLowerCase()
  filteredStudents.value = scoreResult.value.students.filter(s =>
    !kw || s.student_name.toLowerCase().includes(kw)
  )
}, { deep: true })

/** 获取启用的维度列表（用于动态表格列） */
function getEnabledDimensions(): string[] {
  if (!scoreResult.value) return []
  const config = scoreResult.value.config
  return DIMENSION_KEYS.filter(key => config[`${key}_enabled` as keyof ScoringConfig])
}

// ============ 导出 ============
function handleExport() {
  if (!scoreResult.value) return
  const dims = getEnabledDimensions()
  const headers = ["排名", "姓名", ...dims.map(d => `${DIMENSION_LABELS[d]}(${scoreResult.value!.config[`${d}_weight` as keyof ScoringConfig]}%)`), "总分"]
  const rows = scoreResult.value.students.map((s, i) => {
    const cells = [String(i + 1), s.student_name]
    dims.forEach(d => cells.push(String(s.dimensions[d] ?? 0)))
    cells.push(String(s.total_score))
    return cells.join("\t")
  })
  const csv = "﻿" + headers.join("\t") + "\n" + rows.join("\n")
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = "评分结果.csv"
  a.click()
  URL.revokeObjectURL(url)
}

// ============ 模板下载 ============
function handleDownloadTemplate() {
  const csv = "﻿学号\t得分\n20240001\t85\n"
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = "外部成绩导入模板.csv"
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="app-container">
    <!-- 班级选择器（全局） -->
    <el-card shadow="never" class="class-selector-card">
      <div class="class-selector-row">
        <span class="selector-label">班级：</span>
        <el-select v-model="selectedClassId" placeholder="请选择班级" style="width: 280px" clearable>
          <el-option v-for="c in classOptions" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </div>
    </el-card>

    <!-- Tabs -->
    <el-card v-loading="loading" shadow="never" class="main-card">
      <el-tabs v-model="activeTab" @tab-change="(tab: string) => { if (tab === 'config') loadConfig(); if (tab === 'result') loadScores(); }">
        <!-- ============ Tab 1: 评分配置 ============ -->
        <el-tab-pane label="评分配置" name="config">
          <div v-if="!selectedClassId" class="empty-hint">请先选择班级</div>
          <template v-else>
            <div class="dimension-list">
              <div v-for="key in DIMENSION_KEYS" :key="key" class="dimension-row">
                <div class="dimension-left">
                  <el-switch v-model="dimensionEnabled[key]" size="large" />
                  <span class="dimension-label">{{ DIMENSION_LABELS[key] }}</span>
                </div>
                <div class="dimension-right">
                  <el-slider
                    v-model="dimensionWeight[key]"
                    :min="0"
                    :max="100"
                    :step="1"
                    :disabled="!dimensionEnabled[key]"
                    style="width: 200px"
                    show-input
                  />
                  <span class="weight-unit">%</span>
                </div>
              </div>
            </div>

            <div class="total-row">
              <span>已启用合计：</span>
              <span :class="['total-value', totalWeight !== 100 ? 'error' : 'ok']">
                {{ totalWeight }}%
              </span>
              <span v-if="totalWeight !== 100" class="error-hint">（必须等于 100%）</span>
            </div>

            <el-button
              type="primary"
              :disabled="totalWeight !== 100"
              :loading="loading"
              style="margin-top: 16px"
              @click="handleSaveConfig"
            >
              保存配置
            </el-button>

            <!-- 外部数据源（仅当启用时显示） -->
            <template v-if="dimensionEnabled['external']">
              <el-divider />
              <div class="section-title">外部数据源</div>

              <div style="margin-bottom: 12px; display: flex; gap: 12px; align-items: center">
                <el-button type="primary" :icon="Plus" size="small" @click="openAddSource">添加数据源</el-button>

                <span style="font-size: 13px; color: #909399">导入成绩：</span>
                <el-select v-model="uploadSourceId" placeholder="选择数据源" size="small" style="width: 180px" clearable>
                  <el-option v-for="s in externalSources" :key="s.id" :label="s.source_name" :value="s.id" />
                </el-select>
                <el-upload
                  ref="uploadRef"
                  :show-file-list="false"
                  :auto-upload="false"
                  :on-change="handleUploadChange"
                  accept=".xlsx,.xls"
                >
                  <el-button type="success" :icon="Upload" size="small" plain>上传 Excel</el-button>
                </el-upload>
                <el-button type="warning" :icon="Download" size="small" plain text @click="handleDownloadTemplate">下载模板</el-button>
              </div>

              <el-table :data="externalSources" border stripe size="small">
                <el-table-column prop="source_name" label="数据源名称" min-width="160" />
                <el-table-column prop="max_score" label="满分" width="80" align="center" />
                <el-table-column label="操作" width="140" align="center">
                  <template #default="scope">
                    <el-button type="primary" text size="small" @click="openEditSource(scope.row)">编辑</el-button>
                    <el-button type="danger" text size="small" @click="handleDeleteSource(scope.row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </template>
          </template>
        </el-tab-pane>

        <!-- ============ Tab 2: 评分结果 ============ -->
        <el-tab-pane label="评分结果" name="result">
          <div v-if="!selectedClassId" class="empty-hint">请先选择班级</div>
          <template v-else>
            <div class="toolbar-wrapper">
              <div class="toolbar-left">
                <el-input
                  v-model="searchName"
                  placeholder="搜索学生姓名"
                  :prefix-icon="Search"
                  clearable
                  style="width: 220px"
                />
              </div>
              <div class="toolbar-right">
                <el-button :icon="Refresh" @click="loadScores">刷新</el-button>
                <el-button type="primary" :icon="Download" @click="handleExport" :disabled="!scoreResult || scoreResult.students.length === 0">导出 CSV</el-button>
              </div>
            </div>

            <el-table :data="filteredStudents" border stripe highlight-current-row size="small">
              <el-table-column type="index" label="排名" width="60" align="center" />
              <el-table-column prop="student_name" label="姓名" min-width="100" fixed />
              <el-table-column
                v-for="dim in getEnabledDimensions()"
                :key="dim"
                :prop="`dimensions.${dim}`"
                :label="`${DIMENSION_LABELS[dim]}(${scoreResult?.config?.[`${dim}_weight` as keyof ScoringConfig]}%)`"
                min-width="110"
                align="center"
                sortable
              >
                <template #default="scope">
                  {{ scope.row.dimensions[dim] ?? 0 }}
                </template>
              </el-table-column>
              <el-table-column prop="total_score" label="总分" min-width="100" align="center" sortable>
                <template #default="scope">
                  <strong>{{ scope.row.total_score }}</strong>
                </template>
              </el-table-column>
            </el-table>

            <div v-if="scoreResult && scoreResult.students.length === 0" class="empty-hint">
              暂无评分数据
            </div>
          </template>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 添加/编辑外部数据源弹窗 -->
    <el-dialog
      v-model="sourceDialogVisible"
      :title="isEditingSource ? '编辑数据源' : '添加数据源'"
      width="400px"
    >
      <el-form ref="sourceFormRef" :model="sourceForm" label-width="100px">
        <el-form-item label="数据源名称" required>
          <el-input v-model="sourceForm.source_name" placeholder="如：学习通章节测验" />
        </el-form-item>
        <el-form-item label="满分值" required>
          <el-input-number v-model="sourceForm.max_score" :min="1" :max="10000" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sourceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveSource">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.class-selector-card {
  margin-bottom: 16px;
  .class-selector-row {
    display: flex;
    align-items: center;
    gap: 12px;
    .selector-label { font-weight: 500; font-size: 14px; }
  }
}

.main-card {
  :deep(.el-card__body) { padding: 20px 24px; }
}

.dimension-list {
  .dimension-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 0;
    border-bottom: 1px solid #f0f0f0;
    .dimension-left {
      display: flex;
      align-items: center;
      gap: 12px;
      .dimension-label { font-size: 14px; font-weight: 500; min-width: 80px; }
    }
    .dimension-right {
      display: flex;
      align-items: center;
      gap: 8px;
      .weight-unit { font-size: 14px; color: #909399; }
    }
  }
}

.total-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  font-size: 15px;
  font-weight: 500;
  .total-value.ok { color: #67c23a; font-size: 18px; }
  .total-value.error { color: #f56c6c; font-size: 18px; }
  .error-hint { color: #f56c6c; font-size: 12px; }
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin: 16px 0 12px;
}

.toolbar-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  .toolbar-left, .toolbar-right { display: flex; align-items: center; gap: 10px; }
}

.empty-hint {
  text-align: center;
  padding: 60px 0;
  color: #c0c4cc;
  font-size: 15px;
}
</style>
