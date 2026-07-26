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
