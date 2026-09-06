<script lang="ts" setup>
import {
  ChatDotRound,
  Collection,
  Document,
  RefreshRight,
  Search,
  User
} from "@element-plus/icons-vue"
import dayjs from "dayjs"
import { computed, onMounted, ref } from "vue"
import { request } from "@/http/axios"

defineOptions({ name: "ConversationManagement" })

interface ApiResponse<T> {
  code: number
  data: T
  message: string
}

interface ClassSummary {
  id: string
  name: string
  studentCount: number
  conversationCount: number
}

interface StudentSummary {
  id: string
  name: string
  email: string
  conversationCount: number
  lastActiveAt: string
}

interface ConversationSummary {
  id: string
  name: string
  studentId: string
  studentName: string
  studentEmail: string
  classId: string
  className: string
  dialogId: string
  assistantName: string
  messageCount: number
  questionCount: number
  latestQuestion: string
  createTime: string
  updateTime: string
}

interface ReferenceDocument {
  documentId: string
  documentName: string
  count: number
}

interface ReferenceChunk {
  chunkId: string
  documentId: string
  documentName: string
  pageNumber?: number
  content: string
  similarity?: number
}

interface MessageReference {
  documents: ReferenceDocument[]
  chunks: ReferenceChunk[]
  total: number
}

interface ConversationMessage {
  id: string
  role: string
  content: string
  createdAt?: number
  reference: MessageReference | null
}

interface ConversationDetail extends ConversationSummary {
  messages: ConversationMessage[]
}

const classList = ref<ClassSummary[]>([])
const studentList = ref<StudentSummary[]>([])
const conversationList = ref<ConversationSummary[]>([])
const selectedClassId = ref("")
const selectedStudentId = ref("")
const selectedConversationId = ref("")
const selectedConversation = ref<ConversationDetail | null>(null)
const keyword = ref("")
const classLoading = ref(false)
const studentLoading = ref(false)
const conversationLoading = ref(false)
const detailLoading = ref(false)
const page = ref(1)
const pageSize = 20
const total = ref(0)

const selectedClass = computed(() => classList.value.find(item => item.id === selectedClassId.value))
const selectedStudent = computed(() => studentList.value.find(item => item.id === selectedStudentId.value))
const activeStudentCount = computed(() => studentList.value.filter(item => item.conversationCount > 0).length)

function formatTime(value?: string | number) {
  if (!value) return "暂无记录"
  const date = typeof value === "number"
    ? (value > 100000000000 ? dayjs(value) : dayjs.unix(value))
    : dayjs(value)
  return date.isValid() ? date.format("YYYY-MM-DD HH:mm") : "暂无记录"
}

function similarityText(value?: number) {
  if (typeof value !== "number") return ""
  return `${(value * 100).toFixed(1)}%`
}

async function loadClasses() {
  classLoading.value = true
  try {
    const { data } = await request<ApiResponse<ClassSummary[]>>({
      url: "api/v1/conversation/classes",
      method: "get"
    })
    classList.value = data || []
    if (!classList.value.some(item => item.id === selectedClassId.value)) {
      selectedClassId.value = classList.value[0]?.id || ""
    }
    if (selectedClassId.value) {
      await loadClassData()
    }
  } finally {
    classLoading.value = false
  }
}

async function loadClassData() {
  selectedStudentId.value = ""
  selectedConversationId.value = ""
  selectedConversation.value = null
  keyword.value = ""
  page.value = 1
  await Promise.all([loadStudents(), loadConversations()])
}

async function loadStudents() {
  if (!selectedClassId.value) {
    studentList.value = []
    return
  }
  studentLoading.value = true
  try {
    const { data } = await request<ApiResponse<StudentSummary[]>>({
      url: "api/v1/conversation/students",
      method: "get",
      params: { class_id: selectedClassId.value }
    })
    studentList.value = data || []
  } finally {
    studentLoading.value = false
  }
}

async function loadConversations() {
  if (!selectedClassId.value) {
    conversationList.value = []
    total.value = 0
    return
  }
  conversationLoading.value = true
  selectedConversationId.value = ""
  selectedConversation.value = null
  try {
    const { data } = await request<ApiResponse<{ list: ConversationSummary[], total: number }>>({
      url: "api/v1/conversation",
      method: "get",
      params: {
        class_id: selectedClassId.value,
        student_id: selectedStudentId.value || undefined,
        keyword: keyword.value.trim() || undefined,
        page: page.value,
        size: pageSize
      }
    })
    conversationList.value = data.list || []
    total.value = data.total || 0
    if (conversationList.value[0]) {
      await selectConversation(conversationList.value[0])
    }
  } finally {
    conversationLoading.value = false
  }
}

async function selectStudent(studentId: string) {
  if (selectedStudentId.value === studentId) return
  selectedStudentId.value = studentId
  page.value = 1
  await loadConversations()
}

async function selectConversation(conversation: ConversationSummary) {
  selectedConversationId.value = conversation.id
  detailLoading.value = true
  try {
    const { data } = await request<ApiResponse<ConversationDetail>>({
      url: `api/v1/conversation/${conversation.id}`,
      method: "get",
      params: { class_id: selectedClassId.value }
    })
    if (selectedConversationId.value === conversation.id) {
      selectedConversation.value = data
    }
  } finally {
    detailLoading.value = false
  }
}

function searchConversations() {
  page.value = 1
  loadConversations()
}

function resetSearch() {
  keyword.value = ""
  page.value = 1
  loadConversations()
}

function changePage(nextPage: number) {
  page.value = nextPage
  loadConversations()
}

onMounted(loadClasses)
</script>

<template>
  <div class="conversation-page">
    <section class="page-heading">
      <div>
        <p class="eyebrow">
          教学洞察
        </p>
        <h1>学生会话管理</h1>
        <p class="heading-copy">
          按班级查看学生向课程助教提出的问题、完整会话以及回答所引用的教学资料。
        </p>
      </div>
      <div class="heading-actions">
        <el-select
          v-model="selectedClassId"
          :loading="classLoading"
          class="class-select"
          placeholder="选择班级"
          @change="loadClassData"
        >
          <el-option v-for="item in classList" :key="item.id" :label="item.name" :value="item.id">
            <span>{{ item.name }}</span>
            <span class="option-count">{{ item.conversationCount }} 个会话</span>
          </el-option>
        </el-select>
        <el-button :icon="RefreshRight" circle aria-label="刷新会话数据" @click="loadClasses" />
      </div>
    </section>

    <section v-if="selectedClass" class="summary-strip">
      <div class="summary-primary">
        <span class="summary-class">{{ selectedClass.name }}</span>
        <span>当前仅展示您所带班级的学生数据</span>
      </div>
      <div class="summary-metrics">
        <span><strong>{{ selectedClass.studentCount }}</strong> 名学生</span>
        <span><strong>{{ activeStudentCount }}</strong> 人有提问</span>
        <span><strong>{{ selectedClass.conversationCount }}</strong> 个会话</span>
      </div>
    </section>

    <section v-if="classList.length" class="conversation-workspace">
      <aside class="workspace-panel student-panel">
        <div class="panel-heading">
          <div>
            <span class="panel-kicker">01</span>
            <h2>选择学生</h2>
          </div>
          <span class="panel-count">{{ studentList.length }}</span>
        </div>
        <div v-loading="studentLoading" class="student-list">
          <button
            type="button"
            class="student-row all-students"
            :class="{ active: !selectedStudentId }"
            @click="selectStudent('')"
          >
            <span class="avatar all"><el-icon><Collection /></el-icon></span>
            <span class="student-copy">
              <strong>全部学生</strong>
              <small>浏览全班会话</small>
            </span>
            <span class="conversation-badge">{{ selectedClass?.conversationCount || 0 }}</span>
          </button>
          <button
            v-for="student in studentList"
            :key="student.id"
            type="button"
            class="student-row"
            :class="{ active: selectedStudentId === student.id }"
            @click="selectStudent(student.id)"
          >
            <span class="avatar"><el-icon><User /></el-icon></span>
            <span class="student-copy">
              <strong>{{ student.name }}</strong>
              <small>{{ student.email }}</small>
              <small v-if="student.lastActiveAt">最近 {{ formatTime(student.lastActiveAt) }}</small>
            </span>
            <span class="conversation-badge">{{ student.conversationCount }}</span>
          </button>
          <el-empty v-if="!studentLoading && !studentList.length" :image-size="72" description="这个班级还没有学生" />
        </div>
      </aside>

      <section class="workspace-panel session-panel">
        <div class="panel-heading session-heading">
          <div>
            <span class="panel-kicker">02</span>
            <h2>{{ selectedStudent?.name || "全班会话" }}</h2>
          </div>
          <span class="panel-count">{{ total }}</span>
        </div>
        <div class="session-search">
          <el-input v-model="keyword" clearable placeholder="搜索学生、会话或问题" @keyup.enter="searchConversations">
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button type="primary" @click="searchConversations">
            搜索
          </el-button>
          <el-button v-if="keyword" text @click="resetSearch">
            清除
          </el-button>
        </div>
        <div v-loading="conversationLoading" class="session-list">
          <button
            v-for="conversation in conversationList"
            :key="conversation.id"
            type="button"
            class="session-row"
            :class="{ active: selectedConversationId === conversation.id }"
            @click="selectConversation(conversation)"
          >
            <span class="session-topline">
              <strong>{{ conversation.name }}</strong>
              <small>{{ formatTime(conversation.updateTime) }}</small>
            </span>
            <span class="session-owner">{{ conversation.studentName }} · {{ conversation.assistantName }}</span>
            <span class="latest-question">{{ conversation.latestQuestion }}</span>
            <span class="session-footer">
              <span>{{ conversation.questionCount }} 个问题</span>
              <span>{{ conversation.messageCount }} 条消息</span>
            </span>
          </button>
          <el-empty
            v-if="!conversationLoading && !conversationList.length"
            :image-size="88"
            :description="keyword ? '没有找到相关问题' : '暂时没有学生会话'"
          />
        </div>
        <el-pagination
          v-if="total > pageSize"
          class="session-pagination"
          background
          small
          layout="prev, pager, next"
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          @current-change="changePage"
        />
      </section>

      <main class="workspace-panel detail-panel">
        <template v-if="selectedConversation">
          <div class="detail-heading">
            <div>
              <div class="detail-title-line">
                <span class="panel-kicker">03</span>
                <h2>{{ selectedConversation.name }}</h2>
              </div>
              <p>{{ selectedConversation.studentName }} · {{ selectedConversation.className }} · {{ selectedConversation.assistantName }}</p>
            </div>
            <div class="detail-stats">
              <span>{{ selectedConversation.questionCount }} 个问题</span>
              <span>更新于 {{ formatTime(selectedConversation.updateTime) }}</span>
            </div>
          </div>

          <div v-loading="detailLoading" class="message-stream">
            <article
              v-for="(message, messageIndex) in selectedConversation.messages"
              :key="message.id"
              class="message-block"
              :class="message.role === 'user' ? 'student-message' : 'assistant-message'"
            >
              <div class="message-label">
                <span>{{ message.role === "user" ? selectedConversation.studentName : "课程助教" }}</span>
                <span v-if="message.createdAt">{{ formatTime(message.createdAt) }}</span>
                <span v-else>第 {{ messageIndex + 1 }} 条</span>
              </div>
              <div class="message-content">
                {{ message.content }}
              </div>

              <div v-if="message.reference" class="reference-box">
                <div class="reference-heading">
                  <span><el-icon><Document /></el-icon> 回答引用</span>
                  <small>{{ message.reference.chunks.length }} 条依据</small>
                </div>
                <div v-if="message.reference.documents.length" class="reference-documents">
                  <el-tag
                    v-for="documentItem in message.reference.documents"
                    :key="documentItem.documentId"
                    effect="plain"
                    round
                  >
                    {{ documentItem.documentName }}
                  </el-tag>
                </div>
                <el-collapse class="reference-chunks">
                  <el-collapse-item
                    v-for="(chunk, chunkIndex) in message.reference.chunks"
                    :key="chunk.chunkId || `${message.id}-${chunkIndex}`"
                    :name="`${message.id}-${chunkIndex}`"
                  >
                    <template #title>
                      <span class="chunk-title">
                        <strong>{{ chunk.documentName }}</strong>
                        <span v-if="chunk.pageNumber">第 {{ chunk.pageNumber }} 页</span>
                        <span v-if="similarityText(chunk.similarity)">相关度 {{ similarityText(chunk.similarity) }}</span>
                      </span>
                    </template>
                    <p class="chunk-content">
                      {{ chunk.content || "该引用未保存文本摘要" }}
                    </p>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </article>
            <el-empty v-if="!selectedConversation.messages.length" :image-size="88" description="该会话没有消息内容" />
          </div>
        </template>
        <div v-else v-loading="detailLoading" class="detail-empty">
          <el-icon><ChatDotRound /></el-icon>
          <h3>选择一个会话</h3>
          <p>这里会展示学生的完整提问、助教回答及每次回答引用的教学资料。</p>
        </div>
      </main>
    </section>

    <el-empty v-else-if="!classLoading" class="page-empty" description="您还没有创建班级，暂无会话可查看" />
  </div>
</template>

<style lang="scss" scoped>
.conversation-page {
  min-height: calc(100vh - 84px);
  padding: 24px;
  color: #172033;
  background: radial-gradient(circle at 4% 0%, rgba(46, 109, 246, 0.08), transparent 26%), #f4f6fa;
}

.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 18px;

  h1 {
    margin: 2px 0 8px;
    font-family: "Noto Serif SC", "Songti SC", serif;
    font-size: 30px;
    font-weight: 700;
    letter-spacing: -0.02em;
  }
}

.eyebrow,
.panel-kicker {
  margin: 0;
  color: #2e6df6;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.heading-copy {
  margin: 0;
  color: #687287;
  font-size: 14px;
}

.heading-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.class-select {
  width: 260px;
}

.option-count {
  float: right;
  margin-left: 24px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.summary-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  min-height: 54px;
  padding: 10px 16px;
  border: 1px solid #dfe5ef;
  border-radius: 12px;
  margin-bottom: 14px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 8px 24px rgba(20, 35, 65, 0.04);
}

.summary-primary,
.summary-metrics {
  display: flex;
  align-items: center;
  gap: 14px;
  color: #70798b;
  font-size: 12px;
}

.summary-class {
  color: #172033;
  font-size: 15px;
  font-weight: 700;
}

.summary-metrics span {
  padding-left: 14px;
  border-left: 1px solid #dfe5ef;
}

.summary-metrics strong {
  margin-right: 3px;
  color: #172033;
  font-size: 16px;
}

.conversation-workspace {
  display: grid;
  grid-template-columns: minmax(230px, 0.72fr) minmax(300px, 0.95fr) minmax(460px, 1.7fr);
  gap: 14px;
  height: calc(100vh - 245px);
  min-height: 640px;
}

.workspace-panel {
  min-width: 0;
  overflow: hidden;
  border: 1px solid #dfe5ef;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(20, 35, 65, 0.055);
}

.student-panel,
.session-panel,
.detail-panel {
  display: flex;
  flex-direction: column;
}

.panel-heading,
.detail-heading {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  min-height: 72px;
  padding: 14px 16px;
  border-bottom: 1px solid #edf0f5;

  h2 {
    margin: 2px 0 0;
    font-size: 16px;
    font-weight: 700;
  }
}

.panel-count,
.conversation-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  color: #566176;
  background: #eef2f8;
  font-size: 12px;
  font-weight: 700;
}

.student-list,
.session-list,
.message-stream {
  min-height: 0;
  overflow-y: auto;
}

.student-list {
  flex: 1;
  padding: 10px;
}

.student-row,
.session-row {
  width: 100%;
  border: 0;
  text-align: left;
  cursor: pointer;
}

.student-row {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 10px;
  margin-bottom: 4px;
  color: inherit;
  background: transparent;
  transition:
    background 160ms ease,
    box-shadow 160ms ease;

  &:hover {
    background: #f5f7fb;
  }

  &.active {
    background: #edf3ff;
    box-shadow: inset 3px 0 #2e6df6;
  }
}

.avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  color: #315ea8;
  background: #e8eef9;

  &.all {
    color: #fff;
    background: #243653;
  }
}

.student-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;

  strong,
  small {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  strong {
    font-size: 13px;
  }

  small {
    color: #7a8497;
    font-size: 11px;
  }
}

.student-row.active .conversation-badge {
  color: #235ccf;
  background: #fff;
}

.session-search {
  display: flex;
  flex: 0 0 auto;
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid #edf0f5;
}

.session-list {
  flex: 1;
  padding: 8px;
}

.session-row {
  display: flex;
  flex-direction: column;
  gap: 7px;
  padding: 13px;
  border: 1px solid transparent;
  border-radius: 11px;
  margin-bottom: 7px;
  color: inherit;
  background: #fff;
  transition:
    border-color 160ms ease,
    background 160ms ease;

  &:hover {
    border-color: #dce3ee;
    background: #fafbfe;
  }

  &.active {
    border-color: #bcd0fa;
    background: #f1f5ff;
  }
}

.session-topline,
.session-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.session-topline strong {
  overflow: hidden;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-topline small,
.session-footer,
.session-owner {
  color: #7b8495;
  font-size: 11px;
}

.session-owner {
  color: #3d67a5;
  font-weight: 600;
}

.latest-question {
  display: -webkit-box;
  overflow: hidden;
  color: #4b5568;
  font-size: 12px;
  line-height: 1.55;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.session-footer {
  justify-content: flex-start;
}

.session-pagination {
  flex: 0 0 auto;
  justify-content: center;
  padding: 12px;
  border-top: 1px solid #edf0f5;
}

.detail-heading {
  align-items: flex-start;
  min-height: 78px;

  p {
    margin: 6px 0 0;
    color: #697386;
    font-size: 12px;
  }
}

.detail-title-line {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.detail-stats {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 5px;
  color: #747e91;
  font-size: 11px;
}

.message-stream {
  flex: 1;
  padding: 20px 22px 30px;
  background: #f8f9fc;
}

.message-block {
  width: min(86%, 760px);
  padding: 14px 16px;
  border-radius: 14px;
  margin-bottom: 16px;
}

.student-message {
  margin-left: auto;
  color: #fff;
  background: #2e6df6;
  border-bottom-right-radius: 4px;
  box-shadow: 0 8px 20px rgba(46, 109, 246, 0.18);
}

.assistant-message {
  margin-right: auto;
  border: 1px solid #e3e8f0;
  border-bottom-left-radius: 4px;
  background: #fff;
}

.message-label {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 8px;
  color: inherit;
  font-size: 11px;
  font-weight: 700;
  opacity: 0.72;
}

.message-content {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.75;
}

.reference-box {
  padding-top: 13px;
  border-top: 1px solid #e7ebf2;
  margin-top: 14px;
  color: #263247;
}

.reference-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;

  > span {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 800;
  }

  small {
    color: #7a8497;
  }
}

.reference-documents {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.reference-chunks {
  --el-collapse-header-height: 38px;
  border: 0;
}

.chunk-title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
  color: #697386;
  font-size: 11px;

  strong {
    max-width: 240px;
    overflow: hidden;
    color: #344158;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.chunk-content {
  margin: 0;
  color: #5f697b;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.detail-empty {
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  padding: 36px;
  color: #7a8497;
  text-align: center;

  .el-icon {
    padding: 16px;
    border-radius: 18px;
    margin-bottom: 12px;
    color: #2e6df6;
    background: #edf3ff;
    font-size: 34px;
  }

  h3 {
    margin: 0 0 8px;
    color: #273247;
  }

  p {
    max-width: 360px;
    margin: 0;
    font-size: 13px;
    line-height: 1.7;
  }
}

.page-empty {
  padding-top: 120px;
}

@media (max-width: 1180px) {
  .conversation-workspace {
    grid-template-columns: 220px 310px minmax(420px, 1fr);
    overflow-x: auto;
  }

  .workspace-panel {
    min-width: 0;
  }
}

@media (max-width: 760px) {
  .conversation-page {
    padding: 16px;
  }

  .page-heading,
  .summary-strip {
    align-items: stretch;
    flex-direction: column;
  }

  .class-select {
    width: 100%;
  }

  .conversation-workspace {
    display: flex;
    height: auto;
    min-height: 0;
    overflow: visible;
    flex-direction: column;
  }

  .workspace-panel {
    min-height: 420px;
  }
}
</style>
