import { Modal, Spin, Empty, Result, Button, Progress, Typography, Tag } from 'antd';
import { CheckOutlined, QuestionOutlined } from '@ant-design/icons';
import { useEffect, useState, useCallback } from 'react';
import learningService from '@/services/learning-service';
import MathText from '@/components/math-text';
import styles from './index.less';

const { Text, Title } = Typography;

interface Flashcard {
  id: number;
  question: string;
  answer: string;
  knowledge_point_ids?: string[];
}

interface FlashcardModalProps {
  open: boolean;
  docId: string | undefined;
  onClose: () => void;
}

const FlashcardModal = ({ open, docId, onClose }: FlashcardModalProps) => {
  const [loading, setLoading] = useState(false);
  const [cards, setCards] = useState<Flashcard[]>([]);
  const [kpLabels, setKpLabels] = useState<Record<string, string>>({});
  const [progress, setProgress] = useState<Record<number, string>>({});
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(() => {
    if (!docId) return;
    setLoading(true);
    setError(null);
    learningService
      .getFlashcards(docId)
      .then((res: any) => {
        if (res?.code === 0 && res?.data?.cards?.length > 0) {
          setCards(res.data.cards);
          setKpLabels(res.data.kp_labels || {});
          setProgress(res.data.progress || {});
          setCurrentIndex(0);
        }
      })
      .catch((err: any) => setError(err?.message || '获取闪卡失败'))
      .finally(() => setLoading(false));
  }, [docId]);

  useEffect(() => {
    if (open && docId) {
      fetchData();
      setShowAnswer(false);
    }
  }, [open, docId, fetchData]);

  const handleShowAnswer = () => setShowAnswer(true);

  const handleStatus = (status: 'remembered' | 'unclear') => {
    const card = cards[currentIndex];
    if (!card) return;

    learningService
      .updateFlashcardProgress(docId!, {
        card_index: card.id,
        status,
      })
      .catch(() => {});

    setProgress((prev) => ({ ...prev, [card.id]: status }));
    setShowAnswer(false);

    if (currentIndex < cards.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
      setShowAnswer(false);
    }
  };

  const handleNext = () => {
    if (currentIndex < cards.length - 1) {
      setCurrentIndex(currentIndex + 1);
      setShowAnswer(false);
    }
  };

  const renderContent = () => {
    if (loading) return <Spin size="large" tip="加载闪卡..." />;
    if (error) return <Result status="error" title="加载失败" subTitle={error} />;
    if (!cards.length) return <Empty description="闪卡尚未生成，请等待课件解析完成后重试" />;

    const card = cards[currentIndex];
    const currentStatus = progress[card.id];

    return (
      <div className={styles.flashcardContainer}>
        <div className={styles.progressBar}>
          <Progress percent={Math.round(((currentIndex + 1) / cards.length) * 100)} showInfo={false} />
          <Text type="secondary">{currentIndex + 1} / {cards.length}</Text>
        </div>

        {card.knowledge_point_ids && card.knowledge_point_ids.length > 0 && (
          <div className={styles.kpTags}>
            {card.knowledge_point_ids.map((kp, idx) => (
              <Tag key={idx} color="blue">{kpLabels[kp] || kp}</Tag>
            ))}
          </div>
        )}

        <div className={`${styles.card} ${showAnswer ? styles.flipped : ''}`}>
          <div className={styles.cardFront}>
            <div className={styles.cardQuestion}><MathText text={card.question} /></div>
            {!showAnswer && (
              <Button type="primary" onClick={handleShowAnswer} icon={<QuestionOutlined />}>
                查看答案
              </Button>
            )}
          </div>

          {showAnswer && (
            <div className={styles.cardBack}>
              <div className={styles.cardAnswer}><MathText text={card.answer} /></div>
              <div className={styles.cardActions}>
                <Button
                  type={currentStatus === 'remembered' ? 'primary' : 'default'}
                  icon={<CheckOutlined />}
                  onClick={() => handleStatus('remembered')}
                >
                  记住了
                </Button>
                <Button
                  type={currentStatus === 'unclear' ? 'primary' : 'default'}
                  danger={currentStatus === 'unclear'}
                  onClick={() => handleStatus('unclear')}
                >
                  不清楚
                </Button>
              </div>
            </div>
          )}
        </div>

        <div className={styles.cardNav}>
          <Button onClick={handlePrev} disabled={currentIndex === 0}>
            上一张
          </Button>
          <Button onClick={handleNext} disabled={currentIndex >= cards.length - 1}>
            下一张
          </Button>
        </div>
      </div>
    );
  };

  return (
    <Modal
      title="概念速记"
      open={open}
      onCancel={onClose}
      footer={null}
      width={600}
      destroyOnClose
      centered
    >
      <div className={styles.modalContent}>{renderContent()}</div>
    </Modal>
  );
};

export default FlashcardModal;
