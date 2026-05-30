import { BookOpen, Brain, Lightbulb, Sparkles, TrendingUp, Zap } from 'lucide-react';
import styles from './index.less';

const LoginRightPanel = () => {
  return (
    <section className={styles.rightPanel}>
      <div className={styles.rightContent}>
        {/* Logo 和标题 */}
        <div className={styles.brandSection}>
          <div className={styles.logoWrapper}>
            <div className={styles.logoIcon}>
              <Zap className="w-12 h-12 text-yellow-300" />
            </div>
          </div>
          <h1 className={styles.brandTitle}>灵机AI助学平台</h1>
          <p className={styles.brandSubtitle}>智能学习，开启未来</p>
        </div>

        {/* 特性卡片 */}
        <div className={styles.featuresGrid}>
          <div className={styles.featureCard}>
            <div className={styles.featureIcon}>
              <Brain className="w-6 h-6" />
            </div>
            <div className={styles.featureContent}>
              <h3>AI智能对话</h3>
              <p>基于大语言模型的智能问答</p>
            </div>
          </div>

          <div className={styles.featureCard}>
            <div className={styles.featureIcon}>
              <BookOpen className="w-6 h-6" />
            </div>
            <div className={styles.featureContent}>
              <h3>知识库管理</h3>
              <p>高效的文档管理和组织</p>
            </div>
          </div>

          <div className={styles.featureCard}>
            <div className={styles.featureIcon}>
              <Lightbulb className="w-6 h-6" />
            </div>
            <div className={styles.featureContent}>
              <h3>智能推荐</h3>
              <p>个性化的学习内容推荐</p>
            </div>
          </div>

          <div className={styles.featureCard}>
            <div className={styles.featureIcon}>
              <TrendingUp className="w-6 h-6" />
            </div>
            <div className={styles.featureContent}>
              <h3>学习分析</h3>
              <p>可视化的学习数据统计</p>
            </div>
          </div>
        </div>

        {/* 装饰性元素 */}
        <div className={styles.decorativeElements}>
          <Sparkles className={`${styles.sparkle} ${styles.sparkle1}`} />
          <Sparkles className={`${styles.sparkle} ${styles.sparkle2}`} />
          <Sparkles className={`${styles.sparkle} ${styles.sparkle3}`} />
        </div>
      </div>
    </section>
  );
};

export default LoginRightPanel;
