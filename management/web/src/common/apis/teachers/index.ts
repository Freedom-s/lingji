import type * as Teachers from "./type"
import { request } from "@/http/axios"

/** 增 */
export function createTeacherDataApi(data: Teachers.CreateOrUpdateTeacherRequestData) {
  return request({
    url: "api/v1/teachers",
    method: "post",
    data
  })
}

/** 删 */
export function deleteTeacherDataApi(id: string) {
  return request({
    url: `api/v1/teachers/${id}`,
    method: "delete"
  })
}

/** 改 */
export function updateTeacherDataApi(data: Teachers.CreateOrUpdateTeacherRequestData) {
  return request({
    url: `api/v1/teachers/${data.id}`,
    method: "put",
    data
  })
}

/** 查 */
export function getTeacherDataApi(params: Teachers.TeacherRequestData) {
  return request<Teachers.TeacherResponseData>({
    url: "api/v1/teachers",
    method: "get",
    params
  })
}

/**
 * 重置教师密码
 * @param teacherId 教师ID
 * @param password 新密码
 * @returns BaseResponse
 */
export function resetTeacherPasswordApi(teacherId: string, password: string) {
  return request({
    url: `api/v1/teachers/${teacherId}/reset-password`,
    method: "put",
    data: { password }
  })
}
