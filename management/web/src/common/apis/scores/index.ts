import type { ClassScoreResult, CreateExternalSourceData, ExternalScoreRecord, ExternalScoreSource, SaveScoringConfigData, ScoringConfig, StudentScore } from "./type"
import { request } from "@/http/axios"

/** 获取班级评分配置 */
export function getScoringConfigApi(classId: string) {
  return request<ScoringConfig>({
    url: `api/v1/scoring/config/${classId}`,
    method: "get"
  })
}

/** 保存班级评分配置 */
export function saveScoringConfigApi(classId: string, data: SaveScoringConfigData) {
  return request({
    url: `api/v1/scoring/config/${classId}`,
    method: "put",
    data
  })
}

/** 获取班级外部数据源列表 */
export function getExternalSourcesApi(classId: string) {
  return request<ExternalScoreSource[]>({
    url: `api/v1/scoring/external-source/${classId}`,
    method: "get"
  })
}

/** 新增外部数据源 */
export function createExternalSourceApi(data: CreateExternalSourceData) {
  return request<{ id: string }>({
    url: "api/v1/scoring/external-source",
    method: "post",
    data
  })
}

/** 修改外部数据源 */
export function updateExternalSourceApi(sourceId: string, data: { source_name: string, max_score: number }) {
  return request({
    url: `api/v1/scoring/external-source/${sourceId}`,
    method: "put",
    data
  })
}

/** 删除外部数据源 */
export function deleteExternalSourceApi(sourceId: string) {
  return request({
    url: `api/v1/scoring/external-source/${sourceId}`,
    method: "delete"
  })
}

/** 获取外部评分记录 */
export function getExternalRecordsApi(sourceId: string) {
  return request<ExternalScoreRecord[]>({
    url: `api/v1/scoring/external-record/${sourceId}`,
    method: "get"
  })
}

/** 下载预填班级学生花名册的外部成绩 Excel 模板 */
export function downloadExternalTemplateApi(sourceId: string) {
  return request<Blob>({
    url: `api/v1/scoring/external-record/template/${sourceId}`,
    method: "get",
    responseType: "blob"
  })
}

/** 上传 Excel 导入外部评分 */
export function uploadExternalRecordsApi(sourceId: string, file: File) {
  const formData = new FormData()
  formData.append("source_id", sourceId)
  formData.append("file", file)
  return request({
    url: "api/v1/scoring/external-record/upload",
    method: "post",
    data: formData,
    headers: { "Content-Type": "multipart/form-data" }
  })
}

/** 手动修改外部评分记录 */
export function updateExternalRecordApi(recordId: string, score: number) {
  return request({
    url: `api/v1/scoring/external-record/${recordId}`,
    method: "put",
    data: { score }
  })
}

/** 获取班级评分总表 */
export function getClassScoresApi(classId: string) {
  return request<ClassScoreResult>({
    url: `api/v1/scoring/result/${classId}`,
    method: "get"
  })
}

/** 获取单个学生评分详情 */
export function getStudentScoreApi(classId: string, studentId: string) {
  return request<StudentScore>({
    url: `api/v1/scoring/result/${classId}/${studentId}`,
    method: "get"
  })
}
