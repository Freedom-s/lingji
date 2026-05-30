# 🚀 快速修复：浏览器标签显示"Ragflow-plus"

## 问题
浏览器标签页仍然显示"Ragflow-plus"而不是"灵机AI助学平台"

## 快速解决方案

### 步骤1：停止开发服务器
如果开发服务器正在运行，按 `Ctrl + C` 停止它

### 步骤2：清除UmiJS缓存
```bash
cd web
rm -rf .umi
rm -rf node_modules/.cache
```

### 步骤3：重新启动开发服务器
```bash
npm run dev
```

### 步骤4：清除浏览器缓存
- **Chrome/Edge**: 按 `Ctrl + Shift + Delete`，选择"缓存的图片和文件"，点击"清除数据"
- **或者使用无痕模式**: `Ctrl + Shift + N`
- **或者硬刷新**: `Ctrl + Shift + R`

### 步骤5：验证
1. 打开浏览器访问 `http://localhost:9222`
2. 查看浏览器标签页，应该显示"灵机AI助学平台"

---

## 已修改的文件

✅ `web/src/conf.json` - 配置文件中的appName  
✅ `web/src/pages/document.ejs` - HTML模板文件（新创建）  
✅ `management/web/.env` - 管理后台标题  
✅ `docs/index.html` - 文档页面标题

---

## 如果问题仍然存在

### 检查当前标题
打开浏览器开发者工具（F12），在Console中输入：
```javascript
document.title
```

### 检查配置文件
```bash
cat web/src/conf.json
```
应该显示：
```json
{
  "appName": "灵机AI助学平台"
}
```

### 检查HTML模板
```bash
cat web/src/pages/document.ejs
```
应该包含：
```html
<title>灵机AI助学平台</title>
```

---

## 为什么会出现这个问题？

1. **开发服务器缓存**：UmiJS在开发模式下会缓存编译结果
2. **浏览器缓存**：浏览器会缓存HTML文件和标题
3. **配置未生效**：修改配置后需要重启服务器

---

## 相关文档

- [完整标题更新文档](./TITLE_UPDATE.md)
- [品牌更新文档](./BRAND_UPDATE.md)

---

**更新日期**: 2026年1月16日
