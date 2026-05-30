import { useTranslate } from '@/hooks/common-hooks';
import { useChunkIsTesting } from '@/hooks/knowledge-hooks';
import { Button, Card, Divider, Flex, Form, Input } from 'antd';
import { FormInstance } from 'antd/lib';

import styles from './index.less';

type FieldType = {
  question: string;
};

interface IProps {
  form: FormInstance;
  handleTesting: () => Promise<any>;
}

const TestingControl = ({ form, handleTesting }: IProps) => {
  const question = Form.useWatch('question', { form, preserve: true });
  const loading = useChunkIsTesting();
  const { t } = useTranslate('knowledgeDetails');

  const buttonDisabled =
    !question || (typeof question === 'string' && question.trim() === '');

  return (
    <section className={styles.testingControlWrapper}>
      <div>
        <b>{t('testing')}</b>
      </div>
      <Divider></Divider>
      <section>
        <Form name="testing" layout="vertical" form={form}>
          <Card size="small" title={t('testText')}>
            <Form.Item<FieldType>
              name={'question'}
              rules={[{ required: true, message: t('testTextPlaceholder') }]}
            >
              <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }}></Input.TextArea>
            </Form.Item>
            <Flex justify={'end'}>
              <Button
                type="primary"
                size="small"
                onClick={handleTesting}
                disabled={buttonDisabled}
                loading={loading}
              >
                {t('testingLabel')}
              </Button>
            </Flex>
          </Card>
        </Form>
      </section>
    </section>
  );
};

export default TestingControl;
