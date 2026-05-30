<script lang="ts" setup>
import { ChatDotRound, Collection, Document, Files } from "@element-plus/icons-vue"
import SvgDashboard from "../images/dashboard.svg?component"

const stats = [
  {
    label: "我的知识库",
    value: "--",
    icon: Collection,
    description: "查看当前可供编辑与维护的知识资产。",
    tone: "blue"
  },
  {
    label: "对话次数",
    value: "--",
    icon: ChatDotRound,
    description: "快速感知内容与问答使用热度。",
    tone: "slate"
  },
  {
    label: "编辑文档",
    value: "--",
    icon: Document,
    description: "掌握文档维护与更新的总体进展。",
    tone: "amber"
  },
  {
    label: "我的文件",
    value: "--",
    icon: Files,
    description: "统一查看已上传和待整理的文件资源。",
    tone: "emerald"
  }
]
</script>

<template>
  <div class="app-container dashboard-shell">
    <div class="dashboard-content">
      <section class="hero-card dashboard-panel">
        <div class="hero-copy">
          <span class="hero-kicker">Editor Workspace</span>
          <h1 class="hero-title">欢迎回来，编辑者</h1>
          <p class="hero-description">
            在一个更安静、清晰的首页中查看内容资产与使用概况，把精力留给真正重要的编辑工作。
          </p>
        </div>

        <div class="hero-illustration">
          <SvgDashboard class="hero-graphic" />
        </div>
      </section>

      <section class="stats-grid">
        <article
          v-for="item in stats"
          :key="item.label"
          class="stat-card dashboard-panel"
        >
          <div :class="['stat-icon', `is-${item.tone}`]">
            <component :is="item.icon" />
          </div>
          <div class="stat-content">
            <p class="stat-label">{{ item.label }}</p>
            <h3 class="stat-value">{{ item.value }}</h3>
            <p class="stat-description">{{ item.description }}</p>
          </div>
        </article>
      </section>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.dashboard-shell {
  color: var(--color-text-primary);
}

.dashboard-content {
  max-width: 1540px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}

.dashboard-panel {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(226, 232, 240, 0.72);
  border-radius: 24px;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.04);
}

.hero-card {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(280px, 0.9fr);
  gap: 28px;
  align-items: center;
  padding: 32px;
}

.hero-kicker {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.04);
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-title {
  margin: 18px 0 10px;
  font-size: clamp(28px, 4vw, 38px);
  line-height: 1.08;
  font-weight: 700;
  letter-spacing: -0.04em;
}

.hero-description {
  max-width: 600px;
  margin: 0;
  color: var(--color-text-tertiary);
  font-size: 15px;
  line-height: 1.7;
}

.hero-illustration {
  display: flex;
  justify-content: center;
}

.hero-graphic {
  width: min(100%, 340px);
  height: auto;
  opacity: 0.92;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
}

.stat-card {
  padding: 22px;
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;

  :deep(svg) {
    width: 20px;
    height: 20px;
  }

  &.is-blue {
    background: rgba(37, 99, 235, 0.10);
    color: #2563eb;
  }

  &.is-slate {
    background: rgba(15, 23, 42, 0.08);
    color: #0f172a;
  }

  &.is-amber {
    background: rgba(245, 158, 11, 0.12);
    color: #b45309;
  }

  &.is-emerald {
    background: rgba(16, 185, 129, 0.10);
    color: #059669;
  }
}

.stat-content {
  margin-top: 22px;
}

.stat-label {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 14px;
  font-weight: 600;
}

.stat-value {
  margin: 14px 0 10px;
  color: var(--color-text-primary);
  font-size: 34px;
  line-height: 1;
  font-weight: 700;
  letter-spacing: -0.04em;
}

.stat-description {
  margin: 0;
  color: var(--color-text-tertiary);
  font-size: 13px;
  line-height: 1.7;
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .hero-card {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .hero-card,
  .stat-card {
    padding: 20px;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
