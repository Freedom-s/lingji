<script lang="ts" setup>
import type { CreateOrUpdateTeacherRequestData, TeacherData } from "@@/apis/teachers/type"
import type { FormInstance, FormRules } from "element-plus"
import { createTeacherDataApi, deleteTeacherDataApi, getTeacherDataApi, resetTeacherPasswordApi, updateTeacherDataApi } from "@@/apis/teachers"
import { usePagination } from "@@/composables/usePagination"
import { CirclePlus, Delete, Edit, Key, Refresh, RefreshRight, Search } from "@element-plus/icons-vue"
import { cloneDeep } from "lodash-es"
import { onActivated, onMounted } from "vue"

defineOptions({
  name: "TeacherManagement"
})

const loading = ref<boolean>(false)
const { paginationData, handleCurrentChange, handleSizeChange } = usePagination()

const DEFAULT_FORM_DATA: CreateOrUpdateTeacherRequestData = {
  id: undefined,
  username: "",
  email: "",
  password: ""
}
const dialogVisible = ref<boolean>(false)
const formRef = ref<FormInstance | null>(null)
const formData = ref<CreateOrUpdateTeacherRequestData>(cloneDeep(DEFAULT_FORM_DATA))
const formRules: FormRules<CreateOrUpdateTeacherRequestData> = {
  username: [{ required: true, trigger: "blur", message: "请输入用户名" }],
  email: [
    { required: true, trigger: "blur", message: "请输入邮箱" },
    {
      type: "email",
      message: "请输入正确的邮箱格式",
      trigger: ["blur", "change"]
    }
  ],
  password: [{ required: true, trigger: "blur", message: "请输入密码" }]
}

const resetPasswordDialogVisible = ref<boolean>(false)
const resetPasswordFormRef = ref<FormInstance | null>(null)
const currentTeacherId = ref<string | undefined>(undefined)
const resetPasswordFormData = reactive({
  password: ""
})
const resetPasswordFormRules: FormRules = {
  password: [
    { required: true, message: "请输入新密码", trigger: "blur" }
  ]
}

function handleCreateOrUpdate() {
  formRef.value?.validate((valid) => {
    if (!valid) {
      ElMessage.error("表单校验不通过")
      return
    }
    loading.value = true
    const api = formData.value.id === undefined ? createTeacherDataApi : updateTeacherDataApi
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

function handleResetPassword(row: TeacherData) {
  currentTeacherId.value = row.id
  resetPasswordFormData.password = ""
  resetPasswordDialogVisible.value = true
  nextTick(() => {
    resetPasswordFormRef.value?.clearValidate()
  })
}

function submitResetPassword() {
  resetPasswordFormRef.value?.validate((valid) => {
    if (!valid) {
      ElMessage.error("表单校验不通过")
      return
    }
    if (currentTeacherId.value === undefined) {
      ElMessage.error("教师ID丢失，无法重置密码")
      return
    }
    loading.value = true
    resetTeacherPasswordApi(currentTeacherId.value, resetPasswordFormData.password)
      .then(() => {
        ElMessage.success("密码重置成功")
        resetPasswordDialogVisible.value = false
      })
      .finally(() => {
        loading.value = false
      })
  })
}

function resetPasswordDialogClosed() {
  currentTeacherId.value = undefined
  resetPasswordFormRef.value?.resetFields()
}

function handleDelete(row: TeacherData) {
  ElMessageBox.confirm(`正在删除教师：${row.username}，确认删除？`, "提示", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning"
  }).then(() => {
    deleteTeacherDataApi(row.id).then(() => {
      ElMessage.success("删除成功")
      getTableData()
    })
  })
}

function handleUpdate(row: TeacherData) {
  dialogVisible.value = true
  formData.value = cloneDeep(row)
}

const tableData = ref<TeacherData[]>([])
const searchFormRef = ref<FormInstance | null>(null)
const searchData = reactive({
  username: "",
  email: ""
})

const sortData = reactive({
  sortBy: "create_date",
  sortOrder: "desc"
})

const multipleSelection = ref<TeacherData[]>([])

function getTableData() {
  loading.value = true
  getTeacherDataApi({
    currentPage: paginationData.currentPage,
    size: paginationData.pageSize,
    username: searchData.username,
    email: searchData.email,
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

function handleSelectionChange(selection: TeacherData[]) {
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
        multipleSelection.value.map(row => deleteTeacherDataApi(row.id))
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
})

// 当从其他页面切换回来时刷新数据
onActivated(() => {
  getTableData()
})
</script>

<template>
  <div class="app-container">
    <el-card v-loading="loading" shadow="never" class="search-wrapper">
      <el-form ref="searchFormRef" :model="searchData" label-width="70px" class="search-form">
        <el-row :gutter="20">
          <el-col :xs="24" :sm="12" :md="8" :lg="6">
            <el-form-item prop="username" label="用户名">
              <el-input v-model="searchData.username" placeholder="请输入用户名" clearable />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8" :lg="6">
            <el-form-item prop="email" label="邮箱">
              <el-input v-model="searchData.email" placeholder="请输入邮箱" clearable />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="24" :md="8" :lg="12">
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
          <el-button type="primary" :icon="CirclePlus" @click="dialogVisible = true">
            添加教师
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
          stripe
          :header-cell-style="{ background: '#f5f7fa', color: '#606266' }"
        >
          <el-table-column type="selection" width="55" align="center" fixed />
          <el-table-column prop="username" label="用户名" align="center" sortable="custom" min-width="120" />
          <el-table-column prop="email" label="邮箱" align="center" sortable="custom" min-width="180" />
          <el-table-column prop="createTime" label="创建时间" align="center" sortable="custom" min-width="160" />
          <el-table-column prop="updateTime" label="更新时间" align="center" sortable="custom" min-width="160" />
          <el-table-column fixed="right" label="操作" width="280" align="center">
            <template #default="scope">
              <div class="operation-buttons">
                <el-button type="success" text bg :icon="Edit" @click="handleUpdate(scope.row)">
                  修改
                </el-button>
                <el-divider direction="vertical" />
                <el-button type="warning" text bg :icon="Key" @click="handleResetPassword(scope.row)">
                  重置密码
                </el-button>
                <el-divider direction="vertical" />
                <el-button type="danger" text bg :icon="Delete" @click="handleDelete(scope.row)">
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
      :title="formData.id === undefined ? '新增教师' : '修改教师'"
      width="30%"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px" label-position="left">
        <el-form-item prop="username" label="用户名">
          <el-input v-model="formData.username" placeholder="请输入" />
        </el-form-item>
        <el-form-item v-if="formData.id === undefined" prop="email" label="用户邮箱">
          <el-input v-model="formData.email" placeholder="请输入" />
        </el-form-item>
        <el-form-item v-if="formData.id === undefined" prop="password" label="密码">
          <el-input v-model="formData.password" placeholder="请输入" />
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

    <el-dialog
      v-model="resetPasswordDialogVisible"
      title="重置密码"
      width="30%"
      @closed="resetPasswordDialogClosed"
    >
      <el-form ref="resetPasswordFormRef" :model="resetPasswordFormData" :rules="resetPasswordFormRules" label-width="100px" label-position="left">
        <el-form-item prop="password" label="新密码">
          <el-input v-model="resetPasswordFormData.password" type="password" show-password placeholder="请输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPasswordDialogVisible = false">
          取消
        </el-button>
        <el-button type="primary" :loading="loading" @click="submitResetPassword">
          确认重置
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.app-container {
  padding: 20px;
}

.search-wrapper {
  margin-bottom: 16px;

  :deep(.el-card__body) {
    padding: 20px;
  }

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
      height: 100%;
      :deep(.el-form-item__content) {
        display: flex;
        align-items: center;
        gap: 12px;
        height: 100%;
      }
    }
  }
}

.table-card {
  :deep(.el-card__body) {
    padding: 20px;
  }
}

.toolbar-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #ebeef5;

  .toolbar-left {
    display: flex;
    align-items: center;
    gap: 12px;

    .selection-info {
      color: #606266;
      font-size: 14px;
      padding-left: 8px;
      border-left: 1px solid #dcdfe6;
    }
  }

  .toolbar-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.table-wrapper {
  margin-bottom: 16px;

  :deep(.el-table) {
    font-size: 14px;

    .el-table__cell {
      padding: 12px 0;
    }

    .operation-buttons {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 4px;

      .el-button {
        padding: 4px 8px;
        font-size: 13px;
      }

      .el-divider--vertical {
        height: 16px;
        margin: 0 4px;
      }
    }
  }
}

.pager-wrapper {
  display: flex;
  justify-content: flex-end;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

@media screen and (max-width: 768px) {
  .app-container {
    padding: 12px;
  }

  .search-wrapper,
  .table-card {
    :deep(.el-card__body) {
      padding: 16px;
    }
  }

  .toolbar-wrapper {
    flex-direction: column;
    gap: 12px;
    align-items: stretch;

    .toolbar-left {
      justify-content: space-between;

      .selection-info {
        border-left: none;
        padding-left: 0;
      }
    }

    .toolbar-right {
      justify-content: flex-end;
    }
  }

  .table-wrapper {
    :deep(.el-table) {
      font-size: 13px;

      .operation-buttons {
        flex-direction: column;
        gap: 4px;

        .el-divider--vertical {
          display: none;
        }
      }
    }
  }

  .pager-wrapper {
    justify-content: center;

    :deep(.el-pagination) {
      flex-wrap: wrap;
    }
  }
}
</style>
