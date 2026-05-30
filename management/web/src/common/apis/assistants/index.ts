import type * as Assistants from "./type"
import { request } from "@/http/axios"

/** 增 */
export function createAssistantDataApi(data: Assistants.CreateOrUpdateAssistantRequestData) {
  return request({
    url: "api/v1/assistants",
    method: "post",
    data
  })
}

/** 删 */
export function deleteAssistantDataApi(id: string) {
  return request({
    url: `api/v1/assistants/${id}`,
    method: "delete"
  })
}

/** 改 */
export function updateAssistantDataApi(data: Assistants.CreateOrUpdateAssistantRequestData) {
  return request({
    url: `api/v1/assistants/${data.id}`,
    method: "put",
    data
  })
}

/** 查 */
export function getAssistantDataApi(params: Assistants.AssistantRequestData) {
  return request<Assistants.AssistantResponseData>({
    url: "api/v1/assistants",
    method: "get",
    params
  })
}
