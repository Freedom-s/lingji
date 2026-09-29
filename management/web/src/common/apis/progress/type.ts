export interface WeeklyProgressItem {
  id: string
  class_id: string
  name: string
  week_start: string
  week_end: string
  status: string
  create_date?: string
}

export interface CreateProgressData {
  name: string
  week_start: string
  week_end: string
  doc_ids: string[]
  quiz_thresholds: Record<string, number>
}

export interface BatchCreateProgressData extends CreateProgressData {
  class_ids: string[]
}

export interface ClassDocument {
  id: string
  name: string
  type: string
  has_quiz: boolean
}

export interface ProgressDocInfo {
  doc_id: string
  doc_name: string
  doc_type: string
  quiz_threshold: number
}

export interface DocStatus {
  doc_id: string
  is_completed: boolean
  video_completed: boolean
  quiz_passed: boolean
  has_notes: boolean
}

export interface StudentProgressStatus {
  student_id: string
  student_name: string
  doc_statuses: DocStatus[]
  total_completed: number
  total_docs: number
  is_all_completed: boolean
}

export interface ProgressSummary {
  total_students: number
  completed_count: number
  incomplete_count: number
  completion_rate: number
}

export interface ProgressStatusResult {
  progress: {
    id: string
    class_id: string
    class_name?: string
    name: string
    week_start: string
    week_end: string
    status: string
    docs: ProgressDocInfo[]
  }
  summary: ProgressSummary
  students: StudentProgressStatus[]
}

export interface TeacherProgressStudentSummary {
  student_id: string
  student_name: string
  completed_docs: number
  total_docs: number
}

export interface TeacherProgressReminderItem {
  id: string
  class_id: string
  class_name: string
  name: string
  week_start: string
  week_end: string
  state: "upcoming" | "active" | "overdue"
  day_count: number
  total_students: number
  completed_count: number
  incomplete_count: number
  completion_rate: number
  completed_students: TeacherProgressStudentSummary[]
  incomplete_students: TeacherProgressStudentSummary[]
}

export interface TeacherProgressReminderResult {
  summary: {
    total_progresses: number
    attention_progresses: number
    total_incomplete_students: number
  }
  items: TeacherProgressReminderItem[]
}

export type TeacherStudentProgressStatus = "completed" | "partial" | "not_started" | "upcoming"

export interface TeacherStudentProgressWeek {
  progress_id: string
  name: string
  week_start: string
  week_end: string
  state: "upcoming" | "active" | "overdue" | "unassigned"
  status: "completed" | "partial" | "not_started" | "unassigned"
  completed_docs: number
  total_docs: number
}

export interface TeacherStudentProgressOverviewStudent {
  student_id: string
  student_name: string
  class_id: string
  class_name: string
  status: TeacherStudentProgressStatus
  total_progresses: number
  tracked_progresses: number
  completed_progresses: number
  partial_progresses: number
  not_started_progresses: number
  overdue_progresses: number
  consecutive_incomplete_progresses: number
  completion_rate: number
  progresses: TeacherStudentProgressWeek[]
}

export interface TeacherStudentProgressOverviewResult {
  summary: {
    total_students: number
    completed_students: number
    partial_students: number
    not_started_students: number
    upcoming_students: number
    overdue_incomplete_students: number
    total_progresses: number
  }
  progresses: Array<{
    id: string
    name: string
    week_start: string
    week_end: string
    state: "upcoming" | "active" | "overdue"
  }>
  students: TeacherStudentProgressOverviewStudent[]
}

export type WeeklyProgressListResponseData = ApiResponseData<WeeklyProgressItem[]>
export type WeeklyProgressCreateResponseData = ApiResponseData<{ id: string }>
export type WeeklyProgressBatchCreateResponseData = ApiResponseData<{ ids: Record<string, string> }>
export type ProgressMutationResponseData = ApiResponseData<null>
export type ClassDocumentListResponseData = ApiResponseData<ClassDocument[]>
export type ProgressStatusResponseData = ApiResponseData<ProgressStatusResult>
export type TeacherProgressReminderResponseData = ApiResponseData<TeacherProgressReminderResult>
export type TeacherStudentProgressOverviewResponseData = ApiResponseData<TeacherStudentProgressOverviewResult>
