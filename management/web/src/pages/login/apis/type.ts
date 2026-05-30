export interface LoginRequestData {
  /** admin 或 editor */
  username: "admin" | "editor"
  /** 密码 */
  password: string
}

export type CaptchaResponseData = ApiResponseData<string>

export interface UserInfo {
  id: string
  isSuperuser: boolean
  isSystem: boolean
  username: string
}

export type LoginResponseData = ApiResponseData<{ token: string, userInfo: UserInfo }>
