import request from '@/utils/request';

const BASE = '/v1/learning';

// 因为 umi-request 配置了 getResponse: true，返回的是 { data: body, response: Response }
// 这里统一解包，让调用方拿到的是 { code, data, message }
const unwrap = <T>(p: Promise<any>): Promise<T> => p.then((res: any) => res?.data);

const learningService = {
  getMindMap: (docId: string) => unwrap(request.get(`${BASE}/mindmap/${docId}`)),

  getFlashcards: (docId: string) => unwrap(request.get(`${BASE}/flashcards/${docId}`)),

  updateFlashcardProgress: (docId: string, data: { card_index: number; status: string }) =>
    unwrap(request.post(`${BASE}/flashcards/${docId}/progress`, { data })),

  getQuiz: (docId: string) => unwrap(request.get(`${BASE}/quiz/${docId}`)),

  submitQuizResult: (docId: string, data: { question_index: number; student_answer: string; is_correct: boolean }) =>
    unwrap(request.post(`${BASE}/quiz/${docId}/result`, { data })),

  getQuizResult: (docId: string) => unwrap(request.get(`${BASE}/quiz/${docId}/result`)),

  getNote: (docId: string, pageNumber: number) =>
    unwrap(request.get(`${BASE}/note/${docId}`, { params: { page_number: pageNumber } })),

  saveNote: (docId: string, data: { page_number: number; content: string }) =>
    unwrap(request.post(`${BASE}/note/${docId}`, { data })),

  getAllNotes: (docId: string) => unwrap(request.get(`${BASE}/notes/${docId}`)),

  // 个性化测验
  startPersonalizedQuiz: (data: { dialog_id: string; count?: number }) =>
    unwrap(request.post(`${BASE}/personalized-quiz/start`, { data })),

  answerPersonalizedQuiz: (data: {
    doc_id: string;
    question_id: number;
    knowledge_point_ids: string[];
    student_answer: string;
    is_correct: boolean;
  }) => unwrap(request.post(`${BASE}/personalized-quiz/answer`, { data })),

  getKnowledgeReport: (dialogId: string) =>
    unwrap(request.get(`${BASE}/knowledge-report`, { params: { dialog_id: dialogId } })),
};

export default learningService;
