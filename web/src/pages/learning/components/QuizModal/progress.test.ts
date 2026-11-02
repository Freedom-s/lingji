import {
  clearQuizProgress,
  getQuizProgressKey,
  loadQuizProgress,
  saveQuizProgress,
} from './progress';

const questions = Array.from({ length: 82 }, (_, id) => ({
  id,
  options: { A: '选项 A', B: '选项 B' },
}));

describe('quiz progress', () => {
  beforeEach(() => sessionStorage.clear());

  it('restores the current question and graded answer after reopening', () => {
    const key = getQuizProgressKey('student-1', 'chapter-7');
    const progress = {
      currentIndex: 42,
      finished: false,
      answers: {
        41: {
          selectedAnswer: 'B',
          result: {
            is_correct: false,
            correct_answer: 'A',
            explanations: { A: '解析' },
          },
        },
      },
      drafts: { 42: 'A' },
    };

    saveQuizProgress(key, questions, progress);

    expect(loadQuizProgress(key, questions)).toEqual(progress);
    expect(loadQuizProgress(getQuizProgressKey('student-2', 'chapter-7'), questions)).toBeNull();
  });

  it('discards progress when the teacher changes the question list', () => {
    const key = getQuizProgressKey('student-1', 'chapter-7');
    saveQuizProgress(key, questions, {
      currentIndex: 42,
      finished: false,
      answers: {},
      drafts: {},
    });

    expect(loadQuizProgress(key, questions.map((question, index) =>
      index === 42 ? { ...question, id: 999 } : question,
    ))).toBeNull();
    clearQuizProgress(key);
    expect(loadQuizProgress(key, questions)).toBeNull();
  });
});
