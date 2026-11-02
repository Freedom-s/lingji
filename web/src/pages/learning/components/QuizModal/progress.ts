export interface SubmitResult {
  is_correct: boolean;
  correct_answer: string;
  explanations: Record<string, string>;
}

export interface QuizAnswer {
  selectedAnswer: string;
  result: SubmitResult;
}

export interface QuizProgress {
  currentIndex: number;
  finished: boolean;
  answers: Record<number, QuizAnswer>;
  drafts: Record<number, string>;
}

interface StoredQuizProgress extends QuizProgress {
  version: 2;
  questionIds: number[];
}

export const getQuizProgressKey = (userIdentity: string, docId: string) =>
  `quiz-progress:v2:${userIdentity}:${docId}`;

export const loadQuizProgress = (
  key: string,
  questions: Array<{ id: number; options: Record<string, string> }>,
): QuizProgress | null => {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    const saved = JSON.parse(raw) as StoredQuizProgress;
    if (
      saved.version !== 2 ||
      !Array.isArray(saved.questionIds) ||
      saved.questionIds.length !== questions.length ||
      saved.questionIds.some((id, index) => id !== questions[index].id) ||
      !Number.isInteger(saved.currentIndex) ||
      saved.currentIndex < 0 ||
      saved.currentIndex >= questions.length ||
      typeof saved.finished !== 'boolean' ||
      !saved.answers || typeof saved.answers !== 'object' || Array.isArray(saved.answers) ||
      !saved.drafts || typeof saved.drafts !== 'object' || Array.isArray(saved.drafts)
    ) return null;

    for (const [index, answer] of Object.entries(saved.answers)) {
      const question = questions[Number(index)];
      if (
        !question || !answer ||
        !Object.prototype.hasOwnProperty.call(question.options, answer.selectedAnswer) ||
        !answer.result || typeof answer.result.is_correct !== 'boolean' ||
        !Object.prototype.hasOwnProperty.call(question.options, answer.result.correct_answer) ||
        !answer.result.explanations || typeof answer.result.explanations !== 'object'
      ) return null;
    }
    for (const [index, draft] of Object.entries(saved.drafts)) {
      const question = questions[Number(index)];
      if (!question || !Object.prototype.hasOwnProperty.call(question.options, draft)) return null;
    }
    if (saved.finished && Object.keys(saved.answers).length !== questions.length) return null;

    return {
      currentIndex: saved.currentIndex,
      finished: saved.finished,
      answers: saved.answers,
      drafts: saved.drafts,
    };
  } catch {
    return null;
  }
};

export const saveQuizProgress = (
  key: string,
  questions: Array<{ id: number }>,
  progress: QuizProgress,
) => {
  try {
    sessionStorage.setItem(
      key,
      JSON.stringify({
        version: 2,
        questionIds: questions.map((question) => question.id),
        ...progress,
      } satisfies StoredQuizProgress),
    );
  } catch {
    // Storage may be disabled; the in-memory quiz remains usable.
  }
};

export const clearQuizProgress = (key: string) => {
  try {
    sessionStorage.removeItem(key);
  } catch {
    // Storage may be disabled.
  }
};
