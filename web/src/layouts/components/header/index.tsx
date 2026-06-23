import { ReactComponent as KnowledgeBaseIcon } from '@/assets/svg/knowledge-base.svg';
import { ReactComponent as TeachingAssistantIcon } from '@/assets/svg/teaching-assistant.svg';
import { ReactComponent as DeepResearchIcon } from '@/assets/svg/deep-research.svg';
import { ReactComponent as WriteIcon } from '@/assets/svg/write.svg';
import { useTranslate } from '@/hooks/common-hooks';
import { useFetchAppConf } from '@/hooks/logic-hooks';
import { useNavigateWithFromState } from '@/hooks/route-hook';
import { SearchOutlined } from '@ant-design/icons';
import { Flex, Layout, Radio, Space, theme } from 'antd';
import { MouseEventHandler, useCallback, useMemo } from 'react';
import { useLocation } from 'umi';
import Toolbar from '../right-toolbar';

import { useTheme } from '@/components/theme-provider';
import styles from './index.less';

const { Header } = Layout;

const RagHeader = () => {
  const {
    token: { colorBgContainer },
  } = theme.useToken();
  const navigate = useNavigateWithFromState();
  const { pathname } = useLocation();
  const { t } = useTranslate('header');
  const appConf = useFetchAppConf();
  const { theme: themeRag } = useTheme();
  const tagsData = useMemo(
    () => [
      { path: '/teaching-assistant', name: t('teachingAssistant'), icon: TeachingAssistantIcon },
      { path: '/deep-research', name: t('deepResearch'), icon: DeepResearchIcon },
      { path: '/knowledge', name: t('knowledgeBase'), icon: KnowledgeBaseIcon },
      // { path: '/write', name: t('write'), icon: WriteIcon },
      // { path: '/search', name: t('search'), icon: SearchOutlined },
    ],
    [t],
  );

  const currentPath = useMemo(() => {
    // 聊天和学习页面都属于助教
    if (pathname.startsWith('/chat') || pathname.startsWith('/learning')) {
      return t('teachingAssistant');
    }
    return (
      tagsData.find((x) => pathname.startsWith(x.path))?.name || 'knowledge'
    );
  }, [pathname, tagsData, t]);

  const handleChange = useCallback(
    (path: string): MouseEventHandler =>
      (e) => {
        e.preventDefault();
        navigate(path);
      },
    [navigate],
  );

  const handleLogoClick = useCallback(() => {
    navigate('/teaching-assistant');
  }, [navigate]);

  return (
    <Header
      style={{
        padding: '0 16px',
        background: colorBgContainer,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        height: '72px',
      }}
    >
      <a>
        <Space
          size={12}
          onClick={handleLogoClick}
          className={styles.logoWrapper}
        >
          <img src="/logo.svg" alt="" className={styles.appIcon} />
        </Space>
      </a>
      <Space size={[0, 8]} wrap className={styles.centerNav}>
        <Radio.Group
          defaultValue="a"
          buttonStyle="solid"
          className={
            themeRag === 'dark' ? styles.radioGroupDark : styles.radioGroup
          }
          value={currentPath}
        >
          {tagsData.map((item, index) => (
            <Radio.Button
              className={`${themeRag === 'dark' ? 'dark' : 'light'} ${index === 0 ? 'first' : ''} ${index === tagsData.length - 1 ? 'last' : ''}`}
              value={item.name}
              key={item.name}
            >
              <a href={item.path}>
                <Flex
                  align="center"
                  gap={8}
                  onClick={handleChange(item.path)}
                  className="cursor-pointer"
                >
                  <item.icon
                    className={styles.radioButtonIcon}
                    stroke={item.name === currentPath ? 'black' : 'white'}
                  ></item.icon>
                  {item.name}
                </Flex>
              </a>
            </Radio.Button>
          ))}
        </Radio.Group>
      </Space>
      <Toolbar></Toolbar>
    </Header>
  );
};

export default RagHeader;
