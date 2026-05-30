import Image from '@/components/image';
import SvgIcon from '@/components/svg-icon';
import { IReference, IReferenceChunk } from '@/interfaces/database/chat';
import { getExtension } from '@/utils/document-util';
import { InfoCircleOutlined } from '@ant-design/icons';
import { Button, Flex, Popover, Space } from 'antd';
import DOMPurify from 'dompurify';
import React, { useCallback, useEffect, useMemo } from 'react';
import Markdown from 'react-markdown';
import reactStringReplace from 'react-string-replace';
import SyntaxHighlighter from 'react-syntax-highlighter';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import { visitParents } from 'unist-util-visit-parents';

import { useFetchDocumentThumbnailsByIds } from '@/hooks/document-hooks';
import { useTranslation } from 'react-i18next';

import 'katex/dist/katex.min.css'; // `rehype-katex` does not import the CSS for you

import { preprocessLaTeX, replaceThinkToSection } from '@/utils/chat';
import { replaceTextByOldReg } from '../utils';

import { pipe } from 'lodash/fp';
import styles from './index.less';

const reg = /(~{2}\d+={2})/g;
// const curReg = /(~{2}\d+\${2})/g;

const getChunkIndex = (match: string) => Number(match.slice(2, -2));

// 处理附件内容的函数
const processAttachmentContent = (content: string) => {
  // 匹配 [附件内容]: 后面的内容
  const attachmentRegex = /\[附件内容\]:\s*([\s\S]*?)(?=\n\n(?!\s)|$)/g;

  return content.replace(attachmentRegex, (match, attachmentContent) => {
    // 解析附件内容中的文件信息
    const fileRegex = /文件名:\s*([^\n]+)\n内容:\s*([\s\S]*?)(?=\n文件名:|$)/g;
    let fileMatches;
    let processedContent = '\n\n**📎 附件内容**\n\n';

    while ((fileMatches = fileRegex.exec(attachmentContent)) !== null) {
      const [, filename] = fileMatches;
      processedContent += `**📄 ${filename.trim()}**\n\n`;
    }

    return processedContent;
  });
};

// TODO: The display of the table is inconsistent with the display previously placed in the MessageItem.
const MarkdownContent = ({
  reference,
  clickDocumentButton,
  content,
  loading,
}: {
  content: string;
  loading: boolean;
  reference: IReference;
  clickDocumentButton?: (documentId: string, chunk: IReferenceChunk) => void;
}) => {
  const { t } = useTranslation();
  const { setDocumentIds, data: fileThumbnails } =
    useFetchDocumentThumbnailsByIds();

  // 打字机效果的加载提示
  const [loadingDotCount, setLoadingDotCount] = React.useState(0);

  React.useEffect(() => {
    if (loading && !content) {
      const interval = setInterval(() => {
        setLoadingDotCount((prev) => (prev >= 3 ? 0 : prev + 1));
      }, 500);
      return () => clearInterval(interval);
    }
  }, [loading, content]);

  const contentWithCursor = useMemo(() => {
    let text = content;
    if (text === '') {
      if (loading) {
        const dots = '.'.repeat(loadingDotCount + 1);
        return `<span class="loading-text">正在思考中${dots}</span>`;
      } else {
        text = t('chat.searching');
      }
    }
    const nextText = replaceTextByOldReg(text);
    // 处理附件内容
    const processedText = processAttachmentContent(nextText);
    return pipe(replaceThinkToSection, preprocessLaTeX)(processedText);
  }, [content, t, loading, loadingDotCount]);

  useEffect(() => {
    const docAggs = reference?.doc_aggs;
    setDocumentIds(Array.isArray(docAggs) ? docAggs.map((x) => x.doc_id) : []);
  }, [reference, setDocumentIds]);

  const handleDocumentButtonClick = useCallback(
    (
      documentId: string,
      chunk: IReferenceChunk,
      isPdf: boolean,
      documentUrl?: string,
    ) =>
      () => {
        // 如果 chunk 有 img_url，打开图片模态框
        if (chunk?.img_url) {
          clickDocumentButton?.(documentId, chunk);
          return;
        }
        // 否则如果有 documentUrl，在新窗口打开
        if (documentUrl) {
          window.open(documentUrl, '_blank');
        }
      },
    [clickDocumentButton],
  );

  const rehypeWrapReference = () => {
    return function wrapTextTransform(tree: any) {
      visitParents(tree, 'text', (node, ancestors) => {
        const latestAncestor = ancestors.at(-1);
        if (
          latestAncestor.tagName !== 'custom-typography' &&
          latestAncestor.tagName !== 'code'
        ) {
          node.type = 'element';
          node.tagName = 'custom-typography';
          node.properties = {};
          node.children = [{ type: 'text', value: node.value }];
        }
      });
    };
  };

  const getPopoverContent = useCallback(
    (chunkIndex: number) => {
      const chunks = reference?.chunks ?? [];
      const chunkItem = chunks[chunkIndex];
      const document = reference?.doc_aggs?.find(
        (x) => x?.doc_id === chunkItem?.doc_id,
      );
      const documentId = document?.doc_id;
      const documentUrl = document?.url;
      const fileThumbnail = documentId ? fileThumbnails[documentId] : '';
      const fileExtension = documentId ? getExtension(document?.doc_name) : '';
      const imageId = chunkItem?.image_id;
      const img_url = chunkItem?.img_url;
      return (
        <Flex
          key={chunkItem?.chunk_id}
          gap={10}
          className={styles.referencePopoverWrapper}
        >
          {(imageId || img_url) && (
            <Popover
              placement="left"
              content={
                img_url ? (
                  <img
                    src={img_url}
                    alt="reference"
                    className={styles.referenceImagePreview}
                    style={{ maxWidth: '100%', maxHeight: '400px' }}
                  />
                ) : (
                  <Image
                    id={imageId}
                    className={styles.referenceImagePreview}
                  ></Image>
                )
              }
            >
              {img_url ? (
                <img
                  src={img_url}
                  alt="reference"
                  className={styles.referenceChunkImage}
                  style={{ maxWidth: '200px', maxHeight: '150px', objectFit: 'contain' }}
                />
              ) : (
                <Image
                  id={imageId}
                  className={styles.referenceChunkImage}
                ></Image>
              )}
            </Popover>
          )}
          <Space direction={'vertical'}>
            <div
              dangerouslySetInnerHTML={{
                __html: DOMPurify.sanitize(chunkItem?.content_with_weight ?? chunkItem?.content ?? ''),
              }}
              className={styles.chunkContentText}
            ></div>
            {documentId && (
              <Flex gap={'small'}>
                {fileThumbnail ? (
                  <img
                    src={fileThumbnail}
                    alt=""
                    className={styles.fileThumbnail}
                  />
                ) : (
                  <SvgIcon
                    name={`file-icon/${fileExtension}`}
                    width={24}
                  ></SvgIcon>
                )}
                <Button
                  type="link"
                  className={styles.documentLink}
                  onClick={handleDocumentButtonClick(
                    documentId,
                    chunkItem,
                    fileExtension === 'pdf',
                    documentUrl,
                  )}
                >
                  {document?.doc_name}
                </Button>
              </Flex>
            )}
          </Space>
        </Flex>
      );
    },
    [reference, fileThumbnails, handleDocumentButtonClick],
  );

  const renderReference = useCallback(
    (text: string) => {
      let replacedText = reactStringReplace(text, reg, (match, i) => {
        const chunkIndex = getChunkIndex(match);
        return (
          <Popover content={getPopoverContent(chunkIndex)} key={i}>
            <InfoCircleOutlined className={styles.referenceIcon} />
          </Popover>
        );
      });

      // replacedText = reactStringReplace(replacedText, curReg, (match, i) => (
      //   <span className={styles.cursor} key={i}></span>
      // ));

      return replacedText;
    },
    [getPopoverContent],
  );

  return (
    <Markdown
      rehypePlugins={[rehypeWrapReference, rehypeKatex, rehypeRaw]}
      remarkPlugins={[remarkGfm, remarkMath]}
      className={styles.markdownContentWrapper}
      components={
        {
          'custom-typography': ({ children }: { children: string }) =>
            renderReference(children),
          code(props: any) {
            const { children, className, node, ...rest } = props;
            const match = /language-(\w+)/.exec(className || '');
            return match ? (
              <SyntaxHighlighter {...rest} PreTag="div" language={match[1]}>
                {String(children).replace(/\n$/, '')}
              </SyntaxHighlighter>
            ) : (
              <code {...rest} className={className}>
                {children}
              </code>
            );
          },
        } as any
      }
    >
      {contentWithCursor}
    </Markdown>
  );
};

export default MarkdownContent;
