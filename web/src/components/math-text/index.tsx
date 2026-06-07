import Markdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { preprocessLaTeX } from '@/utils/chat';

import 'katex/dist/katex.min.css';

/** 覆盖 react-markdown 的 p 标签，block 模式保留 <p>，inline 模式去掉 <p> */
const noopParagraph = ({ children }: { children: React.ReactNode }) => <>{children}</>;

/**
 * 渲染含 LaTeX 数学公式的文本
 * @param inline - true 时去掉 <p> 包裹，用于行内场景（如选项标签、说明文字）
 */
const MathText = ({
  text,
  inline,
}: {
  text: string | null | undefined;
  inline?: boolean;
}) => {
  if (!text) return null;
  return (
    <Markdown
      remarkPlugins={[remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={inline ? { p: noopParagraph } : undefined}
    >
      {preprocessLaTeX(text)}
    </Markdown>
  );
};

export default MathText;
