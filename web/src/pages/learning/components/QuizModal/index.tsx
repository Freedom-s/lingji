import { Modal, Spin, Empty, Result, Button, Progress, Typography, Radio, Space, Tag } from 'antd';
import { CheckCircleFilled, CloseCircleFilled, ThunderboltOutlined, ExperimentOutlined } from '@ant-design/icons';
import { useEffect, useState, useCallback } from 'react';
import learningService from '@/services/learning-service';
import MathText from '@/components/math-text';
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

interface SubmitResult {
  is_correct: boolean;
  correct_answer: string;
  explanations: Record<string, string>;
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
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [score, setScore] = useState(0);
  const [finished, setFinished] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitResult, setSubmitResult] = useState<SubmitResult | null>(null);

  const isPersonalized = mode === 'personalized';

  const fetchQuiz = useCallback(() => {
    if (isPersonalized) {
      if (!dialogId) return;
      setLoading(true);
      setError(null);
      learningService
        .startPersonalizedQuiz({ dialog_id: dialogId, count: 10 })
        .then((res: any) => {
          if (res?.code === 0 && res?.data?.questions?.length > 0) {
            setQuestions(res.data.questions);
            setKpLabels(res.data.kp_labels || {});
          }
        })
        .catch((err: any) => setError(err?.message || '获取个性化测验失败'))
        .finally(() => setLoading(false));
    } else {
      if (!docId) return;
      setLoading(true);
      setError(null);
      learningService
        .getQuiz(docId)
        .then((res: any) => {
          if (res?.code === 0 && res?.data?.questions?.length > 0) {
            setQuestions(res.data.questions);
            setKpLabels(res.data.kp_labels || {});
          }
        })
        .catch((err: any) => setError(err?.message || '获取测验失败'))
        .finally(() => setLoading(false));
    }
  }, [docId, dialogId, isPersonalized]);

  useEffect(() => {
    if (open && (docId || dialogId)) {
      fetchQuiz();
      setCurrentIndex(0);
      setSelectedAnswer(null);
      setSubmitted(false);
      setScore(0);
      setFinished(false);
      setSubmitResult(null);
    }
  }, [open, docId, dialogId, fetchQuiz]);

  const handleSelect = (value: string) => {
    if (submitted) return;
    setSelectedAnswer(value);
  };

  const handleSubmit = async () => {
    if (!selectedAnswer) return;
    const question = questions[currentIndex];

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
      // unwrap 返回的是 { code, data, message }，body.data 才是实际结果
      const res: SubmitResult = body?.data || body;
      setSubmitResult(res);
      if (res.is_correct) setScore((s) => s + 1);
      setSubmitted(true);
    } catch {
      // API 失败时不做判题回退
    }
  };

  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(currentIndex + 1);
      setSelectedAnswer(null);
      setSubmitted(false);
      setSubmitResult(null);
    } else {
      setFinished(true);
    }
  };

  const handleRestart = () => {
    fetchQuiz();
    setCurrentIndex(0);
    setSelectedAnswer(null);
    setSubmitted(false);
    setScore(0);
    setFinished(false);
    setSubmitResult(null);
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
          {!submitted ? (
            <Button type="primary" onClick={handleSubmit} disabled={!selectedAnswer}>
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
