<div align="center">
  <img src="public/logo.svg" width="240" alt="灵机AI助学平台">
</div>

<div align="center">
  <h1>灵机AI助学平台</h1>
  <p>智能学习，开启未来</p>
  
  <img src="https://img.shields.io/badge/版本-1.0.0-blue" alt="版本">
  <img src="https://img.shields.io/badge/React-18.x-61dafb" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-5.x-3178c6" alt="TypeScript">
  <img src="https://img.shields.io/badge/Ant_Design-5.x-0170fe" alt="Ant Design">
  <img src="https://img.shields.io/badge/Tailwind_CSS-3.x-38bdf8" alt="Tailwind CSS">
</div>

---

## 🌟 项目简介

**灵机AI助学平台**是一个现代化的教育科技（EdTech）平台，专注于为学生和教师提供智能化的学习辅助工具。

### 核心特性

- 🤖 **AI智能对话** - 基于大语言模型的智能问答系统
- 📚 **知识库管理** - 高效的文档管理和知识组织
- 🔍 **智能搜索** - 快速准确的知识检索
- 🎯 **个性化学习** - 根据学习进度智能推荐
- 📊 **学习分析** - 可视化的学习数据统计
- 🎨 **现代化UI** - 大气美观的用户界面

---

## 🎨 设计特色

### 视觉设计
- **品牌蓝** (#2563EB) - 专业、可信赖
- **护眼灰白** (#F8FAFC) - 长时间使用不累眼
- **活力橙** (#F97316) - 强调重点，吸引注意

### 布局风格
- **Bento Grid 布局** - 便当盒式网格，秩序感强
- **卡片式设计** - 信息层次清晰
- **磨砂玻璃效果** - 提升视觉质感
- **轻柔阴影** - 增强空间层次

### 用户体验
- **高可读性字体** - Inter + Noto Sans SC
- **充足留白** - 避免视觉拥挤
- **流畅动画** - 微交互提升体验
- **响应式设计** - 适配各种设备

---

## 🚀 快速开始

### 环境要求

- Node.js >= 18.20.4
- pnpm >= 9.15.9

### 安装依赖

\`\`\`bash
cd web
pnpm install
\`\`\`

### 启动开发服务器

\`\`\`bash
pnpm dev
\`\`\`

访问 `http://localhost:8000` 查看应用。

### 构建生产版本

\`\`\`bash
pnpm build
\`\`\`

---

## 📁 项目结构

\`\`\`
web/
├── public/              # 静态资源
│   ├── logo.svg        # Logo 文件
│   └── favicon.svg     # 网站图标
├── src/
│   ├── assets/         # 资源文件
│   ├── components/     # 公共组件
│   │   └── ui/        # UI 组件库
│   ├── pages/         # 页面组件
│   │   ├── home/      # 首页
│   │   ├── chat/      # 对话页面
│   │   ├── datasets/  # 知识库
│   │   └── ...
│   ├── hooks/         # 自定义 Hooks
│   ├── layouts/       # 布局组件
│   ├── locales/       # 国际化
│   ├── theme/         # 主题配置
│   └── utils/         # 工具函数
├── DESIGN_SYSTEM.md   # 设计系统文档
├── LOCALIZATION_CHANGES.md  # 中文化清单
├── ASSETS_UPDATE.md   # 资源更新说明
└── package.json
\`\`\`

---

## 📚 文档

- [设计系统文档](DESIGN_SYSTEM.md) - 完整的设计规范和组件使用指南
- [优化总结](OPTIMIZATION_SUMMARY.md) - 项目优化记录
- [中文化清单](LOCALIZATION_CHANGES.md) - 界面中文化说明
- [资源更新说明](ASSETS_UPDATE.md) - Logo 和背景资源更新

---

## 🛠️ 技术栈

### 核心框架
- **React 18** - 用户界面库
- **TypeScript** - 类型安全
- **Umi 4** - 企业级前端框架

### UI 组件
- **Ant Design 5** - 企业级 UI 组件库
- **Radix UI** - 无障碍组件基础
- **Tailwind CSS** - 原子化 CSS 框架
- **Lucide React** - 图标库

### 状态管理
- **Zustand** - 轻量级状态管理
- **React Query** - 服务端状态管理
- **Ahooks** - React Hooks 工具库

### 工具库
- **Axios** - HTTP 客户端
- **Day.js** - 日期处理
- **i18next** - 国际化
- **React Hook Form** - 表单管理

---

## 🎯 主要功能

### 1. 首页
- 欢迎 Banner（渐变背景 + 快捷入口）
- 知识库展示（Bento Grid 布局）
- AI 应用推荐（卡片式展示）

### 2. 对话系统
- AI 助手管理
- 多会话支持
- 实时对话
- 历史记录

### 3. 知识库
- 文档上传
- 智能解析
- 分类管理
- 全文搜索

### 4. 个人中心
- 用户信息管理
- 模型配置
- 提示词管理
- 团队协作

---

## 🎨 设计规范

### 配色方案

\`\`\`css
/* 主色调 */
--brand-blue: #2563EB;
--brand-blue-light: #3B82F6;
--brand-blue-lighter: #60A5FA;

/* 强调色 */
--accent-orange: #F97316;
--accent-orange-dark: #EA580C;

/* 背景色 */
--bg-light: #F8FAFC;
--bg-blue-light: #EFF6FF;

/* 文字色 */
--text-primary: #1E293B;
--text-secondary: #64748B;
\`\`\`

### 字体系统

\`\`\`css
font-family: 'Inter', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
\`\`\`

### 间距系统

- 基准网格：8px
- 组件间距：16-24px
- 卡片内边距：16-24px
- 区块间距：32-48px

---

## 🔧 开发指南

### 代码规范

项目使用 ESLint + Prettier 进行代码规范检查：

\`\`\`bash
# 代码检查
pnpm lint

# 代码格式化
pnpm format
\`\`\`

### 组件开发

1. 所有组件使用 TypeScript
2. 使用函数式组件 + Hooks
3. 遵循 Ant Design 设计规范
4. 使用 Tailwind CSS 工具类

### 样式编写

\`\`\`tsx
// 推荐：使用 Tailwind CSS
<div className="bg-slate-50 rounded-2xl shadow-soft-md p-6">
  <h2 className="text-2xl font-bold text-slate-800">标题</h2>
</div>

// 复杂样式：使用 Less 模块
import styles from './index.less';
<div className={styles.container}>...</div>
\`\`\`

---

## 🧪 测试

\`\`\`bash
# 运行测试
pnpm test

# 测试覆盖率
pnpm test:coverage
\`\`\`

---

## 📦 部署

### 构建

\`\`\`bash
pnpm build
\`\`\`

构建产物在 `dist` 目录。

### Docker 部署

\`\`\`bash
docker build -t lingji-ai-web .
docker run -p 8000:8000 lingji-ai-web
\`\`\`

---

## 🤝 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

### 提交规范

\`\`\`
feat: 新功能
fix: 修复 bug
docs: 文档更新
style: 代码格式调整
refactor: 代码重构
perf: 性能优化
test: 测试相关
chore: 构建/工具链相关
\`\`\`

---

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](../LICENSE) 文件。

---

## 🙏 致谢

感谢以下开源项目：

- [React](https://react.dev/)
- [Ant Design](https://ant.design/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Umi](https://umijs.org/)
- [Radix UI](https://www.radix-ui.com/)

---

## 📞 联系我们

- 项目主页：[灵机AI助学平台](#)
- 问题反馈：[GitHub Issues](#)
- 邮箱：support@lingji-ai.com

---

<div align="center">
  <p>用 ❤️ 打造的智能学习平台</p>
  <p>© 2024 灵机AI助学平台. All rights reserved.</p>
</div>
