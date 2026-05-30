# 灵机AI助学平台 - 中文化修改清单

## 📝 修改说明

本文档记录了所有将英文界面文字改为中文的修改。

---

## ✅ 已完成的中文化修改

### 1. 首页（Home）

#### Banner 组件
**文件**: `web/src/pages/home/banner.tsx`
- ✅ "Welcome to RAGFlow" → "欢迎来到灵机AI助学平台"
- ✅ 副标题添加："智能学习，开启未来"
- ✅ 快捷卡片标签：
  - "System" → "快速开始"
  - "Setting up your LLM" → "配置你的LLM"
  - 新增："创建智能对话"
  - 新增："查看学习报告"

#### 知识库组件
**文件**: `web/src/pages/home/datasets.tsx`
- ✅ "Datasets" → "知识库"
- ✅ "See all" → "查看全部"
- ✅ "files" → "个文件"
- ✅ "Created" → "创建于"

#### AI应用组件
**文件**: `web/src/pages/home/applications.tsx`
- ✅ "Applications" → "AI应用"
- ✅ "All" → "全部"
- ✅ "Chat" → "对话"
- ✅ "Search" → "搜索"
- ✅ "Agent" → "AI代理"
- ✅ 应用名称中文化：
  - "Jarvis chatbot" → "Jarvis 智能助手"
  - "Search app 01" → "智能搜索 01"
  - "Chatbot 01" → "学习助手 01"
  - "Workflow 01" → "工作流 01"
- ✅ 应用类型中文化：
  - "Chat app" → "对话应用"
  - "Search app" → "搜索应用"
  - "Agent" → "AI代理"
- ✅ "查看更多应用" 按钮

#### 头部导航
**文件**: `web/src/pages/home/header.tsx`
- ✅ "Knowledge Base" → "知识库"
- ✅ "Chat" → "对话"
- ✅ "Search" → "搜索"
- ✅ "Flow" → "工作流"
- ✅ "stars" → "星标"

---

### 2. 聊天页面（Chat）

**文件**: `web/src/pages/chat/index.tsx`
- ✅ "Create Assistant" → "创建AI助手"
- ✅ "Chat" → "对话列表"
- ✅ 菜单项：
  - "Edit" → "编辑"
  - "Delete" → "删除"
  - "Rename" → "重命名"
  - "Embed into site" → "嵌入网站"

---

### 3. 知识库列表页面（Datasets）

**文件**: `web/src/pages/datasets/index.tsx`
- ✅ "Datasets" → "知识库"
- ✅ "Create dataset" → "创建知识库"
- ✅ "files" → "个文件"
- ✅ "Created" → "创建于"

---

### 4. 登录页面（Login）

**文件**: `web/src/pages/login/index.tsx`
- ✅ "Sign in with Github" → "使用 Github 登录"

---

### 5. 个人设置页面

#### 提示词管理
**文件**: `web/src/pages/profile-setting/prompt/index.tsx`
- ✅ "Prompt templates" → "提示词模板"
- ✅ "Create template" → "创建模板"
- ✅ "Prompt name" → "提示词名称"
- ✅ "Edit" → "编辑"

#### 团队管理
**文件**: `web/src/pages/profile-setting/team/index.tsx`
- ✅ "Team management" → "团队管理"
- ✅ "Create team" → "创建团队"
- ✅ "Yifan's team" → "Yifan 的团队"
- ✅ "Project" → "项目"
- ✅ "Storage" → "存储空间"
- ✅ "Edit" → "编辑"
- ✅ "Remove" → "移除"
- ✅ "Invite member" → "邀请成员"

---

## 📋 使用 i18n 的页面（无需修改）

以下页面已经使用了 i18next 国际化框架，会根据用户语言设置自动显示中文：

### 1. 知识库页面
**文件**: `web/src/pages/knowledge/index.tsx`
- 使用 `useTranslation('translation', { keyPrefix: 'knowledgeList' })`
- 所有文字都通过 `t()` 函数翻译

### 2. 登录页面（大部分）
**文件**: `web/src/pages/login/index.tsx`
- 使用 `useTranslation('translation', { keyPrefix: 'login' })`
- 表单标签、提示文字都已国际化

---

## 🎯 中文化原则

### 1. 术语统一
- **Dataset** → **知识库**（而非"数据集"）
- **Chat** → **对话**（而非"聊天"）
- **Assistant** → **AI助手**（而非"助理"）
- **Agent** → **AI代理**（而非"代理人"）
- **Prompt** → **提示词**（而非"提示"）
- **Template** → **模板**
- **Workflow** → **工作流**

### 2. 按钮文字
- **Create** → **创建**
- **Edit** → **编辑**
- **Delete** → **删除**
- **Remove** → **移除**
- **Rename** → **重命名**
- **Invite** → **邀请**
- **See all** → **查看全部**

### 3. 时间表达
- **Created** → **创建于**
- **Updated** → **更新于**

### 4. 数量单位
- **files** → **个文件**
- **stars** → **星标**

---

## 🔄 待中文化的页面

以下页面可能还需要进一步中文化（如果存在英文文字）：

### 高优先级
- ⏳ 文件管理页面（File Manager）
- ⏳ 文档查看器（Document Viewer）
- ⏳ 搜索页面（Search）
- ⏳ 工作流页面（Flow）

### 中优先级
- ⏳ 用户设置页面（User Settings）
- ⏳ 模型设置页面（Model Settings）
- ⏳ API 设置页面（API Settings）

### 低优先级
- ⏳ 错误提示信息
- ⏳ 表单验证信息
- ⏳ Toast 通知信息

---

## 🛠️ 如何继续中文化

### 方法 1：直接修改（适用于静态文字）
```tsx
// 修改前
<Button>Create dataset</Button>

// 修改后
<Button>创建知识库</Button>
```

### 方法 2：使用 i18n（推荐，适用于需要多语言支持）
```tsx
// 1. 引入 hook
import { useTranslation } from 'react-i18next';

// 2. 在组件中使用
const { t } = useTranslation('translation', { keyPrefix: 'yourPage' });

// 3. 使用翻译
<Button>{t('createDataset')}</Button>

// 4. 在 locales 文件中添加翻译
// web/src/locales/zh/translation.json
{
  "yourPage": {
    "createDataset": "创建知识库"
  }
}
```

---

## 📝 注意事项

### 1. 保持一致性
- 同一个英文词汇在整个系统中应该使用相同的中文翻译
- 参考本文档的"术语统一"部分

### 2. 用户体验
- 中文文字长度可能与英文不同，注意布局调整
- 确保按钮、标签等元素有足够空间显示中文

### 3. 技术考虑
- 优先使用 i18n 框架，便于后续维护和多语言支持
- 对于动态内容，确保翻译函数正确传递参数

### 4. 测试
- 修改后务必在浏览器中测试显示效果
- 检查是否有文字溢出或布局错乱
- 确认所有交互功能正常

---

## 📊 中文化进度

### 已完成
- ✅ 首页（100%）
- ✅ 聊天页面（100%）
- ✅ 知识库列表（100%）
- ✅ 登录页面（100%）
- ✅ 提示词管理（100%）
- ✅ 团队管理（100%）

### 进行中
- 🔄 文件管理（0%）
- 🔄 搜索页面（0%）
- 🔄 工作流页面（0%）

### 待开始
- ⏳ 用户设置
- ⏳ 模型设置
- ⏳ API 设置

---

## 🎉 总结

通过本次中文化工作，"灵机AI助学平台"的主要页面已经完成了中文化，包括：
- 首页的所有文字和标签
- 聊天页面的菜单和按钮
- 知识库相关页面
- 个人设置相关页面

这些修改使得平台更加符合中文用户的使用习惯，提升了用户体验。

---

**中文化完成时间**: 2024年1月16日  
**中文化版本**: v1.0.0  
**维护者**: Kiro AI Assistant
