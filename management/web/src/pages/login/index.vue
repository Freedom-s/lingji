<script lang="ts" setup>
import type { FormInstance, FormRules } from "element-plus"
import type { LoginRequestData } from "./apis/type"
import { useUserStore } from "@/pinia/stores/user"
import { Key, Loading, Lock, Picture, User, DataAnalysis, School, Avatar, Files } from "@element-plus/icons-vue"
import { loginApi } from "./apis"

const router = useRouter()
const userStore = useUserStore()

/** 登录表单元素的引用 */
const loginFormRef = ref<FormInstance | null>(null)

/** 登录按钮 Loading */
const loading = ref(false)

/** 验证码图片 URL */
// const codeUrl = ref("")

/** 登录表单数据 */
const loginFormData: LoginRequestData = reactive({
  username: "",
  password: "",
  code: ""
})

/** 登录表单校验规则 */
const loginFormRules: FormRules = {
  username: [
    { required: true, message: "请输入用户名", trigger: "blur" }
  ],
  password: [
    { required: true, message: "请输入密码", trigger: "blur" },
    { min: 1, max: 16, message: "长度在 8 到 16 个字符", trigger: "blur" }
  ]
}

/** 登录 */
function handleLogin() {
  loginFormRef.value?.validate((valid) => {
    if (!valid) {
      ElMessage.error("表单校验不通过")
      return
    }
    loading.value = true
    loginApi(loginFormData).then(({ data }) => {
      userStore.setToken(data.token)
      userStore.setUserInfo({
        username: data.userInfo.username,
        isSuperuser: data.userInfo.isSuperuser,
        isSystem: data.userInfo.isSystem
      })
      router.push("/")
    }).catch(() => {
      loginFormData.password = ""
    }).finally(() => {
      loading.value = false
    })
  })
}

// /** 创建验证码 */
// function createCode() {
//   // 清空已输入的验证码
//   loginFormData.code = ""
//   // 清空验证图片
//   codeUrl.value = ""
//   // 获取验证码图片
//   getCaptchaApi().then((res) => {
//     codeUrl.value = res.data
//   })
// }

// // 初始化验证码
// createCode()
</script>

<template>
  <div class="login-container">
    <!-- 左侧登录表单区 -->
    <div class="login-section">
      <div class="login-header">
        <div class="logo-wrapper">
          <img src="/logo.svg" alt="灵机AI" class="logo" />
        </div>
      </div>

      <div class="login-title-section">
        <h1 class="login-title">教师管理后台</h1>
        <p class="login-subtitle">登录以管理您的教学资源</p>
      </div>

      <el-form ref="loginFormRef" :model="loginFormData" :rules="loginFormRules" @keyup.enter="handleLogin">
        <el-form-item prop="username">
          <el-input
            v-model.trim="loginFormData.username"
            placeholder="用户名"
            type="text"
            tabindex="1"
            :prefix-icon="User"
            size="large"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model.trim="loginFormData.password"
            placeholder="密码"
            type="password"
            tabindex="2"
            :prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>
        <el-button :loading="loading" type="primary" size="large" @click.prevent="handleLogin">
          立即登录
        </el-button>
      </el-form>

      <div class="login-footer">
        <p class="footer-text">🔒 教师专用管理入口 · 首次使用请联系管理员</p>
      </div>
    </div>

    <!-- 右侧品牌展示区 -->
    <div class="brand-section">
      <div class="brand-illustration">
        <img src="/dashboard.svg" alt="教育插画" class="illustration-img" />
      </div>
      <div class="brand-content">
        <div class="brand-logo">
          <img src="/logo.svg" alt="灵机AI" class="brand-logo-img" />
        </div>
        <h2 class="brand-title">灵机AI智能助学平台</h2>
        <div class="brand-slogan">
          <p class="slogan-line">AI赋能教育</p>
          <p class="slogan-line">智慧启迪未来</p>
        </div>
        <div class="brand-features">
          <div class="feature-tag">
            <el-icon :size="18"><DataAnalysis /></el-icon>
            <span>数据监控</span>
          </div>
          <div class="feature-tag">
            <el-icon :size="18"><User /></el-icon>
            <span>学生管理</span>
          </div>
          <div class="feature-tag">
            <el-icon :size="18"><School /></el-icon>
            <span>班级管理</span>
          </div>
          <div class="feature-tag">
            <el-icon :size="18"><Avatar /></el-icon>
            <span>助教管理</span>
          </div>
          <div class="feature-tag">
            <el-icon :size="18"><Files /></el-icon>
            <span>知识库管理</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.login-container {
  display: flex;
  width: 100%;
  min-height: 100vh;

  // 左侧登录表单区（45%）
  .login-section {
    width: 45%;
    min-width: 500px;
    background: white;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    align-items: stretch;
    position: relative;
    padding: 60px 40px 40px;

    .login-header {
      text-align: center;
      margin-bottom: 16px;

      .logo-wrapper {
        display: flex;
        justify-content: center;
        align-items: center;

        .logo {
          height: 100px;
          width: auto;
          max-width: none;
          filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.08));
          transition: all 0.3s ease;
          cursor: pointer;

          &:hover {
            transform: translateY(-2px);
            filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.12));
          }
        }
      }
    }

    .login-title-section {
      width: 100%;
      max-width: 440px;
      margin: 20px auto 40px;
      text-align: left;

      .login-title {
        font-size: 28px;
        font-weight: 700;
        line-height: 1.3;
        color: #1E293B;
        margin-bottom: 8px;
      }

      .login-subtitle {
        font-size: 14px;
        line-height: 1.6;
        color: #64748B;
        margin: 0;
      }
    }

    :deep(.el-form) {
      width: 100%;
      max-width: 440px;
      margin: 20px auto;
    }

    :deep(.el-form-item) {
      margin-bottom: 20px;
    }

    :deep(.el-form-item__label) {
      font-weight: 500;
      color: #334155;
      font-size: 14px;
    }

    :deep(.el-input__wrapper) {
      border-radius: 8px;
      border-color: #E2E8F0;
      padding: 10px 16px;
      box-shadow: 0 0 0 1px var(--color-border-base) inset;

      &:hover {
        border-color: #2563EB;
        box-shadow: 0 0 0 1px #2563EB inset;
      }

      &.is-focus {
        border-color: #2563EB;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
      }
    }

    :deep(.el-button) {
      width: 100%;
      height: 48px;
      border-radius: 8px;
      font-size: 16px;
      font-weight: 600;
      background: #2563EB;
      border: none;
      margin-top: 8px;
      box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);

      &:hover {
        background: #1D4ED8;
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.4);
      }
    }

    .login-footer {
      margin-top: 40px;
      text-align: center;

      .footer-text {
        font-size: var(--font-size-sm);
        color: var(--color-text-tertiary);
      }
    }
  }

  // 右侧品牌展示区（55%）
  .brand-section {
    width: 55%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding: var(--spacing-3xl);
    background: linear-gradient(135deg, #1E40AF 0%, #2563EB 50%, #3B82F6 100%);
    position: relative;
    overflow: hidden;

    // 背景装饰
    &::before {
      content: "";
      position: absolute;
      inset: 0;
      background-image:
        radial-gradient(circle at 20% 30%, rgba(255, 255, 255, 0.1) 0%, transparent 50%),
        radial-gradient(circle at 80% 70%, rgba(255, 255, 255, 0.08) 0%, transparent 50%);
    }

    .brand-illustration {
      position: relative;
      z-index: 1;
      margin-bottom: var(--spacing-2xl);
      animation: fadeInUp 0.8s ease-out;

      .illustration-img {
        width: 100%;
        max-width: 450px;
        height: auto;
        filter: drop-shadow(0 12px 24px rgba(0, 0, 0, 0.15));
      }
    }

    .brand-content {
      position: relative;
      z-index: 1;
      text-align: center;
      color: white;
      animation: fadeInUp 0.8s ease-out 0.2s both;

      .brand-logo {
        margin-bottom: var(--spacing-xl);

        .brand-logo-img {
          width: 160px;
          height: auto;
          filter: brightness(0) invert(1); // 反转为白色
        }
      }

      .brand-title {
        font-size: 40px;
        font-weight: var(--font-weight-bold);
        margin-bottom: var(--spacing-lg);
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
      }

      .brand-slogan {
        margin-bottom: var(--spacing-2xl);

        .slogan-line {
          font-size: var(--font-size-xl);
          font-weight: var(--font-weight-medium);
          opacity: 0.95;
          margin: var(--spacing-sm) 0;
        }
      }

      .brand-features {
        display: flex;
        flex-wrap: wrap;
        gap: var(--spacing-sm);
        justify-content: center;

        .feature-tag {
          padding: var(--spacing-sm) var(--spacing-lg);
          background: rgba(255, 255, 255, 0.15);
          backdrop-filter: blur(10px);
          border-radius: var(--radius-full);
          font-size: var(--font-size-sm);
          font-weight: var(--font-weight-medium);
          border: 1px solid rgba(255, 255, 255, 0.25);
          transition: all var(--transition-base) var(--ease-out);
          display: flex;
          align-items: center;
          gap: 6px;

          &:hover {
            background: rgba(255, 255, 255, 0.25);
            transform: translateY(-2px);
          }
        }
      }
    }
  }

  // 响应式设计
  @media (max-width: 1024px) {
    .login-section {
      width: 50%;
      min-width: 400px;
    }

    .brand-section {
      .brand-title {
        font-size: 32px;
      }
    }
  }

  @media (max-width: 768px) {
    flex-direction: column;

    .login-section {
      width: 100%;
      min-width: auto;
      min-height: 100vh;
      padding: 40px;

      .logo-wrapper .logo {
        height: 60px;
      }

      .login-title-section {
        text-align: center;
      }
    }

    .brand-section {
      display: none;
    }
  }
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
