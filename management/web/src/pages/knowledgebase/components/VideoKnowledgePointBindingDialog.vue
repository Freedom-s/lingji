<script lang="ts" setup>
import { Connection, Delete, VideoPlay } from "@element-plus/icons-vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { computed, reactive, ref, watch } from "vue"
import { request } from "@/http/axios"

interface VideoDocument {
  id: string
  name: string
}

interface MindmapNode {
  id: string
  label: string
  children: MindmapNode[]
}

interface CoursewareOption {
  id: string
  name: string
  type?: string
  root: MindmapNode
}

interface VideoBinding {
  video_doc_id: string
  video_name: string
  kb_id: string
  courseware_doc_id: string
  courseware_name: string
  knowledge_point_id: string
  knowledge_point_name: string
  sort_order: number
}

const props = defineProps<{
  modelValue: boolean
  video: VideoDocument | null
  kbId: string
}>()

const emit = defineEmits<{
  "update:modelValue": [value: boolean]
  "saved": []
}>()

const visible = computed({
  get: () => props.modelValue,
  set: value => emit("update:modelValue", value)
})
const loading = ref(false)
const saving = ref(false)
const unbinding = ref(false)
const coursewares = ref<CoursewareOption[]>([])
const currentBinding = ref<VideoBinding | null>(null)
const form = reactive({
  courseware_doc_id: "",
  knowledge_point_id: ""
})

const selectedCourseware = computed(() => (
  coursewares.value.find(item => item.id === form.courseware_doc_id) || null
))

const treeData = computed(() => (
  selectedCourseware.value?.root ? [selectedCourseware.value.root] : []
))

function handleCoursewareChange() {
  form.knowledge_point_id = ""
}

async function loadDialogData() {
  if (!props.video?.id || !props.kbId) return
  loading.value = true
  try {
    const [optionsResponse, bindingResponse] = await Promise.all([
      request<{ code: number, data: { coursewares: CoursewareOption[] } }>({
        url: `/api/v1/knowledgebases/${props.kbId}/video-binding-options`,
        method: "get",
        hideMessage: true
      }),
      request<{ code: number, data: VideoBinding | null }>({
        url: `/api/v1/knowledgebases/documents/${props.video.id}/knowledge-point-binding`,
        method: "get",
        hideMessage: true
      })
    ])
    coursewares.value = optionsResponse.data?.coursewares || []
    currentBinding.value = bindingResponse.data || null
    form.courseware_doc_id = currentBinding.value?.courseware_doc_id || ""
    form.knowledge_point_id = currentBinding.value?.knowledge_point_id || ""
  } catch (error: any) {
    ElMessage.error(`加载挂载信息失败：${error?.message || "未知错误"}`)
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.modelValue, props.video?.id] as const,
  ([open]) => {
    if (open) void loadDialogData()
  }
)

async function saveBinding() {
  if (!props.video?.id) return
  if (!form.courseware_doc_id || !form.knowledge_point_id) {
    ElMessage.warning("请选择课件和知识点")
    return
  }
  saving.value = true
  try {
    const response = await request<{ code: number, data: VideoBinding }>({
      url: `/api/v1/knowledgebases/documents/${props.video.id}/knowledge-point-binding`,
      method: "put",
      data: { ...form },
      hideMessage: true
    })
    currentBinding.value = response.data
    ElMessage.success("挂载成功，视频原有观看记录已保留")
    emit("saved")
    visible.value = false
  } catch (error: any) {
    ElMessage.error(`挂载失败：${error?.message || "未知错误"}`)
  } finally {
    saving.value = false
  }
}

async function removeBinding() {
  if (!props.video?.id || !currentBinding.value) return
  try {
    await ElMessageBox.confirm(
      "解除后，视频会回到未归类状态；视频文件和所有学生观看记录都会保留。",
      "解除知识点挂载",
      { type: "warning", confirmButtonText: "解除挂载", cancelButtonText: "取消" }
    )
  } catch {
    return
  }

  unbinding.value = true
  try {
    await request({
      url: `/api/v1/knowledgebases/documents/${props.video.id}/knowledge-point-binding`,
      method: "delete",
      hideMessage: true
    })
    currentBinding.value = null
    form.courseware_doc_id = ""
    form.knowledge_point_id = ""
    ElMessage.success("已解除挂载，视频和观看记录均已保留")
    emit("saved")
  } catch (error: any) {
    ElMessage.error(`解除失败：${error?.message || "未知错误"}`)
  } finally {
    unbinding.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    width="640px"
    append-to-body
    destroy-on-close
    class="video-binding-dialog"
  >
    <template #header>
      <div class="dialog-heading">
        <span class="heading-icon"><el-icon><Connection /></el-icon></span>
        <div>
          <div class="heading-title">
            挂载到知识点
          </div>
          <div class="heading-subtitle">
            将已有视频放到课件的知识结构中
          </div>
        </div>
      </div>
    </template>

    <div v-loading="loading" class="binding-body">
      <div class="video-card">
        <span class="video-icon"><el-icon><VideoPlay /></el-icon></span>
        <div class="video-meta">
          <span class="eyebrow">当前视频</span>
          <strong>{{ video?.name }}</strong>
        </div>
        <el-tag v-if="currentBinding" type="success" effect="light">
          已挂载
        </el-tag>
        <el-tag v-else type="info" effect="plain">
          未归类
        </el-tag>
      </div>

      <el-alert
        v-if="currentBinding"
        :title="`当前位置：${currentBinding.courseware_name} / ${currentBinding.knowledge_point_name}`"
        description="修改下方选择即可改挂。视频 ID、学生观看时长和完成状态不会改变。"
        type="success"
        show-icon
        :closable="false"
      />

      <el-empty v-if="!loading && coursewares.length === 0" description="当前知识库还没有可挂载的思维导图">
        <span class="empty-tip">请先解析课件并生成或创建思维导图</span>
      </el-empty>

      <el-form v-else label-position="top" class="binding-form">
        <el-form-item label="目标课件" required>
          <el-select
            v-model="form.courseware_doc_id"
            filterable
            placeholder="选择同一知识库中的课件"
            style="width: 100%"
            @change="handleCoursewareChange"
          >
            <el-option
              v-for="courseware in coursewares"
              :key="courseware.id"
              :label="courseware.name"
              :value="courseware.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="思维导图知识点" required>
          <el-tree-select
            v-model="form.knowledge_point_id"
            :data="treeData"
            :props="{ value: 'id', label: 'label', children: 'children' }"
            :disabled="!form.courseware_doc_id"
            placeholder="选择视频所属的知识点"
            filterable
            check-strictly
            default-expand-all
            style="width: 100%"
          />
          <div class="form-hint">
            允许选择根节点，用于课程导学或总览视频。
          </div>
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button
          v-if="currentBinding"
          type="danger"
          plain
          :icon="Delete"
          :loading="unbinding"
          @click="removeBinding"
        >
          解除挂载
        </el-button>
        <span class="footer-spacer" />
        <el-button @click="visible = false">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="saving"
          :disabled="coursewares.length === 0"
          @click="saveBinding"
        >
          {{ currentBinding ? "保存调整" : "确认挂载" }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
.dialog-heading {
  display: flex;
  gap: 12px;
  align-items: center;
}

.heading-icon,
.video-icon {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  border: 1px solid var(--el-color-primary-light-7);
  border-radius: 12px;
}

.heading-icon {
  width: 40px;
  height: 40px;
  font-size: 20px;
}

.heading-title {
  color: var(--el-text-color-primary);
  font-size: 17px;
  font-weight: 700;
}

.heading-subtitle {
  margin-top: 2px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.binding-body {
  min-height: 300px;
}

.video-card {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 14px;
  margin-bottom: 16px;
  background: linear-gradient(135deg, var(--el-fill-color-light), var(--el-bg-color));
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 14px;
}

.video-icon {
  width: 42px;
  height: 42px;
  font-size: 22px;
}

.video-meta {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
}

.video-meta strong {
  overflow: hidden;
  color: var(--el-text-color-primary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.eyebrow {
  margin-bottom: 3px;
  color: var(--el-text-color-secondary);
  font-size: 11px;
  letter-spacing: 0.08em;
}

.binding-form {
  padding: 22px 4px 0;
}

.form-hint,
.empty-tip {
  margin-top: 7px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.dialog-footer {
  display: flex;
  align-items: center;
  width: 100%;
}

.footer-spacer {
  flex: 1;
}
</style>
