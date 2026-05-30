export interface OverviewData {
  student_count: number
  class_count: number
  conversation_count: number
  assistant_count: number
  file_count: number
  knowledgebase_count: number
}

export interface ChartDataPoint {
  time: string
  count: number
}

export interface AssistantRankingItem {
  assistant_id: string
  assistant_name: string
  assistant_icon: string
  call_count: number
}

export interface ClassRankingItem {
  class_id: string
  class_name: string
  conversation_count: number
}

export interface DashboardAllData {
  overview: OverviewData
  active_students: ChartDataPoint[]
  conversation_trend: ChartDataPoint[]
  assistant_ranking: AssistantRankingItem[]
  class_ranking: ClassRankingItem[]
}

export interface DashboardAllRequestData {
  range?: "24h" | "7d" | "30d"
  limit?: number
}

export type OverviewResponseData = ApiResponseData<OverviewData>
export type ActiveStudentsResponseData = ApiResponseData<ChartDataPoint[]>
export type ConversationTrendResponseData = ApiResponseData<ChartDataPoint[]>
export type AssistantRankingResponseData = ApiResponseData<AssistantRankingItem[]>
export type ClassRankingResponseData = ApiResponseData<ClassRankingItem[]>
export type DashboardAllResponseData = ApiResponseData<DashboardAllData>
