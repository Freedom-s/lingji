import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import learningService from '@/services/learning-service';
import QuizModal from './index';
import { getQuizProgressKey, saveQuizProgress } from './progress';

jest.mock('@/services/learning-service', () => ({
  __esModule: true,
  default: { getQuiz: jest.fn(), submitQuizResult: jest.fn() },
}));
jest.mock('@/utils/authorization-util', () => ({
  __esModule: true,
  default: { getUserInfo: () => JSON.stringify({ email: 'student@example.com' }) },
}));
jest.mock('@/components/math-text', () => ({
  __esModule: true,
  default: ({ text }: { text: string }) => <span>{text}</span>,
}));

const questions = [0, 1, 2].map((id) => ({
  id,
  question: `第 ${id + 1} 题`,
  options: { A: '选项 A', B: '选项 B' },
}));

describe('QuizModal resume', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    sessionStorage.clear();
    jest.mocked(learningService.getQuiz).mockResolvedValue({
      code: 0,
      data: { questions, kp_labels: {} },
    } as never);
    jest.mocked(learningService.submitQuizResult).mockResolvedValue({
      code: 0,
      data: { is_correct: true, correct_answer: 'A', explanations: {} },
    } as never);
  });

  it('keeps the next question after the modal is closed and the page remounts', async () => {
    const onClose = jest.fn();
    const view = render(<QuizModal open docId="chapter-7" onClose={onClose} />);
    await screen.findByText('第 1 题');

    fireEvent.click(screen.getAllByRole('radio')[0]);
    const submit = screen.getByRole('button', { name: '提交答案' });
    fireEvent.click(submit);
    fireEvent.click(submit);
    expect(learningService.submitQuizResult).toHaveBeenCalledTimes(1);
    fireEvent.click(await screen.findByRole('button', { name: '下一题' }));
    expect(screen.getByText('2 / 3')).toBeInTheDocument();

    fireEvent.click(document.querySelector('.ant-modal-mask')!);
    expect(onClose).not.toHaveBeenCalled();

    view.rerender(<QuizModal open={false} docId="chapter-7" onClose={onClose} />);
    view.rerender(<QuizModal open docId="chapter-7" onClose={onClose} />);
    await waitFor(() => expect(screen.getByText('2 / 3')).toBeInTheDocument());

    view.unmount();
    render(<QuizModal open docId="chapter-7" onClose={onClose} />);
    await waitFor(() => expect(screen.getByText('2 / 3')).toBeInTheDocument());
  });

  it('starts from the first question only when the student chooses to restart', async () => {
    saveQuizProgress(getQuizProgressKey('student@example.com', 'chapter-7'), questions, {
      currentIndex: 2,
      finished: false,
      answers: {
        0: { selectedAnswer: 'A', result: { is_correct: true, correct_answer: 'A', explanations: {} } },
        1: { selectedAnswer: 'A', result: { is_correct: true, correct_answer: 'A', explanations: {} } },
      },
      drafts: {},
    });

    render(<QuizModal open docId="chapter-7" onClose={jest.fn()} />);
    await screen.findByText('3 / 3');
    fireEvent.click(screen.getAllByRole('radio')[0]);
    fireEvent.click(screen.getByRole('button', { name: '提交答案' }));
    fireEvent.click(await screen.findByRole('button', { name: '查看结果' }));
    fireEvent.click(screen.getByRole('button', { name: '再来一次' }));

    await waitFor(() => expect(screen.getByText('1 / 3')).toBeInTheDocument());
  });

  it('reviews submitted answers without changing them and restores a draft after moving forward', async () => {
    const view = render(<QuizModal open docId="chapter-7" onClose={jest.fn()} />);
    await screen.findByText('第 1 题');
    fireEvent.click(screen.getAllByRole('radio')[0]);
    fireEvent.click(screen.getByRole('button', { name: '提交答案' }));
    fireEvent.click(await screen.findByRole('button', { name: '下一题' }));

    fireEvent.click(screen.getAllByRole('radio')[1]);
    expect(screen.getAllByRole('radio')[1]).toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: '上一题' }));
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
    expect(screen.getAllByRole('radio')[0]).toBeDisabled();
    expect(screen.queryByRole('button', { name: '提交答案' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '下一题' }));
    expect(screen.getByText('2 / 3')).toBeInTheDocument();
    expect(screen.getAllByRole('radio')[1]).toBeChecked();

    view.unmount();
    render(<QuizModal open docId="chapter-7" onClose={jest.fn()} />);
    await waitFor(() => expect(screen.getByText('2 / 3')).toBeInTheDocument());
    expect(screen.getAllByRole('radio')[1]).toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: '上一题' }));
    expect(screen.getAllByRole('radio')[0]).toBeDisabled();
    expect(learningService.submitQuizResult).toHaveBeenCalledTimes(1);
  });

  it('returns from the result screen to the last answered question', async () => {
    render(<QuizModal open docId="chapter-7" onClose={jest.fn()} />);
    await screen.findByText('第 1 题');
    for (let index = 0; index < questions.length; index += 1) {
      fireEvent.click(screen.getAllByRole('radio')[0]);
      fireEvent.click(screen.getByRole('button', { name: '提交答案' }));
      const nextLabel = index === questions.length - 1 ? '查看结果' : '下一题';
      fireEvent.click(await screen.findByRole('button', { name: nextLabel }));
    }

    expect(screen.getByText('你的得分：3 / 3')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '回看题目' }));
    expect(screen.getByText('3 / 3')).toBeInTheDocument();
    expect(screen.getAllByRole('radio')[0]).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '上一题' }));
    expect(screen.getByText('2 / 3')).toBeInTheDocument();
    expect(learningService.submitQuizResult).toHaveBeenCalledTimes(3);
  });
});
