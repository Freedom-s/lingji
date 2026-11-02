import { Modal, Spin, Empty, Result, Button, Progress, Typography, Radio, Space, Tag } from 'antd';
import { CheckCircleFilled, CloseCircleFilled, ThunderboltOutlined, ExperimentOutlined } from '@ant-design/icons';
import { useEffect, useMemo, useRef, useState } from 'react';
import learningService from '@/services/learning-service';
import authorizationUtil from '@/utils/authorization-util';
import MathText from '@/components/math-text';
import {
  clearQuizProgress,
  getQuizProgressKey,
  loadQuizProgress,
  saveQuizProgress,
} from './progress';
import type { QuizAnswer, SubmitResult } from './progress';
import styles from './index.less';

const { Text, Title, Paragraph } = Typography;

interface QuizQuestion {
  id: number;
  question: string;
  options: Record<string, string>;
  knowledge_point_ids?: string[];
  knowledge_point_names?: string[];
  doc_id?: string;
}

interface QuizModalProps {
  open: boolean;
  docId?: string;
  dialogId?: string;
  mode?: 'default' | 'personalized';
  onClose: () => void;
}

const QuizModal = ({ open, docId, dialogId, mode = 'default', onClose }: QuizModalProps) => {
  const [loading, setLoading] = useState(false);
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [kpLabels, setKpLabels] = useState<Record<string, string>>({});
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, QuizAnswer>>({});
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [finished, setFinished] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const submitInFlight = useRef(false);
  const [readyKey, setReadyKey] = useState<string | null>(null);
  const [restartCount, setRestartCount] = useState(0);

  const isPersonalized = mode === 'personalized';
  const userEmail = useMemo(() => {
    try {
      return JSON.parse(authorizationUtil.getUserInfo() || '{}').email as string | undefined;
    } catch {
      return undefined;
    }
  }, []);
  const progressKey = !isPersonalized && docId && userEmail
    ? getQuizProgressKey(userEmail, docId)
    : null;
  const currentAnswer = answers[currentIndex];
  const selectedAnswer = currentAnswer?.selectedAnswer ?? drafts[currentIndex] ?? null;
  const submitted = Boolean(currentAnswer);
  const submitResult = currentAnswer?.result ?? null;
  const score = Object.values(answers).filter((answer) => answer.result.is_correct).length;

  useEffect(() => {
    if (!open || (isPersonalized ? !dialogId : !docId)) return;
    let active = true;
    setLoading(true);
    setError(null);
    setQuestions([]);
    setReadyKey(null);

    const request = isPersonalized
      ? learningService.startPersonalizedQuiz({ dialog_id: dialogId!, count: 10 })
      : learningService.getQuiz(docId!);

    request
      .then((res: any) => {
        if (!active) return;
        const nextQuestions: QuizQuestion[] = res?.code === 0
          ? res?.data?.questions || []
          : [];
        setQuestions(nextQuestions);
        setKpLabels(res?.data?.kp_labels || {});
        const saved = progressKey && nextQuestions.length
          ? loadQuizProgress(progressKey, nextQuestions)
          : null;
        setCurrentIndex(saved?.currentIndex ?? 0);
        setAnswers(saved?.answers ?? {});
        setDrafts(saved?.drafts ?? {});
        setFinished(saved?.finished ?? false);
        setReadyKey(progressKey);
      })
      .catch((err: any) => {
        if (active) setError(err?.message || '获取测验失败');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, [open, docId, dialogId, isPersonalized, progressKey, restartCount]);

  useEffect(() => {
    if (readyKey && readyKey === progressKey && questions.length) {
      saveQuizProgress(readyKey, questions, {
        currentIndex,
        finished,
        answers,
        drafts,
      });
    }
  }, [readyKey, progressKey, questions, currentIndex, finished, answers, drafts]);

  const handleSelect = (value: string) => {
    if (submitted) return;
    setDrafts((current) => ({ ...current, [currentIndex]: value }));
  };

  const handleSubmit = async () => {
    if (!selectedAnswer || submitted || submitInFlight.current) return;
    const question = questions[currentIndex];
    submitInFlight.current = true;
    setSubmitting(true);

    try {
      let body: any;
      if (isPersonalized) {
        body = await learningService.answerPersonalizedQuiz({
          doc_id: question.doc_id || docId || '',
          question_id: question.id,
          knowledge_point_ids: question.knowledge_point_ids || [],
          student_answer: selectedAnswer,
        });
      } else {
        body = await learningService.submitQuizResult(docId!, {
          question_index: question.id,
          student_answer: selectedAnswer,
        });
      }
      if (body?.code !== 0 || typeof body?.data?.is_correct !== 'boolean') return;
      const res: SubmitResult = body.data;
      setAnswers((current) => ({
        ...current,
        [currentIndex]: { selectedAnswer, result: res },
      }));
    } catch {
      // API 失败时不做判题回退
    } finally {
      submitInFlight.current = false;
      setSubmitting(false);
    }
  };

  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((index) => index + 1);
    } else {
      setFinished(true);
    }
  };

  const handlePrevious = () => {
    setCurrentIndex((index) => Math.max(0, index - 1));
  };

  const handleRestart = () => {
    if (progressKey) clearQuizProgress(progressKey);
    setReadyKey(null);
    setRestartCount((count) => count + 1);
  };

  const renderContent = () => {
    if (loading) return <Spin size="large" tip="加载测验..." />;
    if (error) return <Result status="error" title="加载失败" subTitle={error} />;
    if (!questions.length) {
      const msg = isPersonalized
        ? '暂无可用题目，请等待课件解析完成后再试'
        : '测验尚未生成，请等待课件解析完成后重试';
      return <Empty description={msg} />;
    }

    if (finished) {
      return (
        <div className={styles.finishContainer}>
          <Title level={3}>{isPersonalized ? '个性化测验完成' : '测验完成'}</Title>
          <div className={styles.scoreCircle}>
            <Progress type="circle" percent={Math.round((score / questions.length) * 100)} format={() => `${score}/${questions.length}`} />
          </div>
          <Paragraph>你的得分：{score} / {questions.length}</Paragraph>
          {isPersonalized && (
            <Paragraph type="secondary">
              答题数据已用于优化后续题目推荐，继续加油！
            </Paragraph>
          )}
          <Space>
            <Button onClick={() => setFinished(false)}>回看题目</Button>
            <Button type="primary" onClick={handleRestart}>再来一次</Button>
            <Button onClick={onClose}>关闭</Button>
          </Space>
        </div>
      );
    }

    const question = questions[currentIndex];
    const optionKeys = Object.keys(question.options);

    return (
      <div className={styles.quizContainer}>
        <div className={styles.progressBar}>
          <Progress percent={Math.round(((currentIndex + 1) / questions.length) * 100)} showInfo={false} />
          <Text type="secondary">{currentIndex + 1} / {questions.length}</Text>
        </div>

        {question.knowledge_point_ids && question.knowledge_point_ids.length > 0 && (
          <div className={styles.kpTags}>
            {question.knowledge_point_ids.map((kp, idx) => (
              <Tag key={idx} color="blue">{question.knowledge_point_names?.[idx] || kpLabels[kp] || kp}</Tag>
            ))}
          </div>
        )}

        <div className={styles.questionCard}>
          <Title level={5} className={styles.questionText}><MathText text={question.question} /></Title>
          <Radio.Group className={styles.optionsGroup} value={selectedAnswer} onChange={(e) => handleSelect(e.target.value)}>
            {optionKeys.map((key) => {
              const isCorrect = key === submitResult?.correct_answer;
              const isSelected = selectedAnswer === key;
              const showResult = submitted;
              let optionClass = styles.option;
              if (showResult && isCorrect) optionClass += ` ${styles.optionCorrect}`;
              if (showResult && isSelected && !isCorrect) optionClass += ` ${styles.optionWrong}`;
              return (
                <div key={key} className={optionClass}>
                  <Radio value={key} disabled={submitted}>
                    <span className={styles.optionLabel}>{key}. <MathText inline text={question.options[key]} /></span>
                  </Radio>
                  {showResult && isCorrect && <CheckCircleFilled className={styles.iconCorrect} />}
                  {showResult && isSelected && !isCorrect && <CloseCircleFilled className={styles.iconWrong} />}
                  {showResult && (
                    <div className={styles.explanation}><MathText inline text={submitResult?.explanations[key]} /></div>
                  )}
                </div>
              );
            })}
          </Radio.Group>
        </div>

        <div className={styles.quizNav}>
          <Button onClick={handlePrevious} disabled={currentIndex === 0 || submitting}>
            上一题
          </Button>
          {!submitted ? (
            <Button type="primary" onClick={handleSubmit} disabled={!selectedAnswer || submitting} loading={submitting}>
              提交答案
            </Button>
          ) : (
            <Button type="primary" onClick={handleNext}>
              {currentIndex < questions.length - 1 ? '下一题' : '查看结果'}
            </Button>
          )}
        </div>
      </div>
    );
  };

  return (
    <Modal
      title={
        isPersonalized
          ? <span><ThunderboltOutlined /> 个性化测验</span>
          : <span><ExperimentOutlined /> 随堂测验</span>
      }
      open={open}
      onCancel={onClose}
      maskClosable={false}
      footer={null}
      width={650}
      destroyOnClose
      centered
    >
      <div className={styles.modalContent}>{renderContent()}</div>
    </Modal>
  );
};

export default QuizModal;
