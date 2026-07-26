import type { RouteRecordRaw } from "vue-router"
import { routerConfig } from "@/router/config"
import { registerNavigationGuard } from "@/router/guard"
import { createRouter } from "vue-router"
import { flatMultiLevelRoutes } from "./helper"

const Layouts = () => import("@/layouts/index.vue")

/**
 * @name 常驻路由
 * @description 除了 redirect/403/404/login 等隐藏页面，其他页面建议设置唯一的 Name 属性
 */
export const constantRoutes: RouteRecordRaw[] = [
  {
    path: "/redirect",
    component: Layouts,
    meta: {
      hidden: true
    },
    children: [
      {
        path: ":path(.*)",
        component: () => import("@/pages/redirect/index.vue")
      }
    ]
  },
  {
    path: "/403",
    component: () => import("@/pages/error/403.vue"),
    meta: {
      hidden: true
    }
  },
  {
    path: "/404",
    component: () => import("@/pages/error/404.vue"),
    meta: {
      hidden: true
    },
    alias: "/:pathMatch(.*)*"
  },
  {
    path: "/login",
    component: () => import("@/pages/login/index.vue"),
    meta: {
      hidden: true
    }
  },
  {
    path: "/",
    component: Layouts,
    redirect: "/dashboard",
    children: [
      {
        path: "dashboard",
        component: () => import("@/pages/dashboard/index.vue"),
        name: "Dashboard",
        meta: {
          title: "数据概览",
          svgIcon: "dashboard",
          affix: true
        }
      }
    ]
  },
  {
    path: "/user-management",
    component: Layouts,
    redirect: "/user-management/index",
    children: [
      {
        path: "index",
        component: () => import("@/pages/user-management/index.vue"),
        name: "UserManagement",
        meta: {
          title: "学生管理",
          svgIcon: "user-management",
          affix: false,
          keepAlive: false
        }
      }
    ]
  },
  {
    path: "/team",
    component: Layouts,
    redirect: "/team/index",
    children: [
      {
        path: "index",
        component: () => import("@/pages/team-management/index.vue"),
        name: "Team",
        meta: {
          title: "班级管理",
          svgIcon: "team-management",
          affix: false,
          keepAlive: true
        }
      }
    ]
  },
  {
    path: "/assistant",
    component: Layouts,
    redirect: "/assistant/index",
    children: [
      {
        path: "index",
        component: () => import("@/pages/assistant-management/index.vue"),
        name: "AssistantManagement",
        meta: {
          title: "助教管理",
          svgIcon: "assistant",
          affix: false,
          keepAlive: true
        }
      }
    ]
  },
  {
    path: "/file",
    component: Layouts,
    redirect: "/file/index",
    children: [
      {
        path: "index",
        component: () => import("@/pages/file/index.vue"),
        name: "File",
        meta: {
          title: "教学文件管理",
          svgIcon: "file",
          affix: false,
          keepAlive: true
        }
      }
    ]
  },
  {
    path: "/knowledgebase",
    component: Layouts,
    redirect: "/knowledgebase/index",
    children: [
      {
        path: "index",
        component: () => import("@/pages/knowledgebase/index.vue"),
        name: "KnowledgeBase",
        meta: {
          title: "教学知识库管理",
          svgIcon: "kb",
          affix: false,
          keepAlive: true
        }
      }
    ]
  },
  {
    path: "/conversation",
    component: Layouts,
    redirect: "/conversation/index",
    children: [
      {
        path: "index",
        component: () => import("@/pages/conversation/index.vue"),
        name: "conversation",
        meta: {
          title: "学生会话管理",
          svgIcon: "conversation",
          affix: false,
          keepAlive: true
        }
      }
    ]
  },
  {
    path: "/scoring",
    component: Layouts,
    redirect: "/scoring/index",
    children: [
      {
        path: "index",
        component: () => import("@/pages/scoring/index.vue"),
        name: "ScoringManagement",
        meta: {
          title: "评分管理",
          svgIcon: "scoring",
          affix: false,
          keepAlive: true
        }
      }
    ]
  }
]

/**
 * @name 动态路由
 * @description 用来放置有权限 (Roles 属性) 的路由
 * @description 必须带有唯一的 Name 属性
 */
export const dynamicRoutes: RouteRecordRaw[] = [
  {
    path: "/teacher",
    component: Layouts,
    redirect: "/teacher/index",
    meta: {
      requiresSystem: true
    },
    children: [
      {
        path: "index",
        component: () => import("@/pages/teacher-management/index.vue"),
        name: "TeacherManagement",
        meta: {
          title: "教师管理",
          svgIcon: "teacher",
          affix: false,
          keepAlive: true,
          requiresSystem: true
        }
      }
    ]
  }
]

/** 路由实例 */
export const router = createRouter({
  history: routerConfig.history,
  routes: routerConfig.thirdLevelRouteCache ? flatMultiLevelRoutes(constantRoutes) : constantRoutes
})

/** 重置路由 */
export function resetRouter() {
  try {
    // 移除动态路由（教师管理等）
    const dynamicRouteNames = ["TeacherManagement"]
    router.getRoutes().forEach((route) => {
      const { name } = route
      if (name && dynamicRouteNames.includes(name as string)) {
        router.hasRoute(name) && router.removeRoute(name)
      }
    })
  } catch {
    // 强制刷新浏览器也行，只是交互体验不是很好
    location.reload()
  }
}

// 注册路由导航守卫
registerNavigationGuard(router)
