<script lang="ts" setup>
import { useAppStore } from "@/pinia/stores/app"
import { useSettingsStore } from "@/pinia/stores/settings"
import { useUserStore } from "@/pinia/stores/user"
import Notify from "@@/components/Notify/index.vue"
import { useDevice } from "@@/composables/useDevice"
import { useLayoutMode } from "@@/composables/useLayoutMode"
import { Breadcrumb, Hamburger, Sidebar } from "../index"

const { isMobile } = useDevice()
const { isTop } = useLayoutMode()
const router = useRouter()
const appStore = useAppStore()
const userStore = useUserStore()
const settingsStore = useSettingsStore()
const { showNotify } = storeToRefs(settingsStore)

/** 切换侧边栏 */
function toggleSidebar() {
  appStore.toggleSidebar(false)
}

/** 登出 */
function logout() {
  userStore.logout()
  router.push("/login")
}
</script>

<template>
  <div class="navigation-bar">
    <Hamburger
      v-if="!isTop || isMobile"
      :is-active="appStore.sidebar.opened"
      class="hamburger"
      @toggle-click="toggleSidebar"
    />
    <Breadcrumb v-if="!isTop || isMobile" class="breadcrumb" />
    <Sidebar v-if="isTop && !isMobile" class="sidebar" />
    <div class="right-menu">
      <Notify v-if="showNotify" class="right-menu-item" />
      <el-dropdown>
        <div class="right-menu-item user">
          <el-avatar :src="userStore.avatar" :size="30" />
          <span>{{ userStore.username }}</span>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="logout">
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.navigation-bar {
  height: var(--v3-navigationbar-height);
  overflow: hidden;
  color: var(--v3-navigationbar-text-color);
  display: flex;
  justify-content: space-between;
  padding: 0 var(--spacing-xl); // 增加左右内边距
  
  .hamburger {
    display: flex;
    align-items: center;
    height: 100%;
    padding: 0 var(--spacing-base);
    cursor: pointer;
    border-radius: var(--radius-base);
    transition: background-color var(--transition-base) var(--ease-out);
    
    &:hover {
      background-color: var(--color-bg-hover);
    }
  }
  
  .breadcrumb {
    flex: 1;
    padding: 0 var(--spacing-lg); // 增加面包屑的左右间距
    // 参考 Bootstrap 的响应式设计将宽度设置为 576
    @media screen and (max-width: 576px) {
      display: none;
    }
  }
  
  .sidebar {
    flex: 1;
    // 设置 min-width 是为了让 Sidebar 里的 el-menu 宽度自适应
    min-width: 0px;
    :deep(.el-menu) {
      background-color: transparent;
    }
    :deep(.el-sub-menu) {
      &.is-active {
        .el-sub-menu__title {
          color: var(--color-primary);
        }
      }
    }
  }
  
  .right-menu {
    margin-right: 0; // 移除右边距，因为父容器已有 padding
    height: 100%;
    display: flex;
    align-items: center;
    gap: var(--spacing-sm); // 使用 gap 替代 margin
    
    &-item {
      padding: var(--spacing-sm);
      cursor: pointer;
      border-radius: var(--radius-base);
      transition: background-color var(--transition-base) var(--ease-out);
      
      &:hover {
        background-color: var(--color-bg-hover);
      }
      
      &:last-child {
        margin-left: var(--spacing-md);
      }
    }
    
    .user {
      display: flex;
      align-items: center;
      padding: var(--spacing-xs) var(--spacing-md);
      
      .el-avatar {
        margin-right: var(--spacing-sm);
      }
      
      span {
        font-size: var(--font-size-base);
        font-weight: var(--font-weight-medium);
        color: var(--color-text-primary);
      }
    }
  }
}
</style>
