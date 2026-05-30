<script lang="ts" setup>
import type { FormInstance, FormRules } from "element-plus"
import { addTeamMemberApi, batchDeleteTeamsApi, getTableDataApi, getTeamMembersApi, getUsersApi, removeTeamMemberApi, getTeamAssistantsApi, addTeamAssistantApi, removeTeamAssistantApi } from "@@/apis/teams"
import { getAssistantDataApi } from "@/common/apis/assistants"
import { request } from "@/http/axios"
import { usePagination } from "@@/composables/usePagination"
import { CirclePlus, Delete, Plus, Refresh, Search, UserFilled, Edit, InfoFilled, Avatar } from "@element-plus/icons-vue"
import { computed, reactive, ref } from "vue"

defineOptions({
  name: "TeamManagement"
})

const loading = ref<boolean>(false)
const { paginationData, handleCurrentChange, handleSizeChange } = usePagination()

// 团队数据结构
interface TeamData {
  id: number
  name: string
  ownerName: string
  studentCount: number
  assistantCount?: number
  assistantNames?: string[]
  createTime: string
  updateTime: string
  status: string
}

// 创建班级表单
const createDialogVisible = ref<boolean>(false)
const createFormRef = ref<FormInstance | null>(null)
const createFormData = reactive({
  name: "",
  description: ""
})
const createFormRules: FormRules = {
  name: [{ required: true, message: "请输入班级名称", trigger: "blur" }]
}

// 提交创建班级
function handleCreate() {
  createFormRef.value?.validate((valid) => {
    if (!valid) {
      ElMessage.error("表单校验不通过")
      return
    }
    loading.value = true
    const payload = {
      name: createFormData.name,
      description: createFormData.description
    }
    request({
      url: "/api/v1/teams",
      method: "post",
      data: payload
    }).then(() => {
      ElMessage.success("班级创建成功")
      createDialogVisible.value = false
      createFormRef.value?.resetFields()
      getTableData()
    }).catch(() => {
      ElMessage.error("班级创建失败")
    }).finally(() => {
      loading.value = false
    })
  })
}

function resetCreateForm() {
  createFormRef.value?.resetFields()
  createFormData.name = ""
  createFormData.description = ""
}

//  删除
function handleDelete(row: TeamData) {
  ElMessageBox.confirm(`确认删除班级 "${row.name}" 吗？删除后将无法恢复。`, "提示", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning"
  }).then(() => {
    loading.value = true
    request({
      url: `/api/v1/teams/${row.id}`,
      method: "delete"
    }).then(() => {
      ElMessage.success("删除成功")
      getTableData()
    }).catch(() => {
      ElMessage.error("删除失败")
    }).finally(() => {
      loading.value = false
    })
  })
}

// 批量删除
function handleBatchDelete() {
  if (multipleSelection.value.length === 0) {
    ElMessage.warning("请至少选择一个班级")
    return
  }
  ElMessageBox.confirm(`确认删除选中的 ${multipleSelection.value.length} 个班级吗？删除后将无法恢复。`, "提示", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning"
  }).then(async () => {
    loading.value = true
    try {
      const ids = multipleSelection.value.map(item => item.id)
      await batchDeleteTeamsApi(ids)
      ElMessage.success("批量删除成功")
      getTableData()
    } catch {
      ElMessage.error("批量删除失败")
    } finally {
      loading.value = false
    }
  })
}

// 助教管理相关
interface TeamAssistant {
  id: string // class_dialog表记录ID，用于删除操作
  dialogId: string // 助教ID（dialog表ID）
  name: string
  description?: string
  addTime: string
}

const assistantDialogVisible = ref<boolean>(false)
const currentTeamForAssistant = ref<TeamData | null>(null)
const teamAssistants = ref<TeamAssistant[]>([])
const assistantLoading = ref<boolean>(false)

// 添加助教子对话框
const addAssistantToTeamDialogVisible = ref<boolean>(false)
const allAssistants = ref<any[]>([])
const selectedAssistants = ref<string[]>([])

// 计算属性：过滤出可添加的助教（不在当前班级助教列表中的助教）
const availableAssistants = computed(() => {
  const addedDialogIds = new Set(teamAssistants.value.map(a => a.dialogId))
  return allAssistants.value.filter(assistant => !addedDialogIds.has(assistant.id))
})

function handleManageAssistants(row: TeamData) {
  currentTeamForAssistant.value = row
  assistantDialogVisible.value = true
  getTeamAssistants(row.id)
}

// 获取班级助教列表
function getTeamAssistants(teamId: number) {
  assistantLoading.value = true
  getTeamAssistantsApi(teamId).then(({ data }) => {
    teamAssistants.value = data || []
  }).catch(() => {
    teamAssistants.value = []
  }).finally(() => {
    assistantLoading.value = false
  })
}

// 获取所有助教列表
function getAllAssistants() {
  getAssistantDataApi({
    currentPage: 1,
    size: 1000,
    sort_by: "create_date",
    sort_order: "desc"
  }).then(({ data }) => {
    allAssistants.value = data.list || []
  }).catch(() => {
    allAssistants.value = []
  })
}

// 打开添加助教对话框
function handleAddAssistantToTeam() {
  addAssistantToTeamDialogVisible.value = true
  selectedAssistants.value = []
  // 获取所有助教列表
  getAllAssistants()
}

// 确认添加助教到班级
function confirmAddAssistantToTeam() {
  if (selectedAssistants.value.length === 0) {
    ElMessage.warning("请至少选择一个助教")
    return
  }
  if (!currentTeamForAssistant.value) {
    ElMessage.error("当前班级信息不存在")
    return
  }
  loading.value = true
  // 批量添加助教
  const promises = selectedAssistants.value.map(assistantId =>
    addTeamAssistantApi(currentTeamForAssistant.value!.id, assistantId)
  )

  Promise.all(promises).then(() => {
    ElMessage.success(`成功添加 ${selectedAssistants.value.length} 个助教`)
    addAssistantToTeamDialogVisible.value = false
    selectedAssistants.value = []
    getTeamAssistants(currentTeamForAssistant.value!.id)
    // 刷新班级列表（更新助教数量和名称）
    getTableData()
  }).catch(() => {
    ElMessage.error("添加助教失败")
  }).finally(() => {
    loading.value = false
  })
}

// 移除班级助教
function handleRemoveAssistant(assistant: TeamAssistant) {
  ElMessageBox.confirm(`确认将助教 "${assistant.name}" 从班级中移除吗？`, "提示", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning"
  }).then(() => {
    if (!currentTeamForAssistant.value) {
      ElMessage.error("当前班级信息不存在")
      return
    }
    loading.value = true
    removeTeamAssistantApi(currentTeamForAssistant.value.id, assistant.id).then(() => {
      ElMessage.success("移除助教成功")
      getTeamAssistants(currentTeamForAssistant.value.id)
      // 刷新班级列表（更新助教数量和名称）
      getTableData()
    }).catch(() => {
      ElMessage.error("移除助教失败")
    }).finally(() => {
      loading.value = false
    })
  })
}

const tableData = ref<TeamData[]>([])

const searchData = reactive({
  name: ""
})

// 排序状态
const sortData = reactive({
  sortBy: "create_date",
  sortOrder: "desc" // 默认排序顺序 (最新创建的在前)
})

// 存储多选的表格数据
const multipleSelection = ref<TeamData[]>([])

function getTableData() {
  loading.value = true

  getTableDataApi({
    currentPage: paginationData.currentPage,
    size: paginationData.pageSize,
    name: searchData.name,
    sort_by: sortData.sortBy,
    sort_order: sortData.sortOrder
  }).then(({ data }) => {
    paginationData.total = data.total
    tableData.value = data.list.map((item: any) => ({
      id: item.id,
      name: item.name,
      ownerName: item.ownerName,
      studentCount: item.studentCount,
      assistantCount: item.assistantCount || 0,
      assistantNames: item.assistantNames || [],
      createTime: item.createTime,
      updateTime: item.updateTime,
      status: item.status
    }))
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

const searchFormRef = ref<FormInstance | null>(null)
function resetSearch() {
  searchFormRef.value?.resetFields()
  handleSearch()
}

// 表格多选事件处理
function handleSelectionChange(selection: TeamData[]) {
  multipleSelection.value = selection
}
// 团队成员管理相关
const memberDialogVisible = ref<boolean>(false)
const currentTeam = ref<TeamData | null>(null)
const teamMembers = ref<TeamMember[]>([])
const memberLoading = ref<boolean>(false)
// 添加成员相关状态
const addMemberDialogVisible = ref<boolean>(false)
const userList = ref<{ id: number, username: string }[]>([])
const userLoading = ref<boolean>(false)
const selectedUsers = ref<number[]>([])

// 计算属性：过滤出可添加的用户（不在当前团队成员列表中的用户）
const availableUsers = computed(() => {
  const memberUserIds = new Set(teamMembers.value.map(member => member.userId))
  return userList.value.filter(user => !memberUserIds.has(user.id))
})

// 计算属性：已选择的用户数量
const selectedUsersCount = computed(() => selectedUsers.value.length)

function handleManageMembers(row: TeamData) {
  currentTeam.value = row
  memberDialogVisible.value = true
  getTeamMembers(row.id)
}

// 获取团队成员列表
function getTeamMembers(teamId: number) {
  memberLoading.value = true
  getTeamMembersApi(teamId)
    .then((response: any) => {
      if (response.data && Array.isArray(response.data.list)) {
        teamMembers.value = response.data.list
      } else if (Array.isArray(response.data)) {
        teamMembers.value = response.data
      } else {
        teamMembers.value = []
      }
    })
    .catch(() => {
      teamMembers.value = []
    })
    .finally(() => {
      memberLoading.value = false
    })
}

// 添加成员
function handleAddMember() {
  // 打开添加成员对话框
  addMemberDialogVisible.value = true
  // 获取可添加的用户列表
  getUserList()
}

// 获取用户列表
function getUserList() {
  userLoading.value = true
  // 调用 getUsersApi 时传递 size 参数以获取所有用户
  getUsersApi({ size: 99999 }).then((res: any) => {
    if (res.data) {
      userList.value = res.data.list
    } else {
      userList.value = []
    }
  }).catch(() => {
    userList.value = []
  }).finally(() => {
    userLoading.value = false
  })
}

// 确认添加成员
function confirmAddMember() {
  if (selectedUsers.value.length === 0) {
    ElMessage.warning("请至少选择一个学生")
    return
  }

  if (!currentTeam.value) {
    ElMessage.error("当前团队信息不存在")
    return
  }

  // 批量添加成员
  const promises = selectedUsers.value.map(userId =>
    addTeamMemberApi({
      team_id: currentTeam.value.id,
      user_id: userId
    })
  )

  Promise.all(promises).then(() => {
    ElMessage.success(`成功添加 ${selectedUsers.value.length} 个成员`)
    // 关闭对话框
    addMemberDialogVisible.value = false
    // 重新获取成员列表
    getTeamMembers(currentTeam.value!.id)
    // 刷新团队列表（更新成员数量）
    getTableData()
    // 重置选择
    selectedUsers.value = []
  }).catch((error) => {
    console.error("添加成员失败:", error)
    ElMessage.error("添加成员失败")
  })
}

// 移除成员
function handleRemoveMember(member: TeamMember) {
  ElMessageBox.confirm(`确认将 ${member.username} 从团队中移除吗？`, "提示", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning"
  }).then(() => {
    if (!currentTeam.value || !currentTeam.value.id) {
      ElMessage.error("当前团队信息不存在")
      return
    }
    removeTeamMemberApi({
      teamId: currentTeam.value.id,
      memberId: member.userId
    }).then(() => {
      ElMessage.success("成员移除成功")
      // 重新获取成员列表
      if (currentTeam.value) {
        getTeamMembers(currentTeam.value.id)
      }
      getTableData()
    })
  })
}

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
    <el-card v-loading="loading" shadow="never" class="search-wrapper">
      <el-form ref="searchFormRef" :model="searchData" label-width="70px" class="search-form">
        <el-row :gutter="16">
          <el-col :xs="24" :sm="12" :md="8" :lg="6">
            <el-form-item prop="name" label="班级名称">
              <el-input v-model="searchData.name" placeholder="请输入班级名称" clearable />
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
          <el-button type="primary" :icon="Plus" @click="createDialogVisible = true">
            新建班级
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
        <el-table :data="tableData" @selection-change="handleSelectionChange" @sort-change="handleSortChange">
          <el-table-column type="selection" width="50" align="center" />
          <el-table-column prop="name" label="班级名称" align="center" min-width="120" sortable="custom"/>
          <el-table-column prop="ownerName" label="负责人" align="center" width="100"/>
          <el-table-column prop="studentCount" label="学生数量" align="center" width="90"/>
          <el-table-column prop="assistantCount" label="助教数量" align="center" width="90"/>
          <el-table-column label="助教名称" align="center" min-width="200">
            <template #default="scope">
              <div v-if="scope.row.assistantNames && scope.row.assistantNames.length > 0" class="assistant-names">
                <el-tag
                  v-for="(name, index) in scope.row.assistantNames"
                  :key="index"
                  type="primary"
                  size="small"
                  class="assistant-tag"
                  round
                >
                  {{ name }}
                </el-tag>
              </div>
              <span v-else class="no-data">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="createTime" label="创建时间" align="center" width="160" sortable="custom"/>
          <el-table-column prop="updateTime" label="更新时间" align="center" width="160" sortable="custom"/>
          <el-table-column label="操作" width="320" align="center" fixed="right">
            <template #default="scope">
              <div class="operation-buttons">
                <el-button type="primary" text bg size="small" :icon="Avatar" @click="handleManageAssistants(scope.row)">
                  助教管理
                </el-button>
                <el-divider direction="vertical" />
                <el-button type="success" text bg size="small" :icon="UserFilled" @click="handleManageMembers(scope.row)">
                  成员管理
                </el-button>
                <el-divider direction="vertical" />
                <el-button type="danger" text bg size="small" @click="handleDelete(scope.row)">
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

    <!-- 新建班级对话框 -->
    <el-dialog
      v-model="createDialogVisible"
      title="新建班级"
      width="30%"
      @closed="resetCreateForm"
    >
      <el-form ref="createFormRef" :model="createFormData" :rules="createFormRules" label-width="100px" label-position="left">
        <el-form-item prop="name" label="班级名称">
          <el-input v-model="createFormData.name" placeholder="请输入班级名称" />
        </el-form-item>
        <el-form-item prop="description" label="班级描述">
          <el-input
            v-model="createFormData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入班级描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">
          取消
        </el-button>
        <el-button type="primary" :loading="loading" @click="handleCreate">
          确认创建
        </el-button>
      </template>
    </el-dialog>

    <!-- 助教管理对话框 -->
    <el-dialog
      v-model="assistantDialogVisible"
      :title="`${currentTeamForAssistant?.name || ''} - 助教管理`"
      width="50%"
    >
      <div v-if="currentTeamForAssistant">
        <div class="team-info">
          <p><strong>班级名称：</strong>{{ currentTeamForAssistant.name }}</p>
          <p><strong>负责人：</strong>{{ currentTeamForAssistant.ownerName }}</p>
        </div>

        <div class="member-toolbar">
          <el-button type="primary" :icon="CirclePlus" size="small" @click="handleAddAssistantToTeam">
            添加助教
          </el-button>
        </div>

        <el-table :data="teamAssistants" style="width: 100%" v-loading="assistantLoading">
          <el-table-column prop="name" label="助教名称" align="center" />
          <el-table-column prop="description" label="助教描述" align="center" />
          <el-table-column prop="addTime" label="添加时间" align="center" />
          <el-table-column fixed="right" label="操作" width="120" align="center">
            <template #default="scope">
              <el-button
                type="danger"
                text
                bg
                size="small"
                @click="handleRemoveAssistant(scope.row)"
              >
                移除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="teamAssistants.length === 0" class="empty-data">
          <el-empty description="暂无助教数据" />
        </div>
      </div>
      <template #footer>
        <el-button @click="assistantDialogVisible = false">
          关闭
        </el-button>
      </template>
    </el-dialog>

    <!-- 添加助教到班级对话框 -->
    <el-dialog
      v-model="addAssistantToTeamDialogVisible"
      title="添加助教到班级"
      width="800px"
      :close-on-click-modal="false"
    >
      <div v-loading="assistantLoading" class="add-member-content">
        <!-- 班级信息 -->
        <div class="team-info-banner">
          <div class="info-item">
            <span class="label">当前班级</span>
            <span class="value">{{ currentTeamForAssistant?.name || '-' }}</span>
          </div>
          <div class="info-item">
            <span class="label">负责人</span>
            <span class="value">{{ currentTeamForAssistant?.ownerName || '-' }}</span>
          </div>
          <div class="info-item">
            <span class="label">当前助教</span>
            <span class="value">{{ teamAssistants.length }} 人</span>
          </div>
        </div>

        <!-- 提示信息 -->
        <div class="transfer-tip">
          <el-icon><InfoFilled /></el-icon>
          <span>从左侧列表选择要添加的助教，可使用搜索框快速查找</span>
        </div>

        <!-- 穿梭框 -->
        <el-transfer
          v-model="selectedAssistants"
          :data="availableAssistants"
          :props="{
            key: 'id',
            label: 'name'
          }"
          filterable
          filter-placeholder="搜索助教名称..."
          :titles="['待选助教', '已选助教']"
          :button-texts="['', '']"
          class="custom-transfer"
        >
          <template #default="{ option }">
            <div class="transfer-item">
              <span class="username">{{ option.name }}</span>
              <span v-if="option.description" class="description">{{ option.description }}</span>
            </div>
          </template>
        </el-transfer>

        <!-- 统计信息 -->
        <div class="selection-summary">
          <span class="summary-text">
            已选择 <strong>{{ selectedAssistants.length }}</strong> 名助教
          </span>
          <el-tag v-if="selectedAssistants.length > 0" type="success" size="small">
            {{ selectedAssistants.length }} 人待添加
          </el-tag>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="addAssistantToTeamDialogVisible = false" size="large">
            取消
          </el-button>
          <el-button
            type="primary"
            @click="confirmAddAssistantToTeam"
            :disabled="selectedAssistants.length === 0"
            size="large"
          >
            <el-icon class="btn-icon"><CirclePlus /></el-icon>
            确认添加
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 团队成员管理 -->
    <el-dialog
      v-model="memberDialogVisible"
      :title="`${currentTeam?.name || ''} - 成员管理`"
      width="50%"
    >
      <div v-if="currentTeam">
        <div class="team-info">
          <p><strong>班级名称：</strong>{{ currentTeam.name }}</p>
          <p><strong>负责人：</strong>{{ currentTeam.ownerName }}</p>
        </div>

        <div class="member-toolbar">
          <el-button type="primary" :icon="CirclePlus" size="small" @click="handleAddMember">
            添加成员
          </el-button>
        </div>

        <el-table :data="teamMembers" style="width: 100%" v-loading="memberLoading">
          <el-table-column prop="username" label="用户名" align="center" />
          <el-table-column prop="role" label="角色" align="center">
            <template #default="scope">
              {{ scope.row.role === 'owner' ? '拥有者' : (scope.row.role === 'normal' ? '普通成员' : scope.row.role) }}
            </template>
          </el-table-column>
          <el-table-column prop="joinTime" label="加入时间" align="center" />
          <el-table-column fixed="right" label="操作" width="150" align="center">
            <template #default="scope">
              <el-button
                type="danger"
                text
                bg
                size="small"
                @click="handleRemoveMember(scope.row)"
                :disabled="scope.row.role === 'owner'"
              >
                移除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="teamMembers.length === 0" class="empty-data">
          <el-empty description="暂无成员数据" />
        </div>
      </div>
      <template #footer>
        <el-button @click="memberDialogVisible = false">
          关闭
        </el-button>
      </template>
    </el-dialog>

    <!-- 添加成员对话框 -->
    <el-dialog
      v-model="addMemberDialogVisible"
      title="添加班级成员"
      width="800px"
      :close-on-click-modal="false"
    >
      <div v-loading="userLoading" class="add-member-content">
        <!-- 班级信息 -->
        <div class="team-info-banner">
          <div class="info-item">
            <span class="label">当前班级</span>
            <span class="value">{{ currentTeam?.name || '-' }}</span>
          </div>
          <div class="info-item">
            <span class="label">负责人</span>
            <span class="value">{{ currentTeam?.ownerName || '-' }}</span>
          </div>
          <div class="info-item">
            <span class="label">当前成员</span>
            <span class="value">{{ teamMembers.length }} 人</span>
          </div>
        </div>

        <!-- 提示信息 -->
        <div class="transfer-tip">
          <el-icon><InfoFilled /></el-icon>
          <span>从左侧列表选择要添加的学生，可使用搜索框快速查找</span>
        </div>

        <!-- 穿梭框 -->
        <el-transfer
          v-model="selectedUsers"
          :data="availableUsers"
          :props="{
            key: 'id',
            label: 'username'
          }"
          filterable
          filter-placeholder="搜索学生姓名..."
          :titles="['待选学生', '已选学生']"
          :button-texts="['', '']"
          class="custom-transfer"
        >
          <template #default="{ option }">
            <div class="transfer-item">
              <span class="username">{{ option.username }}</span>
            </div>
          </template>
        </el-transfer>

        <!-- 统计信息 -->
        <div class="selection-summary">
          <span class="summary-text">
            已选择 <strong>{{ selectedUsers.length }}</strong> 名学生
          </span>
          <el-tag v-if="selectedUsers.length > 0" type="success" size="small">
            {{ selectedUsers.length }} 人待添加
          </el-tag>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="addMemberDialogVisible = false" size="large">
            取消
          </el-button>
          <el-button
            type="primary"
            @click="confirmAddMember"
            :disabled="selectedUsers.length === 0"
            size="large"
          >
            <el-icon class="btn-icon"><CirclePlus /></el-icon>
            确认添加
          </el-button>
        </div>
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

<style lang="scss" scoped>
.el-alert {
  margin-bottom: 20px;
}

.team-info {
  margin-bottom: 20px;
  padding: 18px 20px;
  background: rgba(248, 250, 252, 0.92);
  border: 1px solid rgba(226, 232, 240, 0.84);
  border-radius: 18px;
}

.member-toolbar {
  margin-bottom: 16px;
}

.form-tip {
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-top: 5px;
}

.empty-data {
  margin-top: 20px;
  text-align: center;
}

.selection-tip {
  font-size: 13px;
  line-height: 1.5;
}

.add-member-content {
  .team-info-banner {
    display: flex;
    gap: 24px;
    padding: 18px 20px;
    margin-bottom: 20px;
    background: linear-gradient(180deg, rgba(248, 250, 252, 0.96) 0%, rgba(241, 245, 249, 0.88) 100%);
    border: 1px solid rgba(226, 232, 240, 0.84);
    border-radius: 18px;

    .info-item {
      display: flex;
      flex-direction: column;
      gap: 4px;

      .label {
        font-size: 12px;
        color: var(--color-text-tertiary);
      }

      .value {
        font-size: 16px;
        font-weight: 600;
        color: var(--color-text-primary);
      }
    }
  }

  .transfer-tip {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    margin-bottom: 16px;
    background: rgba(248, 250, 252, 0.92);
    border: 1px solid rgba(226, 232, 240, 0.84);
    border-radius: 14px;
    color: var(--color-text-secondary);
    font-size: 13px;

    .el-icon {
      font-size: 16px;
      color: var(--color-primary);
    }
  }

  .custom-transfer {
    :deep(.el-transfer-panel) {
      width: 280px;
      border-radius: 18px;
      border: 1px solid rgba(226, 232, 240, 0.84);
      box-shadow: none;

      .el-transfer-panel__header {
        background: rgba(248, 250, 252, 0.84);
        border-bottom: 1px solid rgba(226, 232, 240, 0.82);
        padding: 12px 16px;

        .el-checkbox__label {
          font-size: 14px;
          font-weight: 500;
          color: var(--color-text-primary);
        }
      }

      .el-transfer-panel__body {
        height: 300px;

        .el-transfer-panel__item {
          padding: 10px 16px;

          &:hover {
            background-color: rgba(248, 250, 252, 0.92);
          }
        }
      }

      .el-transfer-panel__filter {
        padding: 12px;
      }
    }

    :deep(.el-transfer__buttons) {
      padding: 0 20px;

      .el-button {
        width: 40px;
        height: 40px;
        min-width: 40px;
        border-radius: 999px;
        padding: 0 !important;

        &:nth-child(2) {
          margin-left: 0;
        }

        .el-icon {
          font-size: 16px;
        }
      }
    }
  }

  .transfer-item {
    display: flex;
    align-items: center;
    width: 100%;
    gap: 8px;

    .username {
      font-size: 14px;
      color: var(--color-text-primary);
      line-height: 1;
    }

    .description {
      font-size: 12px;
      color: var(--color-text-tertiary);
      line-height: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 150px;
    }
  }

  :deep(.el-transfer-panel__item) {
    .el-checkbox {
      display: flex;
      align-items: center;
      width: 100%;
    }

    .el-checkbox__label {
      display: flex;
      align-items: center;
      line-height: 1;
    }
  }

  .selection-summary {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid rgba(226, 232, 240, 0.82);

    .summary-text {
      font-size: 14px;
      color: var(--color-text-tertiary);

      strong {
        color: var(--color-primary);
        font-size: 16px;
      }
    }
  }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 0;

  .el-button {
    min-width: 100px;

    .btn-icon {
      margin-right: 4px;
    }
  }
}

@media screen and (max-width: 768px) {
  .add-member-content {
    .team-info-banner {
      flex-direction: column;
      gap: 12px;

      .info-item {
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
      }
    }

    .custom-transfer {
      :deep(.el-transfer-panel) {
        width: 100%;
      }

      :deep(.el-transfer__buttons) {
        padding: 10px 0;
        flex-direction: row;

        .el-button {
          transform: rotate(90deg);
        }
      }
    }
  }
}

.assistant-names {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
  align-items: center;

  .assistant-tag {
    margin: 0;
    padding: 0 10px;
  }
}
</style>
