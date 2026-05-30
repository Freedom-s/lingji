<script lang="ts" setup>
import { useSettingsStore } from "@/pinia/stores/settings"
import { useWatermark } from "@@/composables/useWatermark"
import { getCssVar, setCssVar } from "@@/utils/css"
import { useResize } from "./composables/useResize"
import LeftMode from "./modes/LeftMode.vue"

// Layout 布局响应式
useResize()

const { setWatermark, clearWatermark } = useWatermark()
const settingsStore = useSettingsStore()
const { showTagsView, showWatermark } = storeToRefs(settingsStore)

// #region 隐藏标签栏时删除其高度，是为了让 Logo 组件高度和 Header 区域高度始终一致
const cssVarName = "--v3-tagsview-height"
const v3TagsviewHeight = getCssVar(cssVarName)
watchEffect(() => {
  showTagsView.value ? setCssVar(cssVarName, v3TagsviewHeight) : setCssVar(cssVarName, "0px")
})
// #endregion

// 开启或关闭系统水印
watchEffect(() => {
  showWatermark.value ? setWatermark(import.meta.env.VITE_APP_TITLE) : clearWatermark()
})
</script>

<template>
  <div>
    <!-- 左侧模式 -->
    <LeftMode />
  </div>
</template>
