<script lang="ts" setup>
import type { CreateOrUpdateTableRequestData, TableData } from "@@/apis/tables/type"
import type { FormInstance, FormRules } from "element-plus"
import { createTableDataApi, deleteTableDataApi, getTableDataApi, resetPasswordApi, updateTableDataApi } from "@@/apis/tables"
import { usePagination } from "@@/composables/usePagination"
import { CirclePlus, Delete, Edit, Key, Refresh, RefreshRight, Search } from "@element-plus/icons-vue"
import { cloneDeep } from "lodash-es"

defineOptions({
  // 命名当前组件
  name: "UserManagement"
})

const loading = ref<boolean>(false)
const { paginationData, handleCurrentChange, handleSizeChange } = usePagination()

// #region 增
const DEFAULT_FORM_DATA: CreateOrUpdateTableRequestData = {
  id: undefined,
  username: "",
  email: "",
  password: ""
}
const dialogVisible = ref<boolean>(false)
const formRef = ref<FormInstance | null>(null)
const formData = ref<CreateOrUpdateTableRequestData>(cloneDeep(DEFAULT_FORM_DATA))
const formRules: FormRules<CreateOrUpdateTableRequestData> = {
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
// #region 重置密码
const resetPasswordDialogVisible = ref<boolean>(false)
const resetPasswordFormRef = ref<FormInstance | null>(null)
const currentUserId = ref<string | undefined>(undefined) // 用于存储当前要重置密码的用户ID
const resetPasswordFormData = reactive({
  password: ""
})
const resetPasswordFormRules: FormRules = {
  password: [
    { required: true, message: "请输入新密码", trigger: "blur" }
  ]
}
// #endregion
function handleCreateOrUpdate() {
  formRef.value?.validate((valid) => {
    if (!valid) {
      ElMessage.error("登录校验不通过")
      return
    }
    loading.value = true
    const api = formData.value.id === undefined ? createTableDataApi : updateTableDataApi
    api(formData.value).then(() => {
      ElMessage.success("操作成功")
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
// #endregion

// #region 重置密码处理
/**
 * 打开重置密码对话框
 * @param {TableData} row - 当前行用户数据
 */
function handleResetPassword(row: TableData) {
  currentUserId.value = row.id
  resetPasswordFormData.password = "" // 清空上次输入
  resetPasswordDialogVisible.value = true
  // 清除之前的校验状态
  nextTick(() => {
    resetPasswordFormRef.value?.clearValidate()
  })
}

/**
 * 提交重置密码表单
 */
function submitResetPassword() {
  resetPasswordFormRef.value?.validate((valid) => {
    if (!valid) {
      ElMessage.error("表单校验不通过")
      return
    }
    if (currentUserId.value === undefined) {
      ElMessage.error("用户ID丢失，无法重置密码")
      return
    }
    loading.value = true
    // 调用后端API重置密码
    resetPasswordApi(currentUserId.value, resetPasswordFormData.password)
      .then(() => {
        ElMessage.success("密码重置成功")
        resetPasswordDialogVisible.value = false
      })
      .catch((error: any) => {
        console.error("重置密码失败:", error)
        ElMessage.error("密码重置失败")
      })
      .finally(() => {
        loading.value = false
      })
  })
}

/**
 * 关闭重置密码对话框时重置状态
 */
function resetPasswordDialogClosed() {
  currentUserId.value = undefined
  resetPasswordFormRef.value?.resetFields() // 重置表单字段
}
// #endregion

// #region 删
function handleDelete(row: TableData) {
  ElMessageBox.confirm(`正在删除用户：${row.username}，确认删除？`, "提示", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning"
  }).then(() => {
    deleteTableDataApi(row.id).then(() => {
      ElMessage.success("删除成功")
      getTableData()
    })
  })
}
// #endregion

// #region 改
function handleUpdate(row: TableData) {
  dialogVisible.value = true
  formData.value = cloneDeep(row)
}
// #endregion

// #region 查
const tableData = ref<TableData[]>([])
const searchFormRef = ref<FormInstance | null>(null)
const searchData = reactive({
  username: "",
  email: ""
})

// 排序状态
const sortData = reactive({
  sortBy: "create_date",
  sortOrder: "desc" // 默认排序顺序 (最新创建的在前)
})

// 存储多选的表格数据
const multipleSelection = ref<TableData[]>([])

function getTableData() {
  loading.value = true
  getTableDataApi({
    currentPage: paginationData.currentPage,
    size: paginationData.pageSize,
    username: searchData.username,
    email: searchData.email,
    sort_by: sortData.sortBy,
    sort_order: sortData.sortOrder
  }).then(({ data }) => {
    paginationData.total = data.total
    tableData.value = data.list
    // 清空选中数据
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

// 表格多选事件处理
function handleSelectionChange(selection: TableData[]) {
  multipleSelection.value = selection
}

// 批量删除方法
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
      // 使用 Promise.all 并行处理所有删除请求
      await Promise.all(
        multipleSelection.value.map(row => deleteTableDataApi(row.id))
      )
      ElMessage.success("批量删除成功")
      getTableData()
    } catch {
      ElMessage.error("批量删除失败")
    } finally {
      loading.value = false
    }
  })
}
// #endregion

/**
 * @description 处理表格排序变化事件（只允许正序和倒序切换）
 * @param {object} sortInfo 排序信息对象，包含 prop 和 order
 * @param {string} sortInfo.prop 排序的字段名
 * @param {string | null} sortInfo.order 排序的顺序 ('ascending', 'descending', null)
 */
function handleSortChange({ prop }: { prop: string, order: string | null }) {
  // 如果点击的是同一个字段，则切换排序顺序
  if (sortData.sortBy === prop) {
    // 当前为正序则切换为倒序，否则切换为正序
    sortData.sortOrder = sortData.sortOrder === "asc" ? "desc" : "asc"
  } else {
    // 切换字段时，默认正序
    sortData.sortBy = prop
    sortData.sortOrder = "asc"
  }
  getTableData()
}

// 监听分页参数的变化
watch([() => paginationData.currentPage, () => paginationData.pageSize], getTableData, { immediate: true })
</script>

<template>
  <div class="app-container">
    <!-- 搜索区域 -->
    <el-card v-loading="loading" shadow="never" class="search-wrapper">
      <el-form ref="searchFormRef" :model="searchData" label-width="70px" class="search-form">
        <el-row :gutter="16">
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
          <el-col :xs="24" :sm="24" :md="16" :lg="12">
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

    <!-- 表格区域 -->
    <el-card v-loading="loading" shadow="never" class="table-card">
      <!-- 工具栏 -->
      <div class="toolbar-wrapper">
        <div class="toolbar-left">
          <el-button type="primary" :icon="CirclePlus" @click="dialogVisible = true">
            添加学生
          </el-button>
          <el-button type="danger" :icon="Delete" :disabled="multipleSelection.length === 0" @click="handleBatchDelete">
            批量删除
          </el-button>
          <span v-if="multipleSelection.length > 0" class="selection-info">
            已选择 {{ multipleSelection.length }} 项
          </span>
        </div>
      </div>

      <!-- 表格 -->
      <div class="table-wrapper">
        <el-table
          :data="tableData"
          @selection-change="handleSelectionChange"
          @sort-change="handleSortChange"
        >
          <el-table-column type="selection" width="55" align="center" fixed />
          <el-table-column prop="username" label="用户名" align="center" sortable="custom" min-width="120" />
          <el-table-column prop="email" label="邮箱" align="center" sortable="custom" min-width="180" />
          <el-table-column prop="createTime" label="创建时间" align="center" sortable="custom" min-width="160" />
          <el-table-column prop="updateTime" label="更新时间" align="center" sortable="custom" min-width="160" />
          <el-table-column fixed="right" label="操作" width="300" align="center">
            <template #default="scope">
              <div class="operation-buttons">
                <el-button type="success" text bg size="small" :icon="Edit" @click="handleUpdate(scope.row)">
                  修改
                </el-button>
                <el-divider direction="vertical" />
                <el-button type="warning" text bg size="small" :icon="Key" @click="handleResetPassword(scope.row)">
                  重置密码
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

      <!-- 分页 -->
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
    <!-- 新增/修改 -->
    <el-dialog
      v-model="dialogVisible"
      :title="formData.id === undefined ? '新增学生' : '修改学生'"
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

    <!-- 重置密码对话框 -->
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
</style>
