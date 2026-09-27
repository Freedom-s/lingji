import type * as Progress from "./type"
import { request } from "@/http/axios"

export function getWeeklyProgressListApi(classId: string) {
  return request<Progress.WeeklyProgressListResponseData>({
    url: `api/v1/progress/${classId}`,
    method: "get"
  })
}

export function createWeeklyProgressApi(classId: string, data: Progress.CreateProgressData) {
  return request<Progress.WeeklyProgressCreateResponseData>({
    url: `api/v1/progress/${classId}`,
    method: "post",
    data
  })
}

export function updateWeeklyProgressApi(progressId: string, data: Progress.CreateProgressData) {
  return request<Progress.ProgressMutationResponseData>({
    url: `api/v1/progress/detail/${progressId}`,
    method: "put",
    data
  })
}

export function deleteWeeklyProgressApi(progressId: string) {
  return request<Progress.ProgressMutationResponseData>({
    url: `api/v1/progress/detail/${progressId}`,
    method: "delete"
  })
}

export function getClassDocumentsApi(classId: string) {
  return request<Progress.ClassDocumentListResponseData>({
    url: `api/v1/progress/docs/${classId}`,
    method: "get"
  })
}

export function getProgressStatusApi(progressId: string) {
  return request<Progress.ProgressStatusResponseData>({
    url: `api/v1/progress/status/${progressId}`,
    method: "get"
  })
}

export function refreshProgressStatusApi(progressId: string) {
  return request<Progress.ProgressMutationResponseData>({
    url: `api/v1/progress/refresh/${progressId}`,
    method: "post"
  })
}

export function getTeacherProgressRemindersApi(params?: {
  class_id?: string
  progress_id?: string
}) {
  return request<Progress.TeacherProgressReminderResponseData>({
    url: "api/v1/progress/reminders",
    method: "get",
    params
  })
}

export function getTeacherStudentProgressOverviewApi(params?: { class_id?: string }) {
  return request<Progress.TeacherStudentProgressOverviewResponseData>({
    url: "api/v1/progress/overview",
    method: "get",
    params
  })
}
