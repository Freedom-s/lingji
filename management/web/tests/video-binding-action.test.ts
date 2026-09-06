import { describe, expect, it } from "vitest"
import { getVideoBindingAction } from "../src/pages/knowledgebase/components/video-binding-action"

describe("getVideoBindingAction", () => {
  it("shows an actionable unbind state after a video is mounted", () => {
    expect(getVideoBindingAction({ courseware_doc_id: "doc-1", knowledge_point_id: "node-1" })).toEqual({
      mode: "unbind",
      label: "取消挂载",
      type: "danger"
    })
  })

  it("keeps the mount action for an unbound video", () => {
    expect(getVideoBindingAction(null)).toEqual({
      mode: "bind",
      label: "挂载知识点",
      type: "primary"
    })
  })
})
