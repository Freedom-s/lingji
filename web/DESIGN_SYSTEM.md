# 灵机AI助学平台 - 设计系统文档

## 📐 设计理念

灵机AI助学平台采用现代化的EdTech设计风格，注重**大气美观**、**高可读性**和**长时间使用舒适度**。

---

## 🎨 配色方案

### 主色调
- **品牌蓝** `#2563EB` - 主要品牌色，用于主按钮、链接、选中状态
- **护眼灰白** `#F8FAFC` - 背景色，减少视觉疲劳
- **活力橙** `#F97316` - 强调色，用于CTA按钮和重要提示

### 辅助色
```less
// 文字颜色
@text-primary: #1E293B;    // 主要文字
@text-secondary: #64748B;  // 次要文字
@text-tertiary: #94A3B8;   // 辅助文字

// 边框颜色
@border-color: #E2E8F0;    // 默认边框

// 背景色
@layout-bg: #F8FAFC;       // 页面背景
```

### WCAG 对比度标准
所有文字与背景的对比度均符合 WCAG AA 标准（至少 4.5:1），确保长时间阅读不累眼。

---

## 🔤 字体系统

### 字体家族
```css
font-family: 'Inter', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
```

- **Inter** - 英文主字体，高可读性无衬线字体
- **Noto Sans SC** - 中文主字体，Google 开源字体，适合教育场景

### 字体大小
```less
@font-size-base: 16px;     // 基准字体
@font-size-lg: 18px;       // 大号文字
@font-size-xl: 24px;       // 标题
@font-size-2xl: 32px;      // 大标题
```

---

## 📏 间距系统

采用 8px 基准网格系统，确保视觉秩序感：

```less
@spacing-xs: 8px;
@spacing-sm: 16px;
@spacing-md: 24px;
@spacing-lg: 32px;
@spacing-xl: 48px;
```

### 留白原则
- 组件之间至少保持 16px 间距
- 卡片内边距至少 16px
- 区块之间至少保持 24px 间距

---

## 🎭 视觉效果

### 阴影系统（Soft Shadows）
```less
@shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.04);   // 轻微阴影
@shadow-md: 0 4px 16px rgba(0, 0, 0, 0.06);  // 中等阴影
@shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.08);  // 深度阴影
```

### 磨砂玻璃效果（Backdrop Blur）
```less
@glass-bg: rgba(255, 255, 255, 0.8);
@glass-blur: blur(12px);
```

使用方式：
```css
.glass-effect {
  background: @glass-bg;
  backdrop-filter: @glass-blur;
  -webkit-backdrop-filter: @glass-blur;
  border: 1px solid rgba(255, 255, 255, 0.3);
}
```

### 圆角设计
```less
border-radius: 12px;  // 标准圆角
border-radius: 16px;  // 卡片圆角
border-radius: 24px;  // 大型容器圆角
```

---

## 🧩 组件设计规范

### 卡片（Card）
- 圆角：16px
- 边框：1px solid #E2E8F0
- 阴影：hover 时显示 shadow-md
- 过渡：all 0.3s cubic-bezier(0.4, 0, 0.2, 1)
- hover 效果：向上移动 2px

### 按钮（Button）

#### 主按钮（Primary）
```css
background: #2563EB;
border-radius: 12px;
box-shadow: 0 2px 8px rgba(37, 99, 235, 0.2);
```

#### CTA按钮（活力橙）
```css
background: #F97316;
border-radius: 12px;
box-shadow: 0 2px 8px rgba(249, 115, 22, 0.2);
```

### AI对话框
- 背景：白色
- 边框：1px solid #E2E8F0
- 圆角：16px
- 内边距：24px
- 选中状态：渐变背景 + 品牌蓝边框

### 课程推荐卡片
- 使用渐变背景突出重点
- 图标采用圆角正方形容器
- hover 时图标放大 110%

### 学习进度
- 使用进度条组件
- 颜色：品牌蓝
- 圆角：8px

---

## 📱 布局系统

### Bento Grid（便当盒布局）
首页采用 Bento Grid 布局，特点：
- 网格化排列
- 卡片大小可变
- 视觉层次清晰
- 留白充足

### 响应式断点
```javascript
screens: {
  'sm': '640px',
  'md': '768px',
  'lg': '1024px',
  'xl': '1280px',
  '2xl': '1400px',
}
```

---

## 🎯 教育场景适配

### 重点区域突出
1. **AI对话框** - 使用品牌蓝边框 + 渐变背景
2. **课程推荐** - 使用活力橙标签 + 渐变图标
3. **学习进度** - 使用进度条 + 数据可视化

### 护眼设计
- 背景色：#F8FAFC（护眼灰白）
- 避免纯白背景
- 文字对比度符合 WCAG AA 标准
- 减少高饱和度颜色的大面积使用

### 可访问性（Accessibility）
- 所有交互元素支持键盘导航
- 图标配有文字说明
- 颜色不作为唯一的信息传达方式
- 支持屏幕阅读器

---

## 🚀 动画效果

### 过渡动画
```css
transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
```

### Hover 效果
- 卡片：向上移动 2px + 阴影加深
- 按钮：背景色加深 + 阴影加深
- 图标：放大 110%

### 页面加载动画
```css
@keyframes fade-in {
  0% { opacity: 0; transform: translateY(10px); }
  100% { opacity: 1; transform: translateY(0); }
}
```

---

## 📦 组件库

### 已优化组件
- ✅ 首页 Banner（渐变背景 + 快捷卡片）
- ✅ 知识库卡片（Bento Grid 布局）
- ✅ AI应用卡片（渐变图标 + hover 效果）
- ✅ 聊天页面（三栏布局 + 磨砂玻璃效果）

### 待优化组件
- ⏳ 登录页面
- ⏳ 个人设置页面
- ⏳ 文档查看器
- ⏳ 搜索页面

---

## 🛠️ 使用指南

### 1. 引入设计变量
```less
@import './theme/vars.less';
```

### 2. 使用 Tailwind 工具类
```jsx
<div className="bg-slate-50 rounded-2xl shadow-soft-md p-6">
  <h2 className="text-2xl font-bold text-slate-800">标题</h2>
  <p className="text-slate-600">内容</p>
</div>
```

### 3. 使用 Ant Design 组件
```jsx
<Button type="primary" className="rounded-xl">
  主按钮
</Button>
```

---

## 📚 参考资源

- [Inter 字体](https://fonts.google.com/specimen/Inter)
- [Noto Sans SC 字体](https://fonts.google.com/noto/specimen/Noto+Sans+SC)
- [WCAG 对比度标准](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html)
- [Tailwind CSS 文档](https://tailwindcss.com/docs)
- [Ant Design 文档](https://ant.design/)

---

## 🎨 设计工具

推荐使用以下工具进行设计：
- **Figma** - UI 设计
- **Coolors** - 配色方案
- **Contrast Checker** - 对比度检查

---

**版本**: v1.0.0  
**更新日期**: 2024年1月  
**维护者**: 灵机AI助学平台设计团队
