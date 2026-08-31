import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const scoringPageSource = readFileSync(resolve(process.cwd(), "src/pages/scoring/index.vue"), "utf8")

describe("评分管理删除确认框", () => {
  it("加载程序式 MessageBox 所需的样式", () => {
    expect(scoringPageSource).toContain("import \"element-plus/theme-chalk/el-message-box.css\"")
  })
})

describe("外部成绩班级模板", () => {
  it("通过后端下载预填花名册的 xlsx 模板", () => {
    expect(scoringPageSource).toContain("downloadExternalTemplateApi")
    expect(scoringPageSource).toContain("班级成绩模板.xlsx")
    expect(scoringPageSource).toContain("accept=\".xlsx\"")
    expect(scoringPageSource).toContain("只需填写黄色的“得分”列")
  })

  it("必须选择数据源后才能下载或上传", () => {
    expect(scoringPageSource).toContain(":disabled=\"!uploadSourceId\"")
    expect(scoringPageSource).toContain("请先选择要导入成绩的数据源")
  })
})
