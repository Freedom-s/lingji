<script lang="ts" setup>
import type { CreateOrUpdateAssistantRequestData, AssistantData } from "@/common/apis/assistants/type"
import type { FormInstance, FormRules } from "element-plus"
import { createAssistantDataApi, deleteAssistantDataApi, getAssistantDataApi, updateAssistantDataApi } from "@/common/apis/assistants"
import { getKnowledgeBaseListApi } from "@/common/apis/kbs/knowledgebase"
import { usePagination } from "@@/composables/usePagination"
import { CirclePlus, Delete, Edit, Refresh, Search } from "@element-plus/icons-vue"
import { cloneDeep } from "lodash-es"
import { onActivated, onMounted, ref } from "vue"

defineOptions({
  assistant_name: "AssistantManagement"
})

const loading = ref<boolean>(false)
const { paginationData, handleCurrentChange, handleSizeChange } = usePagination()

const DEFAULT_FORM_DATA: CreateOrUpdateAssistantRequestData = {
  id: undefined,
  assistant_name: "",
  description: "",
  knowledge_bases: []
}
const dialogVisible = ref<boolean>(false)
const formRef = ref<FormInstance | null>(null)
const formData = ref<CreateOrUpdateAssistantRequestData>(cloneDeep(DEFAULT_FORM_DATA))
const formRules: FormRules<CreateOrUpdateAssistantRequestData> = {
  assistant_name: [{ required: true, trigger: "blur", message: "请输入助教名称" }]
}

// 知识库列表
const knowledgeBases = ref<any[]>([])
const knowledgeBasesLoading = ref(false)

// 获取知识库列表
function getKnowledgeBases() {
  knowledgeBasesLoading.value = true
  return getKnowledgeBaseListApi({
    currentPage: 1,
    size: 1000,
    sort_by: "create_date",
    sort_order: "desc"
  }).then(({ data }) => {
    knowledgeBases.value = data.list || []
  }).catch(() => {
    knowledgeBases.value = []
  }).finally(() => {
    knowledgeBasesLoading.value = false
  })
}

function handleCreateOrUpdate() {
  formRef.value?.validate((valid) => {
    if (!valid) {
      ElMessage.error("表单校验不通过")
      return
    }
    loading.value = true
    const api = formData.value.id === undefined ? createAssistantDataApi : updateAssistantDataApi
    api(formData.value).then(() => {
      ElMessage.success(formData.value.id === undefined ? "添加成功" : "修改成功")
      dialogVisible.value = false
      getTableData()
    }).finally(() => {
      loading.value = false
    })
  })
}

function resetForm() {
  formRef.value?.clearValidate()
  formData.value = cloneDeep(DEFAULT_FORM_DATA)
}

function handleDelete(row: AssistantData) {
  ElMessageBox.confirm(`正在删除助教：${row.name}，确认删除？`, "提示", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning"
  }).then(() => {
    deleteAssistantDataApi(row.id).then(() => {
      ElMessage.success("删除成功")
      getTableData()
    })
  })
}

async function handleUpdate(row: AssistantData) {
  // 先获取最新的知识库列表，等待加载完成
  await getKnowledgeBases()
  dialogVisible.value = true
  // 将后端返回的数据转换为表单需要的格式
  formData.value = {
    id: row.id,
    assistant_name: row.name,
    description: row.description,
    knowledge_bases: row.knowledgeBaseIds || []
  }
}

const tableData = ref<AssistantData[]>([])
const searchFormRef = ref<FormInstance | null>(null)
const searchData = reactive({
  assistant_name: ""
})

const sortData = reactive({
  sortBy: "create_date",
  sortOrder: "desc"
})

const multipleSelection = ref<AssistantData[]>([])

function getTableData() {
  loading.value = true
  getAssistantDataApi({
    currentPage: paginationData.currentPage,
    size: paginationData.pageSize,
    assistant_name: searchData.assistant_name,
    sort_by: sortData.sortBy,
    sort_order: sortData.sortOrder
  }).then(({ data }) => {
    paginationData.total = data.total
    tableData.value = data.list
    multipleSelection.value = []
  }).catch(() => {
    tableData.value = []
  }).finally(() => {
    loading.value = false
  })
}

function handleSearch() {
  paginationData.currentPage === 1 ? getTableData() : (paginationData.currentPage = 1)
}

function resetSearch() {
  searchFormRef.value?.resetFields()
  handleSearch()
}

function handleSelectionChange(selection: AssistantData[]) {
  multipleSelection.value = selection
}

function handleBatchDelete() {
  if (multipleSelection.value.length === 0) {
    ElMessage.warning("请至少选择一条记录")
    return
  }
  ElMessageBox.confirm(`确认删除选中的 ${multipleSelection.value.length} 条记录吗？`, "提示", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning"
  }).then(async () => {
    loading.value = true
    try {
      await Promise.all(
        multipleSelection.value.map(row => deleteAssistantDataApi(row.id))
      )
      ElMessage.success("批量删除成功")
      getTableData()
    } finally {
      loading.value = false
    }
  })
}

function handleSortChange({ prop }: { prop: string, order: string | null }) {
  if (sortData.sortBy === prop) {
    sortData.sortOrder = sortData.sortOrder === "asc" ? "desc" : "asc"
  } else {
    sortData.sortBy = prop
    sortData.sortOrder = "asc"
  }
  getTableData()
}

// 监听分页参数的变化
watch([() => paginationData.currentPage, () => paginationData.pageSize], getTableData)

// 确保页面挂载和激活时获取数据
onMounted(() => {
  getTableData()
  getKnowledgeBases()
})

// 当从其他页面切换回来时刷新数据
onActivated(() => {
  getTableData()
})

// 根据索引返回标签类型，实现不同颜色的标签
function getTagType(index: number) {
  const types = ["primary", "success", "info"]
  return types[index % types.length]
}

// 打开创建对话框时刷新知识库列表
function handleOpenCreateDialog() {
  getKnowledgeBases()
  dialogVisible.value = true
}
</script>

<template>
  <div class="app-container">
    <el-card v-loading="loading" shadow="never" class="search-wrapper">
      <el-form ref="searchFormRef" :model="searchData" label-width="70px" class="search-form">
        <el-row :gutter="16">
          <el-col :xs="24" :sm="12" :md="8" :lg="6">
            <el-form-item prop="assistant_name" label="助教名称">
              <el-input v-model="searchData.assistant_name" placeholder="请输入助教名称" clearable />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="24" :md="16" :lg="18">
            <el-form-item class="search-actions" label-width="0">
              <el-button type="primary" :icon="Search" @click="handleSearch">
                查询
              </el-button>
              <el-button :icon="Refresh" @click="resetSearch">
                重置
              </el-button>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card v-loading="loading" shadow="never" class="table-card">
      <div class="toolbar-wrapper">
        <div class="toolbar-left">
          <el-button type="primary" :icon="CirclePlus" @click="handleOpenCreateDialog">
            添加助教
          </el-button>
          <el-button type="danger" :icon="Delete" :disabled="multipleSelection.length === 0" @click="handleBatchDelete">
            批量删除
          </el-button>
          <span v-if="multipleSelection.length > 0" class="selection-info">
            已选择 {{ multipleSelection.length }} 项
          </span>
        </div>
      </div>

      <div class="table-wrapper">
        <el-table
          :data="tableData"
          @selection-change="handleSelectionChange"
          @sort-change="handleSortChange"
        >
          <el-table-column type="selection" width="55" align="center" fixed />
          <el-table-column prop="name" label="助教名称" align="center" sortable="custom" min-width="120" />
          <el-table-column prop="description" label="助教描述" align="center" min-width="180" show-overflow-tooltip />
          <el-table-column prop="knowledgeBaseNames" label="关联知识库" align="center" min-width="220">
            <template #default="scope">
              <div v-if="scope.row.knowledgeBaseNames && scope.row.knowledgeBaseNames.length > 0" class="knowledge-bases-tags">
                <el-tag
                  v-for="(kbName, index) in scope.row.knowledgeBaseNames"
                  :key="index"
                  :type="getTagType(index)"
                  size="small"
                  class="kb-tag"
                  round
                >
                  {{ kbName }}
                </el-tag>
              </div>
              <span v-else class="no-data">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="createTime" label="创建时间" align="center" sortable="custom" min-width="160" />
          <el-table-column prop="updateTime" label="更新时间" align="center" sortable="custom" min-width="160" />
          <el-table-column fixed="right" label="操作" width="200" align="center">
            <template #default="scope">
              <div class="operation-buttons">
                <el-button type="success" text bg size="small" :icon="Edit" @click="handleUpdate(scope.row)">
                  修改
                </el-button>
                <el-divider direction="vertical" />
                <el-button type="danger" text bg size="small" :icon="Delete" @click="handleDelete(scope.row)">
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="pager-wrapper">
        <el-pagination
          background
          :layout="paginationData.layout"
          :page-sizes="paginationData.pageSizes"
          :total="paginationData.total"
          :page-size="paginationData.pageSize"
          :current-page="paginationData.currentPage"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="formData.id === undefined ? '新增助教' : '修改助教'"
      width="500px"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px" label-position="left">
        <el-form-item prop="assistant_name" label="助教名称">
          <el-input v-model="formData.assistant_name" placeholder="请输入助教名称" />
        </el-form-item>
        <el-form-item prop="description" label="助教描述">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入助教描述"
          />
        </el-form-item>
        <el-form-item prop="knowledge_bases" label="教学知识库">
          <el-select
            v-model="formData.knowledge_bases"
            multiple
            placeholder="请选择教学知识库"
            style="width: 100%"
            :loading="knowledgeBasesLoading"
          >
            <el-option
              v-for="kb in knowledgeBases"
              :key="kb.id"
              :label="kb.name"
              :value="kb.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">
          取消
        </el-button>
        <el-button type="primary" :loading="loading" @click="handleCreateOrUpdate">
          确认
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.search-wrapper {
  .search-form {
    :deep(.el-form-item__content) {
      width: 100%;
    }

    :deep(.el-input) {
      width: 100%;
      max-width: 240px;
    }

    :deep(.el-input__wrapper) {
      height: 48px;
      line-height: 48px;
    }

    :deep(.el-form-item__label) {
      line-height: 48px;
      height: 48px;
    }

    @media screen and (min-width: 768px) {
      :deep(.el-form-item) {
        margin-bottom: 0;
      }
    }

    .search-actions {
      :deep(.el-form-item__content) {
        display: flex;
        align-items: center;
        gap: 12px;
        height: 100%;
      }
    }
  }
}

.knowledge-bases-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
  align-items: center;

  .kb-tag {
    margin: 0;
    padding: 0 10px;
  }
}
</style>
