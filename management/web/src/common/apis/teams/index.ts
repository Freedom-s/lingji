import type * as Tables from "./type"
import { request } from "@/http/axios"

// 查询团队整体数据
export function getTableDataApi(params: Tables.TableRequestData) {
  return request<Tables.TableResponseData>({
    url: "api/v1/teams",
    method: "get",
    params
  })
}

// 批量删除班级
export function batchDeleteTeamsApi(ids: (number | string)[]) {
  return request({
    url: "api/v1/teams/batch",
    method: "post",
    data: { ids }
  })
}

// 获取团队成员列表
export function getTeamMembersApi(teamId: number) {
  return request({
    url: `api/v1/teams/${teamId}/members`,
    method: "get"
  })
}

// 添加团队成员
export function addTeamMemberApi(data: { team_id: number, user_id: number }) {
  return request({
    url: `api/v1/teams/${data.team_id}/members`,
    method: "post",
    data: { user_id: data.user_id }
  })
}

// 移除团队成员
export function removeTeamMemberApi(data: { teamId: number, memberId: number }) {
  return request({
    url: `api/v1/teams/${data.teamId}/members/${data.memberId}`,
    method: "delete"
  })
}

/**
 * @description 获取用户列表
 * @param params 查询参数，例如 { size: number, currentPage: number, username: string }
 */
export function getUsersApi(params?: object) {
  return request({
    url: "api/v1/users",
    method: "get",
    params
  })
}

// ==================== 班级助教管理接口 ====================

/**
 * @description 获取班级助教列表
 * @param classId 班级ID
 */
export function getTeamAssistantsApi(classId: number) {
  return request({
    url: `api/v1/teams/${classId}/assistants`,
    method: "get"
  })
}

/**
 * @description 添加助教到班级
 * @param classId 班级ID
 * @param dialogId 助教ID（dialog表ID）
 */
export function addTeamAssistantApi(classId: number, dialogId: string) {
  return request({
    url: `api/v1/teams/${classId}/assistants`,
    method: "post",
    data: { dialog_id: dialogId }
  })
}

/**
 * @description 移除班级助教
 * @param classId 班级ID
 * @param assistantId 助教关联记录ID（class_dialog表的ID）
 */
export function removeTeamAssistantApi(classId: number, assistantId: string) {
  return request({
    url: `api/v1/teams/${classId}/assistants/${assistantId}`,
    method: "delete"
  })
}
