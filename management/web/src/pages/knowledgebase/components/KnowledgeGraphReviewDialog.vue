<script lang="ts" setup>
import {
  generateKnowledgeGraphApi,
  getKnowledgeGraphApi,
  publishKnowledgeGraphApi,
} from "@@/apis/kbs/knowledgebase";
import { ElMessage, ElMessageBox } from "element-plus";
import { use } from "echarts/core";
import { GraphChart } from "echarts/charts";
import { LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import VChart from "vue-echarts";
import { computed, ref, watch } from "vue";

use([CanvasRenderer, GraphChart, TooltipComponent, LegendComponent]);

interface GraphNode {
  id: string;
  name: string;
  aliases?: string[];
  parent_id?: string | null;
  confidence?: number;
  source_refs?: Array<{ doc_id: string; source_node_ids?: string[] }>;
}

interface GraphEdge {
  source: string;
  target: string;
  relation: string;
  confidence?: number;
  evidence?: string;
}

interface GraphQuestion {
  doc_id: string;
  question_id: string;
  doc_name?: string;
  question?: string;
  node_ids: string[];
  confidence?: number;
  evidence?: string;
}

interface GraphContent {
  nodes: GraphNode[];
  edges: GraphEdge[];
  questions: GraphQuestion[];
}

interface GraphResponse {
  status: "empty" | "draft" | "published";
  version: number;
  draft: GraphContent | null;
  published: GraphContent | null;
  generated_at?: string | null;
  published_at?: string | null;
}

const props = defineProps<{
  modelValue: boolean;
  kbId: string;
  kbName?: string;
}>();

const emit = defineEmits<{ "update:modelValue": [value: boolean] }>();

const loading = ref(false);
const generating = ref(false);
const publishing = ref(false);
const graph = ref<GraphResponse>({
  status: "empty",
  version: 0,
  draft: null,
  published: null,
});
const activeTab = ref<"draft" | "published">("draft");
const selectedNodeId = ref("");

const currentContent = computed<GraphContent | null>(() => {
  if (activeTab.value === "published") return graph.value.published;
  return graph.value.draft || graph.value.published;
});

const nodeNameMap = computed(() => {
  const result = new Map<string, string>();
  for (const node of currentContent.value?.nodes || []) result.set(node.id, node.name);
  return result;
});

const selectedNode = computed(() => {
  return currentContent.value?.nodes.find((node) => node.id === selectedNodeId.value) || null;
});

const graphOption = computed(() => {
  const content = currentContent.value;
  if (!content) return {};

  const links = content.edges.map((edge) => ({
    source: edge.source,
    target: edge.target,
    value: relationLabel(edge.relation),
    relation: edge.relation,
    lineStyle: {
      color: edge.relation === "prerequisite" ? "#f5b85b" : "#7196b9",
      width: edge.relation === "prerequisite" ? 2.2 : 1.1,
      curveness: 0.12,
      opacity: edge.relation === "related_to" ? 0.28 : 0.72,
    },
  }));

  const degreeMap = new Map<string, number>();
  for (const link of links) {
    degreeMap.set(link.source, (degreeMap.get(link.source) || 0) + 1);
    degreeMap.set(link.target, (degreeMap.get(link.target) || 0) + 1);
  }
  const relationChildIds = new Set(
    links.filter((link) => link.relation === "part_of").map((link) => link.source),
  );
  const coreNodeIds = new Set(
    content.nodes
      .filter((node) => !node.parent_id && !relationChildIds.has(node.id))
      .map((node) => node.id),
  );
  content.nodes.forEach((node) => {
    if ((degreeMap.get(node.id) || 0) >= 3) coreNodeIds.add(node.id);
  });
  if (coreNodeIds.size > 48) {
    const reducedCore = new Set(
      content.nodes
        .filter(
          (node) =>
            (!node.parent_id && !relationChildIds.has(node.id)) ||
            (degreeMap.get(node.id) || 0) >= 5,
        )
        .map((node) => node.id),
    );
    coreNodeIds.clear();
    reducedCore.forEach((id) => coreNodeIds.add(id));
  }
  if (selectedNodeId.value) coreNodeIds.add(selectedNodeId.value);

  const nodeData = content.nodes.map((node) => {
    const confidence = Number(node.confidence) || 0;
    const sourceSize = Math.min(5, sourceCount(node));
    return {
      id: node.id,
      name: node.name,
      value: sourceSize,
      symbolSize: Math.max(26, Math.min(56, 28 + sourceSize * 5)),
      category: confidence >= 0.8 ? 0 : confidence >= 0.6 ? 1 : 2,
      itemStyle: {
        color: confidence >= 0.8 ? "#54d6c7" : confidence >= 0.6 ? "#f5b85b" : "#f07c73",
        borderColor: "#effffc",
        borderWidth: 2,
        shadowBlur: 18,
        shadowColor: "rgba(84, 214, 199, 0.35)",
      },
      label: {
        show: coreNodeIds.has(node.id),
        color: "#f4fbff",
        fontSize: 12,
        fontWeight: 600,
        position: "bottom",
        distance: 7,
        width: 108,
        overflow: "truncate",
        backgroundColor: "rgba(8, 26, 40, 0.78)",
        borderRadius: 4,
        padding: [4, 6],
      },
    };
  });

  return {
    animationDuration: 900,
    animationEasingUpdate: "quinticInOut" as const,
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(11, 28, 43, 0.96)",
      borderWidth: 0,
      textStyle: { color: "#f5fbff" },
      formatter: (params: any) => {
        if (params.dataType === "edge") {
          return `${params.data.value || "知识关系"}`;
        }
        const node = content.nodes.find((item) => item.id === params.data?.id);
        return node
          ? `${node.name}<br/>来源课件：${sourceCount(node)} 个<br/>置信度：${formatConfidence(node.confidence)}`
          : params.name;
      },
    },
    legend: {
      show: true,
      bottom: 12,
      textStyle: { color: "#a7bdd0", fontSize: 11 },
      data: ["高置信度", "待复核", "低置信度"],
    },
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        data: nodeData,
        links,
        categories: [
          { name: "高置信度", itemStyle: { color: "#54d6c7" } },
          { name: "待复核", itemStyle: { color: "#f5b85b" } },
          { name: "低置信度", itemStyle: { color: "#f07c73" } },
        ],
        force: {
          repulsion: Math.max(300, Math.min(920, content.nodes.length * 24)),
          edgeLength: [120, 220],
          gravity: 0.08,
          layoutAnimation: true,
        },
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: [0, 7],
        lineStyle: { color: "#7196b9", opacity: 0.7 },
        scaleLimit: { min: 0.35, max: 3.2 },
        emphasis: {
          focus: "adjacency",
          lineStyle: { width: 3 },
          label: {
            show: true,
            fontSize: 13,
            color: "#f4fbff",
            backgroundColor: "rgba(8, 26, 40, 0.9)",
          },
        },
      },
    ],
  };
});

function formatConfidence(value?: number) {
  return `${Math.round((Number(value) || 0) * 100)}%`;
}

function relationLabel(value: string) {
  return {
    prerequisite: "前置知识",
    part_of: "组成 / 隶属",
    related_to: "相关知识",
  }[value] || value;
}

function confidenceType(value?: number) {
  const confidence = Number(value) || 0;
  if (confidence >= 0.8) return "success";
  if (confidence >= 0.6) return "warning";
  return "danger";
}

function sourceCount(node: GraphNode) {
  return node.source_refs?.length || 0;
}

function handleGraphClick(params: any) {
  if (params?.dataType === "node" && params.data?.id) {
    selectedNodeId.value = String(params.data.id);
  }
}

async function loadGraph() {
  if (!props.kbId) return;
  loading.value = true;
  try {
    const response = (await getKnowledgeGraphApi(props.kbId)) as { data: GraphResponse };
    graph.value = response.data;
    activeTab.value = graph.value.draft ? "draft" : "published";
    selectedNodeId.value = graph.value.draft?.nodes[0]?.id || graph.value.published?.nodes[0]?.id || "";
  } catch (error: any) {
    ElMessage.error(`读取知识图谱失败：${error?.message || "未知错误"}`);
  } finally {
    loading.value = false;
  }
}

async function handleGenerate() {
  generating.value = true;
  try {
    const response = (await generateKnowledgeGraphApi(props.kbId)) as { data: GraphResponse };
    graph.value = response.data;
    activeTab.value = "draft";
    selectedNodeId.value = graph.value.draft?.nodes[0]?.id || "";
    ElMessage.success("知识图谱草稿已生成，请先检查后发布");
  } catch (error: any) {
    ElMessage.error(`生成失败：${error?.message || "请检查模型服务和课件生成内容"}`);
  } finally {
    generating.value = false;
  }
}

async function handlePublish() {
  if (!graph.value.draft) return;
  try {
    await ElMessageBox.confirm(
      "发布后，这份知识图谱会作为知识库的当前版本使用。确定发布吗？",
      "发布知识图谱",
      { type: "warning", confirmButtonText: "确认发布", cancelButtonText: "返回" },
    );
  } catch {
    return;
  }

  publishing.value = true;
  try {
    const response = (await publishKnowledgeGraphApi(props.kbId)) as { data: GraphResponse };
    graph.value = response.data;
    activeTab.value = "published";
    selectedNodeId.value = graph.value.published?.nodes[0]?.id || "";
    ElMessage.success("知识图谱已发布");
  } catch (error: any) {
    ElMessage.error(`发布失败：${error?.message || "未知错误"}`);
  } finally {
    publishing.value = false;
  }
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) void loadGraph();
  },
);
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="`知识图谱 · ${kbName || '知识库'}`"
    width="92%"
    top="5vh"
    append-to-body
    destroy-on-close
    @close="emit('update:modelValue', false)"
  >
    <div v-loading="loading" class="graph-dialog">
      <div class="graph-intro">
        <div>
          <div class="eyebrow">COURSE KNOWLEDGE MAP</div>
          <h3>把课件中的知识点串成可复习的路径</h3>
          <p>
            第一版只参考各课件已有的思维导图，由当前配置的大模型生成全局知识图谱；题目绑定将在下一阶段单独处理。
          </p>
        </div>
        <div class="graph-actions">
          <el-button type="primary" :loading="generating" @click="handleGenerate">
            {{ graph.draft ? "重新生成草稿" : "生成知识图谱" }}
          </el-button>
          <el-button
            type="success"
            :disabled="!graph.draft"
            :loading="publishing"
            @click="handlePublish"
          >
            发布当前草稿
          </el-button>
        </div>
      </div>

      <el-alert
        v-if="!currentContent"
        title="还没有知识图谱草稿"
        description="请先确保课件已经完成解析，并且已经生成课件思维导图。"
        type="info"
        :closable="false"
        show-icon
      />

      <template v-else>
        <div class="graph-stats">
          <div class="stat-card">
            <span>知识点</span>
            <strong>{{ currentContent.nodes.length }}</strong>
            <small>合并后的复习节点</small>
          </div>
          <div class="stat-card">
            <span>知识关系</span>
            <strong>{{ currentContent.edges.length }}</strong>
            <small>前置、组成与相关</small>
          </div>
          <div class="stat-card">
            <span>题目映射（后续）</span>
            <strong>{{ currentContent.questions.length }}</strong>
            <small>第一版暂不绑定题目</small>
          </div>
          <div class="stat-card stat-card--status">
            <span>版本状态</span>
            <el-tag :type="activeTab === 'published' ? 'success' : 'warning'">
              {{ activeTab === "published" ? `已发布 v${graph.version}` : "待审核草稿" }}
            </el-tag>
            <small v-if="graph.generated_at">生成于 {{ graph.generated_at }}</small>
          </div>
        </div>

        <el-tabs v-model="activeTab" class="graph-tabs">
          <el-tab-pane v-if="graph.draft" label="草稿预览" name="draft" />
          <el-tab-pane v-if="graph.published" label="当前已发布版本" name="published" />
        </el-tabs>

        <div class="section-heading">
          <div>
            <span class="section-kicker">01 / GRAPH</span>
            <h4>全局知识图谱</h4>
          </div>
          <span>默认突出显示知识主干，悬停或点击节点查看细节</span>
        </div>
        <div class="graph-workspace">
          <div class="graph-canvas">
            <VChart
              :option="graphOption"
              autoresize
              class="knowledge-graph-chart"
              @click="handleGraphClick"
            />
            <div class="graph-canvas-hint">节点大小代表来源覆盖度 · 滚轮缩放 · 拖拽平移</div>
          </div>
          <aside v-if="selectedNode" class="node-inspector">
            <span class="inspector-kicker">SELECTED NODE</span>
            <h4>{{ selectedNode.name }}</h4>
            <div class="inspector-meta">
              <el-tag size="small" :type="confidenceType(selectedNode.confidence)">
                置信度 {{ formatConfidence(selectedNode.confidence) }}
              </el-tag>
              <span>{{ sourceCount(selectedNode) }} 个来源课件</span>
            </div>
            <div v-if="selectedNode.aliases?.length" class="inspector-block">
              <span>常用别名</span>
              <p>{{ selectedNode.aliases.join("、") }}</p>
            </div>
            <div class="inspector-block">
              <span>来源节点</span>
              <p v-if="selectedNode.source_refs?.length">
                {{ selectedNode.source_refs.map((ref) => ref.doc_id).join("、") }}
              </p>
              <p v-else>暂无来源标记</p>
            </div>
            <div class="inspector-block">
              <span>节点 ID</span>
              <p class="mono">{{ selectedNode.id }}</p>
            </div>
          </aside>
          <aside v-else class="node-inspector node-inspector--empty">
            <span class="inspector-kicker">NODE INSPECTOR</span>
            <h4>点击图谱节点</h4>
            <p>选择一个知识点后，这里会显示它的来源课件、别名和置信度。</p>
          </aside>
        </div>

        <div class="split-grid">
          <section>
            <div class="section-heading section-heading--compact">
              <div>
                <span class="section-kicker">02 / EDGES</span>
                <h4>知识点关系</h4>
              </div>
            </div>
            <el-table :data="currentContent.edges" max-height="260" class="graph-table">
              <el-table-column label="关系" min-width="170">
                <template #default="scope">
                  <div class="relation-cell">
                    <span>{{ nodeNameMap.get(scope.row.source) || scope.row.source }}</span>
                    <span class="arrow">→</span>
                    <span>{{ nodeNameMap.get(scope.row.target) || scope.row.target }}</span>
                  </div>
                  <el-tag size="small" type="info">{{ relationLabel(scope.row.relation) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="置信度" width="92" align="center">
                <template #default="scope">{{ formatConfidence(scope.row.confidence) }}</template>
              </el-table-column>
            </el-table>
          </section>

          <section v-if="currentContent.questions.length">
            <div class="section-heading section-heading--compact">
              <div>
                <span class="section-kicker">03 / QUESTIONS</span>
                <h4>题目挂载</h4>
              </div>
            </div>
            <el-table :data="currentContent.questions" max-height="260" class="graph-table">
              <el-table-column label="题目来源" min-width="150">
                <template #default="scope">
                  <el-tooltip :content="scope.row.question || '暂无题干'" placement="top">
                    <span class="question-source">
                      {{ scope.row.doc_name || scope.row.doc_id }} / 第 {{ scope.row.question_id }} 题
                    </span>
                  </el-tooltip>
                </template>
              </el-table-column>
              <el-table-column label="关联知识点" min-width="170" show-overflow-tooltip>
                <template #default="scope">
                  {{ scope.row.node_ids.map((id: string) => nodeNameMap.get(id) || id).join("、") || "待补充" }}
                </template>
              </el-table-column>
              <el-table-column label="置信度" width="92" align="center">
                <template #default="scope">{{ formatConfidence(scope.row.confidence) }}</template>
              </el-table-column>
            </el-table>
          </section>
          <section v-else class="later-stage-panel">
            <div class="section-heading section-heading--compact">
              <div>
                <span class="section-kicker">03 / QUESTIONS</span>
                <h4>题目绑定</h4>
              </div>
            </div>
            <div class="later-stage-copy">
              <strong>下一阶段处理</strong>
              <span>先确认全局知识图谱，再把题目逐题挂载到稳定的知识点上。</span>
            </div>
          </section>
        </div>
      </template>
    </div>
  </el-dialog>
</template>

<style lang="scss" scoped>
.graph-dialog {
  min-height: 360px;
  color: #17233c;
}

.graph-intro {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 28px;
  padding: 24px;
  margin-bottom: 18px;
  border: 1px solid #dbe5f3;
  border-radius: 20px;
  background: linear-gradient(135deg, #f4f8ff 0%, #f9fbff 62%, #eefaf6 100%);
}

.eyebrow,
.section-kicker {
  color: #4f75bb;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.graph-intro h3 {
  margin: 8px 0 8px;
  font-size: 22px;
  font-weight: 650;
}

.graph-intro p {
  max-width: 700px;
  margin: 0;
  color: #6e7f9c;
  line-height: 1.7;
}

.graph-actions {
  display: flex;
  flex-shrink: 0;
  gap: 10px;
}

.graph-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 8px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-height: 102px;
  padding: 16px 18px;
  border: 1px solid #e3eaf4;
  border-radius: 16px;
  background: #fff;
}

.stat-card span,
.stat-card small {
  color: #8090aa;
  font-size: 12px;
}

.stat-card strong {
  color: #1c4e8f;
  font-size: 27px;
  line-height: 1;
}

.stat-card--status .el-tag {
  align-self: flex-start;
}

.graph-tabs {
  margin: 8px 0 18px;
}

.section-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin: 20px 0 10px;
}

.section-heading h4 {
  margin: 5px 0 0;
  font-size: 16px;
}

.section-heading > span {
  color: #9aa7bb;
  font-size: 12px;
}

.section-heading--compact {
  margin-top: 0;
}

.graph-table {
  border: 1px solid #e7edf5;
  border-radius: 12px;
  overflow: hidden;
}

.split-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 22px;
  margin-top: 22px;
}

.graph-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 245px;
  gap: 14px;
  min-height: 520px;
}

.graph-canvas {
  position: relative;
  min-width: 0;
  min-height: 520px;
  overflow: hidden;
  border: 1px solid #263f57;
  border-radius: 20px;
  background:
    radial-gradient(circle at 23% 18%, rgba(51, 117, 133, 0.28), transparent 28%),
    radial-gradient(circle at 78% 74%, rgba(47, 73, 120, 0.24), transparent 30%),
    #0e2234;
  box-shadow: 0 18px 44px rgba(27, 57, 83, 0.16);
}

.graph-canvas::before {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: "";
  opacity: 0.38;
  background-image: linear-gradient(rgba(151, 191, 212, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(151, 191, 212, 0.05) 1px, transparent 1px);
  background-size: 34px 34px;
}

.knowledge-graph-chart {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 520px;
}

.graph-canvas-hint {
  position: absolute;
  z-index: 2;
  right: 18px;
  bottom: 14px;
  color: #8ca9bd;
  font-size: 11px;
  pointer-events: none;
}

.node-inspector {
  min-width: 0;
  padding: 22px 18px;
  border: 1px solid #dce7f2;
  border-radius: 18px;
  background: linear-gradient(180deg, #f7fbff 0%, #ffffff 100%);
}

.node-inspector--empty {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.inspector-kicker {
  color: #5f85ad;
  font-size: 10px;
  font-weight: 750;
  letter-spacing: 0.14em;
}

.node-inspector h4 {
  margin: 13px 0 12px;
  color: #183d61;
  font-size: 20px;
  line-height: 1.35;
}

.node-inspector--empty h4 {
  font-size: 17px;
}

.node-inspector--empty p,
.inspector-block p {
  margin: 0;
  color: #7c8ea5;
  font-size: 12px;
  line-height: 1.65;
  overflow-wrap: anywhere;
}

.inspector-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding-bottom: 17px;
  border-bottom: 1px solid #e7eef6;
  color: #8192a8;
  font-size: 12px;
}

.inspector-block {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding-top: 17px;
}

.inspector-block > span {
  color: #a0adbc;
  font-size: 11px;
}

.mono {
  font-family: "SFMono-Regular", Consolas, monospace;
  font-size: 11px !important;
}

.relation-cell {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 6px;
  color: #334766;
}

.later-stage-panel {
  min-width: 0;
}

.later-stage-copy {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 104px;
  padding: 22px;
  border: 1px dashed #cad8ea;
  border-radius: 12px;
  background: #f8fbff;
  color: #7b8ba5;
  line-height: 1.6;
}

.later-stage-copy strong {
  color: #42689f;
}

.question-source {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.relation-cell span:first-child,
.relation-cell span:last-child {
  max-width: 145px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.arrow {
  color: #8aa4ca;
  font-size: 16px;
}

@media screen and (max-width: 900px) {
  .graph-intro,
  .split-grid,
  .graph-workspace {
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .graph-canvas,
  .knowledge-graph-chart {
    min-height: 430px;
    height: 430px;
  }

  .graph-actions {
    width: 100%;
  }

  .graph-actions .el-button {
    flex: 1;
  }

  .graph-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
