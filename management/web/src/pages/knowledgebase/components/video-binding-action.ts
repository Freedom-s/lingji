export interface VideoBindingState {
  courseware_doc_id?: string | null
  knowledge_point_id?: string | null
}

export function getVideoBindingAction(binding?: VideoBindingState | null) {
  const mounted = Boolean(binding?.courseware_doc_id && binding?.knowledge_point_id)
  return mounted
    ? { mode: "unbind" as const, label: "取消挂载", type: "danger" as const }
    : { mode: "bind" as const, label: "挂载知识点", type: "primary" as const }
}
