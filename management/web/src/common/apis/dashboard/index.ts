import type * as Dashboard from "./type"
import { request } from "@/http/axios"

/** 获取基础指标概览 */
export function getOverviewApi() {
  return request<Dashboard.OverviewResponseData>({
    url: "api/v1/dashboard/overview",
    method: "get"
  })
}

/** 获取活跃学生数趋势 */
export function getActiveStudentsApi(params?: { range?: "24h" | "7d" | "30d" }) {
  return request<Dashboard.ActiveStudentsResponseData>({
    url: "api/v1/dashboard/chart/active-students",
    method: "get",
    params
  })
}

/** 获取会话数趋势 */
export function getConversationTrendApi(params?: { range?: "24h" | "7d" | "30d" }) {
  return request<Dashboard.ConversationTrendResponseData>({
    url: "api/v1/dashboard/chart/conversation-trend",
    method: "get",
    params
  })
}

/** 获取最受欢迎的AI助教排行榜 */
export function getAssistantRankingApi(params?: { range?: "24h" | "7d" | "30d"; limit?: number }) {
  return request<Dashboard.AssistantRankingResponseData>({
    url: "api/v1/dashboard/ranking/assistants",
    method: "get",
    params
  })
}

/** 获取班级活跃度排行榜 */
export function getClassRankingApi(params?: { range?: "24h" | "7d" | "30d"; limit?: number }) {
  return request<Dashboard.ClassRankingResponseData>({
    url: "api/v1/dashboard/ranking/classes",
    method: "get",
    params
  })
}

/** 一键获取所有数据 */
export function getDashboardAllApi(params?: Dashboard.DashboardAllRequestData) {
  return request<Dashboard.DashboardAllResponseData>({
    url: "api/v1/dashboard/all",
    method: "get",
    params
  })
}
