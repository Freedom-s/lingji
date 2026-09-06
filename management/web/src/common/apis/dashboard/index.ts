import type * as Dashboard from "./type"
import { request } from "@/http/axios"

export interface LearningInsightClass {
  id: string
  name: string
}

export interface LearningInsightStudent {
  student_id: string
  student_name: string
  student_email: string
  class_ids: string[]
  class_names: string
  quiz_attempts: number
  correct_answers: number
  wrong_answers: number
  accuracy: number
  question_count: number
  activity_count: number
  last_active_at: string
}

export interface WrongQuestionInsight {
  doc_id: string
  document_name: string
  question_index: number
  question: string
  correct_answer: string
  attempt_count: number
  wrong_count: number
  wrong_student_count: number
  wrong_rate: number
}

export interface LearningInsightsData {
  classes: LearningInsightClass[]
  summary: {
    student_count: number
    active_student_count: number
    quiz_attempt_count: number
    wrong_answer_count: number
    question_count: number
  }
  students: LearningInsightStudent[]
  wrong_questions: WrongQuestionInsight[]
  range: "24h" | "7d" | "30d"
}

export interface QuizAttemptDetail {
  id: string
  doc_id: string
  document_name: string
  question_index: number
  question: string
  student_answer: string
  correct_answer: string
  is_correct: boolean
  answered_at: string
}

export interface StudentQuestionDetail {
  id: string
  conversation_id: string
  conversation_name: string
  assistant_name: string
  content: string
  asked_at: string
}

export interface StudentLearningDetailData {
  student: Pick<LearningInsightStudent, "student_id" | "student_name" | "student_email" | "class_ids" | "class_names">
  summary: {
    quiz_attempt_count: number
    correct_answer_count: number
    wrong_answer_count: number
    accuracy: number
    question_count: number
  }
  quiz_attempts: QuizAttemptDetail[]
  questions: StudentQuestionDetail[]
  range: "24h" | "7d" | "30d"
}

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

/** 获取学生学习活跃度和高频错题 */
export function getLearningInsightsApi(params?: {
  range?: "24h" | "7d" | "30d"
  class_id?: string
  limit?: number
}) {
  return request<ApiResponseData<LearningInsightsData>>({
    url: "api/v1/dashboard/learning-insights",
    method: "get",
    params
  })
}

/** 获取单个学生的逐题记录与提问内容 */
export function getStudentLearningDetailApi(
  studentId: string,
  params?: { range?: "24h" | "7d" | "30d" }
) {
  return request<ApiResponseData<StudentLearningDetailData>>({
    url: `api/v1/dashboard/students/${studentId}/learning-detail`,
    method: "get",
    params
  })
}
