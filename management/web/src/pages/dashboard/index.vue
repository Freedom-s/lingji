<script lang="ts" setup>
import { computed } from "vue"
import { useUserStore } from "@/pinia/stores/user"
import Admin from "./components/Admin.vue"
import Editor from "./components/Editor.vue"
import Teacher from "./components/Teacher.vue"

const userStore = useUserStore()
const isAdmin = userStore.isSuperuser
const isSystem = userStore.isSystem

const currentComponent = computed(() => {
  if (isSystem) return Admin
  if (isAdmin) return Teacher
  return Editor
})
</script>

<template>
  <component :is="currentComponent" />
</template>
