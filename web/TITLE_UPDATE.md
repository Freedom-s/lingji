# 网页标题更新文档

## 📋 更新概述

将所有网页标题从"RAGFlow"相关名称更新为"灵机AI助学平台"。

**更新日期**：2026年1月16日

---

## ✅ 已更新的文件

### 1. 前端主应用标题（方案一：配置文件）
**文件**：`web/src/conf.json`  
**配置项**：`appName`  
**原值**：`RAGFlow` 或类似  
**新值**：`灵机AI助学平台`

**说明**：
- 该配置通过 `web/.umirc.ts` 中的 `title: appName` 自动应用到网页标题
- UmiJS框架会自动将此值设置为 `<title>` 标签内容
- 适用于所有前端页面

### 1.1 前端主应用标题（方案二：HTML模板）
**文件**：`web/src/pages/document.ejs`  
**标签**：`<title>`  
**新值**：`灵机AI助学平台`

**说明**：
- 创建自定义HTML模板文件，直接设置标题
- 这个方法优先级更高，会覆盖配置文件中的设置
- 同时添加了SEO相关的meta标签（description、keywords）
- 设置了正确的favicon路径

---

### 2. 管理后台标题
**文件**：`management/web/.env`  
**配置项**：`VITE_APP_TITLE`  
**原值**：`Ragflow Plus`  
**新值**：`灵机AI助学平台 - 管理后台`

**说明**：
- Vite框架通过环境变量注入到 `management/web/index.html` 的 `%VITE_APP_TITLE%` 占位符
- 管理后台标题添加了"管理后台"后缀以区分前后台
- 需要重启开发服务器才能生效

---

### 3. 文档页面标题
**文件**：`docs/index.html`  
**标签**：`<title>`  
**原值**：`Ragflow-Plus`  
**新值**：`灵机AI助学平台 - 文档`

**说明**：
- 直接修改HTML文件中的 `<title>` 标签
- 文档页面标题添加了"文档"后缀以明确页面用途

---

## 🔍 标题配置说明

### 前端应用（web/）
```
配置文件：web/src/conf.json
配置方式：JSON配置
生效机制：UmiJS框架自动读取
标题格式：灵机AI助学平台
```

### 管理后台（management/web/）
```
配置文件：management/web/.env
配置方式：环境变量
生效机制：Vite框架注入HTML
标题格式：灵机AI助学平台 - 管理后台
```

### 文档页面（docs/）
```
配置文件：docs/index.html
配置方式：直接HTML标签
生效机制：静态HTML
标题格式：灵机AI助学平台 - 文档
```

---

## 🚀 如何验证更新

### 前端应用
1. **停止当前运行的开发服务器**（如果正在运行）：
   - 按 `Ctrl + C` 停止服务器
   
2. 启动开发服务器：
   ```bash
   cd web
   npm run dev
   ```
   
3. 打开浏览器访问 `http://localhost:9222`

4. 查看浏览器标签页标题，应显示"灵机AI助学平台"

5. **如果标题仍未更新**：
   - 清除浏览器缓存（Chrome: Ctrl+Shift+Delete）
   - 或使用无痕模式打开（Chrome: Ctrl+Shift+N）
   - 或硬刷新页面（Chrome: Ctrl+Shift+R）

### 管理后台
1. 启动开发服务器：
   ```bash
   cd management/web
   npm run dev
   ```
2. 打开浏览器访问管理后台地址
3. 查看浏览器标签页标题，应显示"灵机AI助学平台 - 管理后台"

### 文档页面
1. 直接打开 `docs/index.html` 文件
2. 或通过文档服务器访问
3. 查看浏览器标签页标题，应显示"灵机AI助学平台 - 文档"

---

## 📱 浏览器标签页显示效果

```
┌─────────────────────────────────┐
│ 🔵 灵机AI助学平台              │  ← 前端应用
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ 🔵 灵机AI助学平台 - 管理后台    │  ← 管理后台
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ 🔵 灵机AI助学平台 - 文档        │  ← 文档页面
└─────────────────────────────────┘
```

---

## 🔧 技术细节

### UmiJS标题配置（前端）
UmiJS通过 `.umirc.ts` 配置文件的 `title` 属性设置网页标题：

```typescript
// web/.umirc.ts
import { appName } from './src/conf.json';

export default defineConfig({
  title: appName,  // 从conf.json读取
  // ... 其他配置
});
```

### Vite标题配置（管理后台）
Vite通过环境变量和HTML模板占位符实现：

```html
<!-- management/web/index.html -->
<title>%VITE_APP_TITLE%</title>
```

```properties
# management/web/.env
VITE_APP_TITLE = 灵机AI助学平台 - 管理后台
```

---

## 📝 注意事项

1. **开发环境**：修改配置后需要**重启开发服务器**才能看到效果
2. **HTML模板优先级**：`document.ejs` 中的设置会覆盖 `.umirc.ts` 中的配置
3. **生产环境**：需要重新构建项目（`npm run build`）
4. **浏览器缓存**：如果标题未更新，尝试：
   - 清除浏览器缓存（Chrome: Ctrl+Shift+Delete）
   - 使用无痕模式（Chrome: Ctrl+Shift+N）
   - 硬刷新页面（Chrome: Ctrl+Shift+R）
5. **动态标题**：某些页面可能通过JavaScript动态修改标题，需要检查相关代码

## 🔍 故障排查

### 问题：标题仍然显示"Ragflow-plus"

**可能原因和解决方案**：

1. **开发服务器未重启**
   ```bash
   # 停止服务器（Ctrl+C），然后重新启动
   cd web
   npm run dev
   ```

2. **浏览器缓存**
   - 清除浏览器缓存
   - 使用无痕模式打开
   - 硬刷新页面（Ctrl+Shift+R）

3. **文件未保存**
   - 确认 `web/src/conf.json` 和 `web/src/pages/document.ejs` 已保存

4. **UmiJS缓存**
   ```bash
   cd web
   rm -rf .umi
   npm run dev
   ```

5. **检查实际运行的标题**
   - 打开浏览器开发者工具（F12）
   - 在Console中输入：`document.title`
   - 查看返回值

---

## 🎯 SEO优化建议

为了更好的搜索引擎优化，建议在不同页面使用不同的标题：

### 首页
```
灵机AI助学平台 - 智能学习，开启未来
```

### 知识库页面
```
知识库管理 - 灵机AI助学平台
```

### 对话页面
```
AI对话 - 灵机AI助学平台
```

### 实现方式
可以在各页面组件中使用 `useEffect` 动态设置：

```typescript
import { useEffect } from 'react';

useEffect(() => {
  document.title = '知识库管理 - 灵机AI助学平台';
}, []);
```

---

## ✨ 相关文档

- [品牌更新文档](./BRAND_UPDATE.md)
- [设计系统文档](./DESIGN_SYSTEM.md)
- [项目完成总结](./PROJECT_COMPLETION_SUMMARY.md)

---

**更新人员**：AI Assistant  
**项目名称**：灵机AI助学平台  
**版本**：1.0.0  
**更新日期**：2026年1月16日
