export interface CreateOrUpdateAssistantRequestData {
  id?: string
  assistant_name: string
  description?: string
  knowledge_bases?: string[]
}

export interface AssistantRequestData {
  /** 当前页码 */
  currentPage: number
  /** 查询条数 */
  size: number
  /** 查询参数：助教名称 */
  assistant_name?: string
  /** 排序字段 */
  sort_by: string
  /** 排序方式 */
  sort_order: string
}

export interface AssistantData {
  id: string
  name: string
  description?: string
  knowledgeBaseIds?: string[]
  knowledgeBaseNames?: string[]
  createTime: string
  updateTime: string
}

export type AssistantResponseData = ApiResponseData<{
  list: AssistantData[]
  total: number
}>
