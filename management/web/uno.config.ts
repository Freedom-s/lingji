import { defineConfig, presetAttributify, presetWind3 } from "unocss"

export default defineConfig({
  // 预设
  presets: [
    // 属性化模式 & 无值的属性模式
    presetAttributify({
      prefix: "un-",
      prefixedOnly: false
    }),
    // 默认预设
    presetWind3({
      important: "#app"
    })
  ],
  // 主题配置 - 使用设计令牌
  theme: {
    colors: {
      primary: {
        DEFAULT: '#2563EB',
        hover: '#1D4ED8',
        active: '#1E40AF',
        light: '#3B82F6',
        lighter: '#60A5FA',
        lightest: '#DBEAFE',
      },
      accent: {
        DEFAULT: '#F97316',
        hover: '#EA580C',
        active: '#C2410C',
        light: '#FB923C',
        lighter: '#FDBA74',
        lightest: '#FED7AA',
      },
      bg: {
        base: '#F8FAFC',
        elevated: '#FFFFFF',
        hover: '#F1F5F9',
        active: '#E2E8F0',
      },
      text: {
        primary: '#1E293B',
        secondary: '#334155',
        tertiary: '#64748B',
        disabled: '#94A3B8',
      },
      border: {
        base: '#E2E8F0',
        light: '#F1F5F9',
        dark: '#CBD5E1',
      },
    },
    spacing: {
      'xs': '4px',
      'sm': '8px',
      'md': '12px',
      'base': '16px',
      'lg': '20px',
      'xl': '24px',
      '2xl': '32px',
      '3xl': '40px',
      '4xl': '48px',
    },
    borderRadius: {
      'sm': '6px',
      'base': '8px',
      'md': '10px',
      'lg': '12px',
      'xl': '16px',
      '2xl': '20px',
    },
    boxShadow: {
      'xs': '0 1px 2px rgba(0, 0, 0, 0.05)',
      'sm': '0 2px 4px rgba(0, 0, 0, 0.06)',
      'base': '0 4px 12px rgba(0, 0, 0, 0.08)',
      'md': '0 6px 16px rgba(0, 0, 0, 0.10)',
      'lg': '0 8px 24px rgba(0, 0, 0, 0.12)',
      'xl': '0 12px 32px rgba(0, 0, 0, 0.15)',
    },
  },
  // 自定义规则
  rules: [],
  // 自定义快捷方式
  shortcuts: {
    "wh-full": "w-full h-full",
    "flex-center": "flex justify-center items-center",
    "flex-x-center": "flex justify-center",
    "flex-y-center": "flex items-center",
    // 布局快捷方式
    "container-padding": "p-xl",
    "section-spacing": "mb-2xl",
    "card-base": "bg-bg-elevated rounded-lg shadow-base p-xl",
    "card-hover": "transition-all duration-200 hover:shadow-md hover:-translate-y-0.5",
    // 文本快捷方式
    "text-heading": "text-text-primary font-semibold",
    "text-body": "text-text-secondary",
    "text-caption": "text-text-tertiary text-sm",
  }
})
