import type {
  ClassDocument,
  CreateProgressData,
  ProgressStatusResult,
  WeeklyProgressItem
} from "./type"
import { request } from "@/http/axios"

export function getWeeklyProgressListApi(classId: string) {
  return request<WeeklyProgressItem[]>({
    url: `api/v1/progress/${classId}`,
    method: "get"
  })
}

export function createWeeklyProgressApi(classId: string, data: CreateProgressData) {
  return request<{ id: string }>({
    url: `api/v1/progress/${classId}`,
    method: "post",
    data
  })
}

export function updateWeeklyProgressApi(progressId: string, data: CreateProgressData) {
  return request({
    url: `api/v1/progress/detail/${progressId}`,
    method: "put",
    data
  })
}

export function deleteWeeklyProgressApi(progressId: string) {
  return request({
    url: `api/v1/progress/detail/${progressId}`,
    method: "delete"
  })
}

export function getClassDocumentsApi(classId: string) {
  return request<ClassDocument[]>({
    url: `api/v1/progress/docs/${classId}`,
    method: "get"
  })
}

export function getProgressStatusApi(progressId: string) {
  return request<ProgressStatusResult>({
    url: `api/v1/progress/status/${progressId}`,
    method: "get"
  })
}

export function refreshProgressStatusApi(progressId: string) {
  return request({
    url: `api/v1/progress/refresh/${progressId}`,
    method: "post"
  })
}
