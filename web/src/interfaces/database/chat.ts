import { MessageType } from '@/constants/chat';

export interface PromptConfig {
  empty_response: string;
  parameters: Parameter[];
  prologue: string;
  system: string;
  tts?: boolean;
  cross_language_search?: boolean;
}

export interface Parameter {
  key: string;
  optional: boolean;
}

export interface LlmSetting {
  Creative: Variable;
  Custom: Variable;
  Evenly: Variable;
  Precise: Variable;
}

export interface Variable {
  frequency_penalty?: number;
  max_tokens?: number;
  presence_penalty?: number;
  temperature?: number;
  top_p?: number;
}

export interface IDialog {
  create_date: string;
  create_time: number;
  description: string;
  icon: string;
  id: string;
  dialog_id: string;
  kb_ids: string[];
  kb_names: string[];
  language: string;
  llm_id: string;
  llm_setting: Variable;
  llm_setting_type: string;
  name: string;
  prompt_config: PromptConfig;
  prompt_type: string;
  status: string;
  tenant_id: string;
  update_date: string;
  update_time: number;
  vector_similarity_weight: number;
  similarity_threshold: number;
}

export interface IConversation {
  create_date: string;
  create_time: number;
  dialog_id: string;
  id: string;
  avatar: string;
  message: Message[];
  reference: IReference[];
  name: string;
  update_date: string;
  update_time: number;
  is_new: true;
}

export interface Message {
  content: string;
  role: MessageType;
  doc_ids?: string[];
  temp_file_ids?: string[];
  attachments?: { id: string; file_name: string; file_type: string; file_size: number; mime_type: string }[];
  prompt?: string;
  id?: string;
  audio_binary?: string;
  original_content?: string;
}

export interface IReferenceChunk {
  page_id: string;             // 页面ID
  doc_id: string;              // 文档ID
  docnm_kwd: string;           // 文档名称
  kb_id: string;               // 知识库ID
  page_num_int?: number;       // 页码
  img_url?: string;            // 页面图片URL
  content_with_weight?: string; // 内容（带权重）
  similarity: number;          // 相似度分数
}

export interface IReference {
  chunks: IReferenceChunk[];
  doc_aggs: Docagg[];
  total: number;
}

export interface IAnswer {
  answer: string;
  reference: IReference;
  conversationId?: string;
  prompt?: string;
  id?: string;
  audio_binary?: string;
}

export interface Docagg {
  count: number;
  doc_id: string;
  doc_name: string;
  url?: string;
}

// interface Chunk {
//   chunk_id: string;
//   content_ltks: string;
//   content_with_weight: string;
//   doc_id: string;
//   docnm_kwd: string;
//   img_id: string;
//   important_kwd: any[];
//   kb_id: string;
//   similarity: number;
//   term_similarity: number;
//   vector_similarity: number;
// }

export interface IToken {
  create_date: string;
  create_time: number;
  tenant_id: string;
  token: string;
  update_date?: any;
  update_time?: any;
  beta: string;
}

export interface IStats {
  pv: [string, number][];
  uv: [string, number][];
  speed: [string, number][];
  tokens: [string, number][];
  round: [string, number][];
  thumb_up: [string, number][];
}
