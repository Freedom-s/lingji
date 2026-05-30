import type { RouteRecordRaw } from "vue-router"
import { pinia } from "@/pinia"
import { constantRoutes, dynamicRoutes } from "@/router"
import { routerConfig } from "@/router/config"
import { flatMultiLevelRoutes } from "@/router/helper"

/**
 * 检查路由是否可访问
 * - 常驻路由：所有登录用户都可以访问
 * - requiresSystem 的动态路由：需要 isSystem 为 true
 */
function canAccessRoute(route: RouteRecordRaw, isSuperuser: boolean, isSystem: boolean): boolean {
  const requiresSystem = route.meta?.requiresSystem
  if (requiresSystem) {
    return isSystem
  }
  // 常驻路由，所有登录用户都可以访问
  return true
}

function filterDynamicRoutes(routes: RouteRecordRaw[], isSuperuser: boolean, isSystem: boolean) {
  const res: RouteRecordRaw[] = []
  routes.forEach((route) => {
    const tempRoute = { ...route }
    if (canAccessRoute(tempRoute, isSuperuser, isSystem)) {
      if (tempRoute.children) {
        tempRoute.children = filterDynamicRoutes(tempRoute.children, isSuperuser, isSystem)
        // 如果子路由被全部过滤，且父路由没有重定向目标，则不显示父路由
        if (tempRoute.children.length === 0 && !tempRoute.redirect) {
          return
        }
      }
      res.push(tempRoute)
    }
  })
  return res
}

export const usePermissionStore = defineStore("permission", () => {
  // 可访问的路由
  const routes = ref<RouteRecordRaw[]>([])

  // 有访问权限的动态路由
  const addRoutes = ref<RouteRecordRaw[]>([])

  // 根据权限生成可访问的路由
  const setRoutes = (isSuperuser: boolean, isSystem: boolean) => {
    const accessedRoutes = filterDynamicRoutes(dynamicRoutes, isSuperuser, isSystem)
    set(accessedRoutes)
  }

  // 所有路由 = 所有常驻路由 + 所有动态路由
  const setAllRoutes = () => {
    set(dynamicRoutes)
  }

  // 统一设置
  const set = (accessedRoutes: RouteRecordRaw[]) => {
    routes.value = constantRoutes.concat(accessedRoutes)
    addRoutes.value = routerConfig.thirdLevelRouteCache ? flatMultiLevelRoutes(accessedRoutes) : accessedRoutes
  }

  return { routes, addRoutes, setRoutes, setAllRoutes }
})

/**
 * @description 在 SPA 应用中可用于在 pinia 实例被激活前使用 store
 * @description 在 SSR 应用中可用于在 setup 外使用 store
 */
export function usePermissionStoreOutside() {
  return usePermissionStore(pinia)
}
