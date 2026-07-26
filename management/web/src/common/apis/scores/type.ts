/** 评分配置 */
export interface ScoringConfig {
  id: string | null
  class_id: string
  video_enabled: boolean
  video_weight: number
  quiz_enabled: boolean
  quiz_weight: number
  note_enabled: boolean
  note_weight: number
  flashcard_enabled: boolean
  flashcard_weight: number
  qa_enabled: boolean
  qa_weight: number
  external_enabled: boolean
  external_weight: number
}

export interface SaveScoringConfigData {
  video_enabled: boolean
  video_weight: number
  quiz_enabled: boolean
  quiz_weight: number
  note_enabled: boolean
  note_weight: number
  flashcard_enabled: boolean
  flashcard_weight: number
  qa_enabled: boolean
  qa_weight: number
  external_enabled: boolean
  external_weight: number
}

/** 外部数据源 */
export interface ExternalScoreSource {
  id: string
  class_id: string
  source_name: string
  max_score: number
  create_date?: string
}

export interface CreateExternalSourceData {
  class_id: string
  source_name: string
  max_score: number
}

/** 外部评分记录 */
export interface ExternalScoreRecord {
  id: string
  student_id: string
  student_name: string
  score: number
  create_date?: string
}

/** 评分结果 — 维度明细 */
export interface ScoreDimensions {
  video?: number
  quiz?: number
  note?: number
  flashcard?: number
  qa?: number
  external?: number
}

/** 评分结果 — 单个学生 */
export interface StudentScore {
  student_id: string
  student_name: string
  dimensions: ScoreDimensions
  total_score: number
}

/** 评分结果 — 全班 */
export interface ClassScoreResult {
  class_id: string
  config: ScoringConfig
  students: StudentScore[]
}
