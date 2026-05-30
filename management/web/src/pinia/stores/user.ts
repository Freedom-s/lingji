import { pinia } from "@/pinia"
import { resetRouter } from "@/router"
import { setToken as _setToken, getToken, removeToken } from "@@/utils/cache/cookies"
import { useSettingsStore } from "./settings"
import { useTagsViewStore } from "./tags-view"

export const useUserStore = defineStore("user", () => {
  const token = ref<string>(getToken() || "")
  const username = ref<string>(localStorage.getItem("username") || "")
  const avatar = ref<string>("/avatar.jpg")
  const isSuperuser = ref<boolean>(localStorage.getItem("isSuperuser") === "true")
  const isSystem = ref<boolean>(localStorage.getItem("isSystem") === "true")
  const tagsViewStore = useTagsViewStore()
  const settingsStore = useSettingsStore()

  // 设置 Token
  const setToken = (value: string) => {
    _setToken(value)
    token.value = value
  }

  // 设置用户信息
  const setUserInfo = (userInfo: { username: string, isSuperuser: boolean, isSystem: boolean }) => {
    username.value = userInfo.username
    isSuperuser.value = userInfo.isSuperuser
    isSystem.value = userInfo.isSystem
    localStorage.setItem("username", userInfo.username)
    localStorage.setItem("isSuperuser", String(userInfo.isSuperuser))
    localStorage.setItem("isSystem", String(userInfo.isSystem))
  }

  // 登出
  const logout = () => {
    removeToken()
    token.value = ""
    username.value = ""
    isSuperuser.value = false
    isSystem.value = false
    localStorage.removeItem("username")
    localStorage.removeItem("isSuperuser")
    localStorage.removeItem("isSystem")
    resetRouter()
    resetTagsView()
  }

  // 重置 Token
  const resetToken = () => {
    removeToken()
    token.value = ""
  }

  // 重置 Visited Views 和 Cached Views
  const resetTagsView = () => {
    if (!settingsStore.cacheTagsView) {
      tagsViewStore.delAllVisitedViews()
      tagsViewStore.delAllCachedViews()
    }
  }

  return { token, username, avatar, isSuperuser, isSystem, setToken, setUserInfo, logout, resetToken }
})

/**
 * @description 在 SPA 应用中可用于在 pinia 实例被激活前使用 store
 * @description 在 SSR 应用中可用于在 setup 外使用 store
 */
export function useUserStoreOutside() {
  return useUserStore(pinia)
}
