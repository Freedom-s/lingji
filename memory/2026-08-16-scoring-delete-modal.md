# 评分管理删除确认框异常排查

- **Symptom:** 评分管理删除外部数据源时，确认内容平铺在页面中，没有标准模态框布局。
- **Root cause:** 页面以程序式 API 调用 `ElMessageBox.confirm`，但未加载 `element-plus/theme-chalk/el-message-box.css`。按需构建清单也没有为评分页面包含该样式。
- **Fix:** 在评分管理页面显式导入 MessageBox 样式。
- **Evidence:** 修复前确认框计算样式为 `position: static`、`width: 1280px`、透明背景；修复后为 `position: relative`、`width: 420px`、白色背景，并恢复居中遮罩布局。
- **Regression test:** `management/web/tests/pages/scoring.test.ts`，确保程序式 MessageBox 的样式依赖不会再次被移除。
- **Verification:** 定向 Vitest 通过，Vite 生产构建通过，并使用教师测试账号在本地页面完成打开和取消确认框的交互验证；未执行实际删除。
- **Status:** DONE
