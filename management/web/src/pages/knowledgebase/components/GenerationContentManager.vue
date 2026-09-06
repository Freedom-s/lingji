<script lang="ts" setup>
import {
  CirclePlus,
  Delete,
  Edit,
  Refresh,
  VideoPlay,
} from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { computed, reactive, ref, watch } from "vue";
import { request } from "@/http/axios";

type GenerationType = "mindmap" | "flashcards" | "quiz";
type EditOperation = "add" | "edit" | "delete" | "replace";

interface DocumentInfo {
  id: string;
  name: string;
  type?: string;
}

interface MindMapNode {
  id: string;
  label: string;
  children: MindMapNode[];
}

interface MindMapContent {
  title: string;
  root: MindMapNode;
}

interface Flashcard {
  id: number;
  knowledge_point_ids: string[];
  question: string;
  answer: string;
}

interface QuizQuestion {
  id: number;
  knowledge_point_ids: string[];
  question: string;
  options: Record<"A" | "B" | "C" | "D", string>;
  correct: "A" | "B" | "C" | "D";
  explanations: Record<"A" | "B" | "C" | "D", string>;
}

interface SaveResponse {
  code: number;
  message: string;
  data: {
    generation_type: GenerationType;
    content: MindMapContent | Flashcard[] | QuizQuestion[];
    reset_records: number;
  };
}

interface BindingVideo {
  video_doc_id: string;
  video_name: string;
  courseware_doc_id: string | null;
  courseware_name: string | null;
  knowledge_point_id: string | null;
  knowledge_point_name: string | null;
  sort_order: number;
}

const props = defineProps<{
  modelValue: boolean;
  document: DocumentInfo | null;
  kbId: string;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  saved: [];
}>();

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit("update:modelValue", value),
});

const loading = ref(false);
const savingType = ref<GenerationType | "">("");
const activeTab = ref<GenerationType>("mindmap");
const mindmap = ref<MindMapContent | null>(null);
const mindmapTitle = ref("");
const flashcards = ref<Flashcard[]>([]);
const quizQuestions = ref<QuizQuestion[]>([]);
const bindingVideos = ref<BindingVideo[]>([]);
const videoManagerVisible = ref(false);
const videoManagerNode = ref<MindMapNode | null>(null);
const selectedUnboundVideoId = ref("");
const videoActionLoading = ref(false);

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value));
}

function flattenMindmap(
  node: MindMapNode | undefined,
  depth = 0,
): Array<MindMapNode & { depth: number }> {
  if (!node) return [];
  return [
    { ...node, depth },
    ...(node.children || []).flatMap((child) =>
      flattenMindmap(child, depth + 1),
    ),
  ];
}

const knowledgePointOptions = computed(() =>
  flattenMindmap(mindmap.value?.root),
);
const knowledgePointLabels = computed(() =>
  Object.fromEntries(
    knowledgePointOptions.value.map((node) => [node.id, node.label]),
  ),
);
const unboundVideos = computed(() =>
  bindingVideos.value.filter((video) => !video.courseware_doc_id),
);

function videosForNode(nodeId: string) {
  return bindingVideos.value
    .filter(
      (video) =>
        video.courseware_doc_id === props.document?.id &&
        video.knowledge_point_id === nodeId,
    )
    .sort((left, right) => left.sort_order - right.sort_order);
}

async function loadVideoBindings() {
  if (!props.kbId) {
    bindingVideos.value = [];
    return;
  }
  const response = await request<{
    code: number;
    data: { videos: BindingVideo[] };
  }>({
    url: `/api/v1/knowledgebases/${props.kbId}/video-bindings`,
    method: "get",
    hideMessage: true,
  });
  bindingVideos.value = response.data?.videos || [];
}

function findNode(root: MindMapNode, nodeId: string): MindMapNode | null {
  if (root.id === nodeId) return root;
  for (const child of root.children || []) {
    const found = findNode(child, nodeId);
    if (found) return found;
  }
  return null;
}

function removeNode(root: MindMapNode, nodeId: string): boolean {
  const index = (root.children || []).findIndex((child) => child.id === nodeId);
  if (index >= 0) {
    root.children.splice(index, 1);
    return true;
  }
  return (root.children || []).some((child) => removeNode(child, nodeId));
}

function createItemId(prefix: string) {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

function nextNumericId(items: Array<{ id: number }>) {
  return (
    items.reduce(
      (maximum, item) => Math.max(maximum, Number(item.id) || 0),
      -1,
    ) + 1
  );
}

function normalizeLoadedItems<
  T extends { id: number; knowledge_point_ids: string[] },
>(items: T[], validNodeIds: Set<string> | null): T[] {
  const usedIds = new Set<number>();
  let nextId = 0;
  return items.map((item) => {
    const candidate = Number(item.id);
    let id =
      Number.isInteger(candidate) && candidate >= 0 && !usedIds.has(candidate)
        ? candidate
        : nextId;
    while (usedIds.has(id)) id += 1;
    usedIds.add(id);
    nextId = Math.max(nextId, id + 1);

    const knowledgePointIds = Array.isArray(item.knowledge_point_ids)
      ? item.knowledge_point_ids.map(String)
      : [];
    return {
      ...item,
      id,
      knowledge_point_ids: validNodeIds
        ? knowledgePointIds.filter((nodeId) => validNodeIds.has(nodeId))
        : knowledgePointIds,
    };
  });
}

async function loadData() {
  if (!props.document?.id) return;
  loading.value = true;
  try {
    const docId = props.document.id;
    const [mindmapResponse, flashcardsResponse, quizResponse] =
      await Promise.all([
        request<any>({
          url: `/api/v1/knowledgebases/documents/${docId}/mindmap`,
          method: "get",
          hideMessage: true,
        }),
        request<any>({
          url: `/api/v1/knowledgebases/documents/${docId}/flashcards`,
          method: "get",
          hideMessage: true,
        }),
        request<any>({
          url: `/api/v1/knowledgebases/documents/${docId}/quiz`,
          method: "get",
          hideMessage: true,
        }),
      ]);
    mindmap.value = mindmapResponse.data?.content || null;
    mindmapTitle.value = mindmap.value?.title || "";
    const validNodeIds = mindmap.value
      ? new Set(flattenMindmap(mindmap.value.root).map((node) => node.id))
      : null;
    flashcards.value = normalizeLoadedItems(
      flashcardsResponse.data?.cards || [],
      validNodeIds,
    );
    quizQuestions.value = normalizeLoadedItems(
      quizResponse.data?.questions || [],
      validNodeIds,
    );
    await loadVideoBindings();
  } catch (error: any) {
    ElMessage.error(`加载学习内容失败：${error?.message || "未知错误"}`);
  } finally {
    loading.value = false;
  }
}

function openNodeVideoManager(node: MindMapNode) {
  videoManagerNode.value = node;
  selectedUnboundVideoId.value = "";
  videoManagerVisible.value = true;
}

async function attachVideoToNode() {
  if (
    !props.document?.id ||
    !videoManagerNode.value ||
    !selectedUnboundVideoId.value
  ) {
    ElMessage.warning("请选择要挂载的视频");
    return;
  }
  videoActionLoading.value = true;
  try {
    await request({
      url: `/api/v1/knowledgebases/documents/${selectedUnboundVideoId.value}/knowledge-point-binding`,
      method: "put",
      data: {
        courseware_doc_id: props.document.id,
        knowledge_point_id: videoManagerNode.value.id,
      },
      hideMessage: true,
    });
    selectedUnboundVideoId.value = "";
    await loadVideoBindings();
    emit("saved");
    ElMessage.success("视频已挂载，原有观看记录保持不变");
  } catch (error: any) {
    ElMessage.error(`挂载失败：${error?.message || "未知错误"}`);
  } finally {
    videoActionLoading.value = false;
  }
}

async function unbindNodeVideo(video: BindingVideo) {
  videoActionLoading.value = true;
  try {
    await request({
      url: `/api/v1/knowledgebases/documents/${video.video_doc_id}/knowledge-point-binding`,
      method: "delete",
      hideMessage: true,
    });
    await loadVideoBindings();
    emit("saved");
    ElMessage.success("已解除挂载，视频和学习记录均已保留");
  } catch (error: any) {
    ElMessage.error(`解除失败：${error?.message || "未知错误"}`);
  } finally {
    videoActionLoading.value = false;
  }
}

async function moveNodeVideo(index: number, direction: -1 | 1) {
  if (!props.document?.id || !videoManagerNode.value) return;
  const videos = videosForNode(videoManagerNode.value.id);
  const targetIndex = index + direction;
  if (targetIndex < 0 || targetIndex >= videos.length) return;
  const ordered = [...videos];
  const currentVideo = ordered[index];
  ordered[index] = ordered[targetIndex];
  ordered[targetIndex] = currentVideo;
  videoActionLoading.value = true;
  try {
    await request({
      url: `/api/v1/knowledgebases/documents/${props.document.id}/knowledge-point-videos/order`,
      method: "put",
      data: {
        knowledge_point_id: videoManagerNode.value.id,
        video_doc_ids: ordered.map((video) => video.video_doc_id),
      },
      hideMessage: true,
    });
    await loadVideoBindings();
  } catch (error: any) {
    ElMessage.error(`调整顺序失败：${error?.message || "未知错误"}`);
  } finally {
    videoActionLoading.value = false;
  }
}

watch(
  () => [props.modelValue, props.document?.id] as const,
  ([open]) => {
    if (open) void loadData();
  },
);

async function saveGeneration(
  generationType: GenerationType,
  content: MindMapContent | Flashcard[] | QuizQuestion[],
  operation: EditOperation,
  itemIndex?: number,
) {
  if (!props.document?.id) return false;
  savingType.value = generationType;
  try {
    const response = await request<SaveResponse>({
      url: `/api/v1/knowledgebases/documents/${props.document.id}/generation/${generationType}`,
      method: "put",
      data: {
        content,
        operation,
        item_index: itemIndex,
      },
      hideMessage: true,
    });
    if (generationType === "mindmap") {
      mindmap.value = response.data.content as MindMapContent;
      mindmapTitle.value = mindmap.value.title;
    } else if (generationType === "flashcards") {
      flashcards.value = response.data.content as Flashcard[];
    } else {
      quizQuestions.value = response.data.content as QuizQuestion[];
    }
    ElMessage.success(
      response.data.reset_records > 0
        ? `保存成功，已清理 ${response.data.reset_records} 条失效学习记录`
        : "保存成功",
    );
    emit("saved");
    return true;
  } catch (error: any) {
    ElMessage.error(`保存失败：${error?.message || "未知错误"}`);
    return false;
  } finally {
    savingType.value = "";
  }
}

async function createMindmap() {
  const content: MindMapContent = {
    title: "新思维导图",
    root: { id: "root", label: "核心主题", children: [] },
  };
  await saveGeneration("mindmap", content, "add");
}

async function saveMindmapTitle() {
  if (!mindmap.value) return;
  const title = mindmapTitle.value.trim();
  if (!title) return ElMessage.warning("请输入思维导图标题");
  const content = clone(mindmap.value);
  content.title = title;
  await saveGeneration("mindmap", content, "edit");
}

const mindmapDialogVisible = ref(false);
const mindmapEditMode = ref<"add" | "edit">("add");
const mindmapTargetId = ref("");
const mindmapNodeForm = reactive({ label: "" });

function openAddMindmapNode(parent: MindMapNode) {
  mindmapEditMode.value = "add";
  mindmapTargetId.value = parent.id;
  mindmapNodeForm.label = "";
  mindmapDialogVisible.value = true;
}

function openEditMindmapNode(node: MindMapNode) {
  mindmapEditMode.value = "edit";
  mindmapTargetId.value = node.id;
  mindmapNodeForm.label = node.label;
  mindmapDialogVisible.value = true;
}

async function submitMindmapNode() {
  const label = mindmapNodeForm.label.trim();
  if (!label) return ElMessage.warning("请输入知识点名称");
  if (!mindmap.value) return;
  const content = clone(mindmap.value);
  const target = findNode(content.root, mindmapTargetId.value);
  if (!target) return ElMessage.error("目标知识点不存在，请刷新后重试");

  if (mindmapEditMode.value === "add") {
    target.children ||= [];
    target.children.push({ id: createItemId("kp"), label, children: [] });
  } else {
    target.label = label;
  }
  const saved = await saveGeneration("mindmap", content, mindmapEditMode.value);
  if (saved) mindmapDialogVisible.value = false;
}

async function deleteMindmapNode(node: MindMapNode) {
  if (!mindmap.value || node.id === mindmap.value.root.id) return;
  try {
    await ElMessageBox.confirm(
      `删除“${node.label}”会同时删除它的所有子知识点，并解除闪卡、测验中的相关引用。确定继续吗？`,
      "删除知识点",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  const content = clone(mindmap.value);
  if (removeNode(content.root, node.id)) {
    await saveGeneration("mindmap", content, "delete");
  }
}

const flashcardDialogVisible = ref(false);
const flashcardEditIndex = ref(-1);
const flashcardForm = reactive({
  question: "",
  answer: "",
  knowledge_point_ids: [] as string[],
});

function openFlashcardEditor(index = -1) {
  flashcardEditIndex.value = index;
  const item = index >= 0 ? flashcards.value[index] : null;
  Object.assign(flashcardForm, {
    question: item?.question || "",
    answer: item?.answer || "",
    knowledge_point_ids: [...(item?.knowledge_point_ids || [])],
  });
  flashcardDialogVisible.value = true;
}

async function submitFlashcard() {
  const question = flashcardForm.question.trim();
  const answer = flashcardForm.answer.trim();
  if (!question || !answer) return ElMessage.warning("问题和答案不能为空");
  const content = clone(flashcards.value);
  const index = flashcardEditIndex.value;
  const item: Flashcard = {
    id: index >= 0 ? content[index].id : nextNumericId(content),
    question,
    answer,
    knowledge_point_ids: [...flashcardForm.knowledge_point_ids],
  };
  if (index >= 0) content[index] = item;
  else content.push(item);
  const saved = await saveGeneration(
    "flashcards",
    content,
    index >= 0 ? "edit" : "add",
    index >= 0 ? index : undefined,
  );
  if (saved) flashcardDialogVisible.value = false;
}

async function deleteFlashcard(index: number) {
  try {
    await ElMessageBox.confirm(
      "删除后，该卡片已有的学生记忆状态也会被清理。确定继续吗？",
      "删除概念速记",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }
  const content = clone(flashcards.value);
  content.splice(index, 1);
  await saveGeneration("flashcards", content, "delete", index);
}

const quizDialogVisible = ref(false);
const quizEditIndex = ref(-1);
const optionKeys = ["A", "B", "C", "D"] as const;
const createEmptyOptions = () => ({ A: "", B: "", C: "", D: "" });
const quizForm = reactive({
  question: "",
  options: createEmptyOptions(),
  correct: "A" as QuizQuestion["correct"],
  explanations: createEmptyOptions(),
  knowledge_point_ids: [] as string[],
});

function openQuizEditor(index = -1) {
  quizEditIndex.value = index;
  const item = index >= 0 ? quizQuestions.value[index] : null;
  quizForm.question = item?.question || "";
  quizForm.options = { ...(item?.options || createEmptyOptions()) };
  quizForm.correct = item?.correct || "A";
  quizForm.explanations = { ...(item?.explanations || createEmptyOptions()) };
  quizForm.knowledge_point_ids = [...(item?.knowledge_point_ids || [])];
  quizDialogVisible.value = true;
}

async function submitQuizQuestion() {
  const question = quizForm.question.trim();
  if (!question) return ElMessage.warning("题干不能为空");
  if (optionKeys.some((key) => !quizForm.options[key].trim())) {
    return ElMessage.warning("请填写完整的 A、B、C、D 四个选项");
  }
  const content = clone(quizQuestions.value);
  const index = quizEditIndex.value;
  const item: QuizQuestion = {
    id: index >= 0 ? content[index].id : nextNumericId(content),
    question,
    options: clone(quizForm.options),
    correct: quizForm.correct,
    explanations: clone(quizForm.explanations),
    knowledge_point_ids: [...quizForm.knowledge_point_ids],
  };
  if (index >= 0) content[index] = item;
  else content.push(item);
  const saved = await saveGeneration(
    "quiz",
    content,
    index >= 0 ? "edit" : "add",
    index >= 0 ? index : undefined,
  );
  if (saved) quizDialogVisible.value = false;
}

async function deleteQuizQuestion(index: number) {
  try {
    await ElMessageBox.confirm(
      "删除后，该题已有的学生作答结果将被清理，并重新计算相关知识点记录。确定继续吗？",
      "删除测验题",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }
  const content = clone(quizQuestions.value);
  content.splice(index, 1);
  await saveGeneration("quiz", content, "delete", index);
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="`学习内容管理 · ${document?.name || ''}`"
    width="min(1120px, 94vw)"
    top="4vh"
    append-to-body
    destroy-on-close
    class="generation-manager-dialog"
  >
    <el-alert
      title="这里的内容会直接展示给学生"
      description="老师可以审核并修改 AI 生成结果。编辑或删除已有闪卡、题目时，系统会清理对应的旧学习记录，避免成绩引用已变化的内容。"
      type="warning"
      show-icon
      :closable="false"
      class="review-alert"
    />

    <div v-loading="loading" class="manager-body">
      <el-tabs v-model="activeTab" class="content-tabs">
        <el-tab-pane name="mindmap">
          <template #label>
            <span
              >思维导图
              <el-tag size="small" type="info">{{
                knowledgePointOptions.length
              }}</el-tag></span
            >
          </template>
          <div v-if="mindmap" class="tab-panel">
            <div class="panel-toolbar">
              <el-input
                v-model="mindmapTitle"
                maxlength="200"
                placeholder="思维导图标题"
              />
              <el-button
                type="primary"
                plain
                :loading="savingType === 'mindmap'"
                @click="saveMindmapTitle"
              >
                保存标题
              </el-button>
              <el-button
                type="primary"
                :icon="CirclePlus"
                @click="openAddMindmapNode(mindmap.root)"
              >
                添加一级知识点
              </el-button>
            </div>
            <el-tree
              :data="[mindmap.root]"
              node-key="id"
              default-expand-all
              :expand-on-click-node="false"
              class="mindmap-tree"
            >
              <template #default="{ data }">
                <div class="tree-node-row">
                  <div class="node-main">
                    <span class="node-label">{{ data.label }}</span>
                    <code>{{ data.id }}</code>
                  </div>
                  <div class="node-actions">
                    <el-button
                      text
                      type="success"
                      size="small"
                      :icon="VideoPlay"
                      @click.stop="openNodeVideoManager(data)"
                    >
                      视频 {{ videosForNode(data.id).length || "" }}
                    </el-button>
                    <el-button
                      text
                      type="primary"
                      size="small"
                      :icon="CirclePlus"
                      @click.stop="openAddMindmapNode(data)"
                    >
                      添加子节点
                    </el-button>
                    <el-button
                      text
                      size="small"
                      :icon="Edit"
                      @click.stop="openEditMindmapNode(data)"
                    >
                      编辑
                    </el-button>
                    <el-button
                      v-if="data.id !== mindmap.root.id"
                      text
                      type="danger"
                      size="small"
                      :icon="Delete"
                      @click.stop="deleteMindmapNode(data)"
                    >
                      删除
                    </el-button>
                  </div>
                </div>
              </template>
            </el-tree>
          </div>
          <el-empty v-else description="尚未生成思维导图">
            <el-button
              type="primary"
              :loading="savingType === 'mindmap'"
              @click="createMindmap"
            >
              手动创建
            </el-button>
          </el-empty>
        </el-tab-pane>

        <el-tab-pane name="flashcards">
          <template #label>
            <span
              >概念速记
              <el-tag size="small" type="info">{{
                flashcards.length
              }}</el-tag></span
            >
          </template>
          <div class="tab-panel">
            <div class="panel-toolbar end-aligned">
              <el-button :icon="Refresh" :loading="loading" @click="loadData">
                刷新
              </el-button>
              <el-button
                type="primary"
                :icon="CirclePlus"
                @click="openFlashcardEditor()"
              >
                新增卡片
              </el-button>
            </div>
            <el-table
              :data="flashcards"
              stripe
              max-height="520"
              empty-text="暂无概念速记，可点击右上角新增"
            >
              <el-table-column type="index" label="#" width="55" />
              <el-table-column
                prop="question"
                label="问题"
                min-width="220"
                show-overflow-tooltip
              />
              <el-table-column
                prop="answer"
                label="答案"
                min-width="260"
                show-overflow-tooltip
              />
              <el-table-column label="关联知识点" min-width="190">
                <template #default="scope">
                  <div class="tag-list">
                    <el-tag
                      v-for="nodeId in scope.row.knowledge_point_ids"
                      :key="nodeId"
                      size="small"
                      effect="plain"
                    >
                      {{ knowledgePointLabels[nodeId] || nodeId }}
                    </el-tag>
                    <span
                      v-if="!scope.row.knowledge_point_ids?.length"
                      class="muted-text"
                      >未关联</span
                    >
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150" fixed="right">
                <template #default="scope">
                  <el-button
                    text
                    type="primary"
                    :icon="Edit"
                    @click="openFlashcardEditor(scope.$index)"
                  >
                    编辑
                  </el-button>
                  <el-button
                    text
                    type="danger"
                    :icon="Delete"
                    @click="deleteFlashcard(scope.$index)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <el-tab-pane name="quiz">
          <template #label>
            <span
              >随堂测验
              <el-tag size="small" type="info">{{
                quizQuestions.length
              }}</el-tag></span
            >
          </template>
          <div class="tab-panel">
            <div class="panel-toolbar end-aligned">
              <el-button :icon="Refresh" :loading="loading" @click="loadData">
                刷新
              </el-button>
              <el-button
                type="primary"
                :icon="CirclePlus"
                @click="openQuizEditor()"
              >
                新增题目
              </el-button>
            </div>
            <el-table
              :data="quizQuestions"
              stripe
              max-height="520"
              empty-text="暂无测验题，可点击右上角新增"
            >
              <el-table-column type="index" label="#" width="55" />
              <el-table-column
                prop="question"
                label="题干"
                min-width="300"
                show-overflow-tooltip
              />
              <el-table-column
                prop="correct"
                label="答案"
                width="80"
                align="center"
              >
                <template #default="scope">
                  <el-tag type="success">
                    {{ scope.row.correct }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="关联知识点" min-width="190">
                <template #default="scope">
                  <div class="tag-list">
                    <el-tag
                      v-for="nodeId in scope.row.knowledge_point_ids"
                      :key="nodeId"
                      size="small"
                      effect="plain"
                    >
                      {{ knowledgePointLabels[nodeId] || nodeId }}
                    </el-tag>
                    <span
                      v-if="!scope.row.knowledge_point_ids?.length"
                      class="muted-text"
                      >未关联</span
                    >
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150" fixed="right">
                <template #default="scope">
                  <el-button
                    text
                    type="primary"
                    :icon="Edit"
                    @click="openQuizEditor(scope.$index)"
                  >
                    编辑
                  </el-button>
                  <el-button
                    text
                    type="danger"
                    :icon="Delete"
                    @click="deleteQuizQuestion(scope.$index)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <template #footer>
      <el-button @click="visible = false"> 关闭 </el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="videoManagerVisible"
    :title="`知识点视频 · ${videoManagerNode?.label || ''}`"
    width="620px"
    append-to-body
  >
    <el-alert
      title="直接挂载已有视频"
      description="不会重新上传，也不会改变视频 ID、观看进度、周任务或评分记录。"
      type="success"
      show-icon
      :closable="false"
      class="video-manager-alert"
    />
    <div v-loading="videoActionLoading" class="video-manager-body">
      <div class="video-add-row">
        <el-select
          v-model="selectedUnboundVideoId"
          filterable
          clearable
          placeholder="从未归类视频中选择"
        >
          <el-option
            v-for="video in unboundVideos"
            :key="video.video_doc_id"
            :label="video.video_name"
            :value="video.video_doc_id"
          />
        </el-select>
        <el-button
          type="primary"
          :disabled="!selectedUnboundVideoId"
          @click="attachVideoToNode"
        >
          挂载到此知识点
        </el-button>
      </div>
      <div
        v-if="videoManagerNode && videosForNode(videoManagerNode.id).length"
        class="node-video-list"
      >
        <div
          v-for="(video, index) in videosForNode(videoManagerNode.id)"
          :key="video.video_doc_id"
          class="node-video-item"
        >
          <span class="video-order">{{ index + 1 }}</span>
          <span class="video-name">{{ video.video_name }}</span>
          <el-button-group>
            <el-button
              size="small"
              :disabled="index === 0"
              @click="moveNodeVideo(index, -1)"
            >
              上移
            </el-button>
            <el-button
              size="small"
              :disabled="
                index === videosForNode(videoManagerNode.id).length - 1
              "
              @click="moveNodeVideo(index, 1)"
            >
              下移
            </el-button>
          </el-button-group>
          <el-button
            text
            type="danger"
            size="small"
            @click="unbindNodeVideo(video)"
          >
            解除
          </el-button>
        </div>
      </div>
      <el-empty v-else description="此知识点还没有视频" :image-size="72" />
      <p v-if="unboundVideos.length === 0" class="video-manager-tip">
        当前没有未归类视频；如需调整位置，请先在原知识点解除挂载，再重新选择目标知识点。
      </p>
    </div>
    <template #footer>
      <el-button @click="videoManagerVisible = false"> 完成 </el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="mindmapDialogVisible"
    :title="mindmapEditMode === 'add' ? '添加知识点' : '编辑知识点'"
    width="460px"
    append-to-body
  >
    <el-form label-position="top">
      <el-form-item label="知识点名称" required>
        <el-input
          v-model="mindmapNodeForm.label"
          maxlength="200"
          show-word-limit
          @keyup.enter="submitMindmapNode"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="mindmapDialogVisible = false"> 取消 </el-button>
      <el-button
        type="primary"
        :loading="savingType === 'mindmap'"
        @click="submitMindmapNode"
      >
        保存
      </el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="flashcardDialogVisible"
    :title="flashcardEditIndex >= 0 ? '编辑概念速记' : '新增概念速记'"
    width="620px"
    append-to-body
  >
    <el-form label-position="top">
      <el-form-item label="问题" required>
        <el-input v-model="flashcardForm.question" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="答案" required>
        <el-input v-model="flashcardForm.answer" type="textarea" :rows="4" />
      </el-form-item>
      <el-form-item label="关联知识点">
        <el-select
          v-model="flashcardForm.knowledge_point_ids"
          multiple
          filterable
          clearable
          placeholder="可选择一个或多个知识点"
          style="width: 100%"
        >
          <el-option
            v-for="node in knowledgePointOptions"
            :key="node.id"
            :label="`${node.label}（${node.id}）`"
            :value="node.id"
          />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="flashcardDialogVisible = false"> 取消 </el-button>
      <el-button
        type="primary"
        :loading="savingType === 'flashcards'"
        @click="submitFlashcard"
      >
        保存
      </el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="quizDialogVisible"
    :title="quizEditIndex >= 0 ? '编辑测验题' : '新增测验题'"
    width="760px"
    append-to-body
  >
    <el-form label-position="top" class="quiz-form">
      <el-form-item label="题干" required>
        <el-input v-model="quizForm.question" type="textarea" :rows="3" />
      </el-form-item>
      <div v-for="key in optionKeys" :key="key" class="option-row">
        <div class="option-key">
          {{ key }}
        </div>
        <el-input
          v-model="quizForm.options[key]"
          :placeholder="`选项 ${key}`"
        />
        <el-input
          v-model="quizForm.explanations[key]"
          :placeholder="`选项 ${key} 的解析（可选）`"
        />
      </div>
      <div class="quiz-meta-row">
        <el-form-item label="正确答案" required>
          <el-select v-model="quizForm.correct" style="width: 140px">
            <el-option
              v-for="key in optionKeys"
              :key="key"
              :label="key"
              :value="key"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关联知识点" class="knowledge-select">
          <el-select
            v-model="quizForm.knowledge_point_ids"
            multiple
            filterable
            clearable
            placeholder="可选择一个或多个知识点"
            style="width: 100%"
          >
            <el-option
              v-for="node in knowledgePointOptions"
              :key="node.id"
              :label="`${node.label}（${node.id}）`"
              :value="node.id"
            />
          </el-select>
        </el-form-item>
      </div>
    </el-form>
    <template #footer>
      <el-button @click="quizDialogVisible = false"> 取消 </el-button>
      <el-button
        type="primary"
        :loading="savingType === 'quiz'"
        @click="submitQuizQuestion"
      >
        保存
      </el-button>
    </template>
  </el-dialog>
</template>

<style lang="scss" scoped>
.review-alert {
  margin-bottom: 16px;
}
.manager-body {
  min-height: 500px;
}
.content-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}
.content-tabs :deep(.el-tabs__item) {
  height: 44px;
}
.content-tabs :deep(.el-tag) {
  margin-left: 6px;
}
.tab-panel {
  min-height: 460px;
}
.panel-toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 14px;
}
.panel-toolbar .el-input {
  max-width: 520px;
}
.panel-toolbar.end-aligned {
  justify-content: flex-end;
}
.mindmap-tree {
  padding: 8px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
}
.mindmap-tree :deep(.el-tree-node__content) {
  height: 46px;
  border-radius: 7px;
}
.mindmap-tree :deep(.el-tree-node__content:hover) {
  background: var(--el-fill-color-light);
}
.tree-node-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-width: 0;
  padding-right: 8px;
}
.node-main {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 10px;
}
.node-label {
  overflow: hidden;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node-main code {
  padding: 2px 6px;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
  border-radius: 4px;
  font-size: 11px;
}
.node-actions {
  display: flex;
  flex-shrink: 0;
}
.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.tag-list :deep(.el-tag) {
  margin-left: 0;
}
.muted-text {
  color: var(--el-text-color-placeholder);
  font-size: 12px;
}
.option-row {
  display: grid;
  grid-template-columns: 34px 1fr 1fr;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}
.option-key {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  border-radius: 50%;
  font-weight: 700;
}
.quiz-meta-row {
  display: flex;
  gap: 18px;
  margin-top: 18px;
}
.knowledge-select {
  flex: 1;
}
.video-manager-alert {
  margin-bottom: 16px;
}
.video-manager-body {
  min-height: 220px;
}
.video-add-row {
  display: flex;
  gap: 10px;
  margin-bottom: 18px;
}
.video-add-row .el-select {
  flex: 1;
}
.node-video-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.node-video-item {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
}
.video-order {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  width: 26px;
  height: 26px;
  color: var(--el-color-success);
  background: var(--el-color-success-light-9);
  border-radius: 50%;
  font-weight: 700;
}
.video-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.video-manager-tip {
  margin: 14px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.6;
}

@media (max-width: 720px) {
  .panel-toolbar {
    flex-wrap: wrap;
  }
  .node-main code {
    display: none;
  }
  .node-actions .el-button {
    padding: 5px;
  }
  .option-row {
    grid-template-columns: 34px 1fr;
  }
  .option-row .el-input:last-child {
    grid-column: 2;
  }
  .quiz-meta-row {
    flex-direction: column;
    gap: 0;
  }
}
</style>
