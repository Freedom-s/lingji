import type { AxiosInstance, AxiosRequestConfig, InternalAxiosRequestConfig } from "axios"
import { useUserStore } from "@/pinia/stores/user"
import { getToken } from "@@/utils/cache/cookies"
import axios from "axios"
import { get, merge } from "lodash-es"

/** 扩展配置类型，支持是否显示消息提示 */
interface ExtendedAxiosRequestConfig extends AxiosRequestConfig {
  hideMessage?: boolean
}

/** 退出登录并强制刷新页面（会重定向到登录页） */
function logout() {
  useUserStore().logout()
  location.reload()
}

/** 创建请求实例 */
function createInstance() {
  // 创建一个 axios 实例命名为 instance
  const instance = axios.create()
  // 请求拦截器
  instance.interceptors.request.use(
    // 发送之前
    config => config,
    // 发送失败
    error => Promise.reject(error)
  )
  // 响应拦截器
  instance.interceptors.response.use(
    (response) => {
      const apiData = response.data
      // 二进制数据则直接返回
      const responseType = response.request?.responseType
      if (responseType === "blob" || responseType === "arraybuffer") return apiData

      const code = apiData.code
      const config = response.config as ExtendedAxiosRequestConfig

      // 如果没有 code, 代表这不是项目后端开发的 api
      if (code === undefined) {
        if (!config.hideMessage) {
          ElMessage.error("非本系统的接口")
        }
        return Promise.reject(new Error("非本系统的接口"))
      }

      switch (code) {
        case 0:
        case 201:
          // 成功时不自动提示，由业务代码决定
          return apiData
        case 401:
          // Token 过期时
          return logout()
        default:
          // 业务错误时显示后端返回的 message
          if (!config.hideMessage) {
            ElMessage.error(apiData.message || "操作失败")
          }
          return Promise.reject(new Error(apiData.message || "Error"))
      }
    },
    (error) => {
      const config = error.config as ExtendedAxiosRequestConfig
      // status 是 HTTP 状态码
      const status = get(error, "response.status")
      const message = get(error, "response.data.message")

      let errorMessage = ""
      switch (status) {
        case 400:
          errorMessage = message || "请求错误"
          break
        case 401:
          errorMessage = message || "未授权"
          logout()
          break
        case 403:
          errorMessage = message || "拒绝访问"
          break
        case 404:
          errorMessage = "请求地址出错"
          break
        case 408:
          errorMessage = "请求超时"
          break
        case 500:
          errorMessage = message || "服务器内部错误"
          break
        case 501:
          errorMessage = "服务未实现"
          break
        case 502:
          errorMessage = "网关错误"
          break
        case 503:
          errorMessage = "服务不可用"
          break
        case 504:
          errorMessage = "网关超时"
          break
        case 505:
          errorMessage = "HTTP 版本不受支持"
          break
        default:
          errorMessage = error.message || "网络错误"
      }

      if (!config.hideMessage) {
        ElMessage.error(errorMessage)
      }
      return Promise.reject(error)
    }
  )
  return instance
}

/** 创建请求方法 */
function createRequest(instance: AxiosInstance) {
  return <T>(config: ExtendedAxiosRequestConfig): Promise<T> => {
    const token = getToken()
    // 默认配置
    const defaultConfig: ExtendedAxiosRequestConfig = {
      // 接口地址
      baseURL: import.meta.env.VITE_BASE_URL,
      // 请求头
      headers: {
        // 携带 Token
        "Authorization": token ? `Bearer ${token}` : undefined,
        "Content-Type": "application/json"
      },
      // 请求体
      data: {},
      // 请求超时
      timeout: 60000,
      // 跨域请求时是否携带 Cookies
      withCredentials: false
    }
    // 将默认配置 defaultConfig 和传入的自定义配置 config 进行合并成为 mergeConfig
    const mergeConfig = merge(defaultConfig, config)
    return instance(mergeConfig)
  }
}

/** 用于请求的实例 */
const instance = createInstance()

/** 用于请求的方法 */
export const request = createRequest(instance)
