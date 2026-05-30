# -*- coding: utf-8 -*-
"""
基于 jieba 的简化分词器
支持中英文混合文本分词 + 停用词过滤
"""

import logging
import os
import re

import jieba


# 获取停用词表目录的默认路径
_STOPWORDS_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "stopwords")
_DEFAULT_STOPWORDS_PATH = os.path.join(_STOPWORDS_DIR, "stopwords.txt")


class JiebaTokenizer:
    """简化的 jieba 分词器"""

    def __init__(self, user_dict_path=None, stop_words_path=None):
        """
        初始化分词器

        Args:
            user_dict_path: 用户自定义词典路径（可选）
            stop_words_path: 停用词表路径（可选），默认使用 stopwords/cn_stopwords.txt
        """
        # 如果没有指定停用词表，使用默认的 cn_stopwords.txt
        if stop_words_path is None:
            if os.path.exists(_DEFAULT_STOPWORDS_PATH):
                stop_words_path = _DEFAULT_STOPWORDS_PATH

        # 默认停用词列表（作为后备）
        self.default_stop_words = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一',
            '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有',
            '看', '好', '自己', '这', '那', '里', '就是', '啊', '吗', '吧', '呢', '哦',
            '嗯', '哈', '呀', '哪', '怎么', '为什么', '什么', '如何', 'whether', 'the',
            'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be', 'been', 'being', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may',
            'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he',
            'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your',
            'his', 'its', 'our', 'their'
        }

        # 加载停用词表
        self.stop_words = self.default_stop_words.copy()
        if stop_words_path and os.path.exists(stop_words_path):
            self._load_stop_words(stop_words_path)

        # 加载自定义词典（如果提供）
        if user_dict_path and os.path.exists(user_dict_path):
            jieba.load_userdict(user_dict_path)
            logging.info(f"[JiebaTokenizer] 已加载自定义词典: {user_dict_path}")

        logging.info(f"[JiebaTokenizer] 初始化完成，停用词数量: {len(self.stop_words)}")

    def _load_stop_words(self, filepath):
        """从文件加载停用词表"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                words = set([line.strip() for line in f if line.strip()])
                self.stop_words.update(words)
                logging.info(f"[JiebaTokenizer] 已加载停用词表: {filepath}, 词数: {len(words)}")
        except Exception as e:
            logging.error(f"[JiebaTokenizer] 加载停用词表失败: {e}")

    def _clean_text(self, text):
        """
        预处理文本：全角转半角、转小写
        """
        # 全角转半角
        text = text.replace('　', ' ').replace('，', ',').replace('。', '.')
        text = text.replace('：', ':').replace('；', ';').replace('！', '!').replace('？', '?')
        text = text.replace('（', '(').replace('）', ')').replace('【', '[').replace('】', ']')
        # 全角转半角引号（使用 Unicode 转义）
        text = text.replace('\u201c', '"').replace('\u201d', '"')  # 中文双引号
        text = text.replace('\u2018', "'").replace('\u2019', "'")  # 中文单引号

        # 转小写
        text = text.lower()

        return text

    def tokenize(self, text):
        """
        对文本进行分词，返回用空格分隔的词元字符串

        Args:
            text (str): 待分词的文本

        Returns:
            str: 分词结果，词元之间用空格分隔
        """
        if not text or not isinstance(text, str):
            return ""

        # 预处理
        text = self._clean_text(text)

        # 使用 jieba 分词（精确模式）
        words = jieba.cut(text)

        # 过滤：去掉停用词、空白、纯标点、单个字符
        filtered_words = []
        for word in words:
            word = word.strip()
            # 跳过空字符串
            if not word:
                continue
            # 跳过停用词
            if word in self.stop_words:
                continue
            # 跳过纯标点符号
            if not re.search(r'[\w\u4e00-\u9fa5]', word):
                continue
            # 跳过单个非中文字符（可选）
            if len(word) == 1 and not ('\u4e00' <= word <= '\u9fa5'):
                continue

            filtered_words.append(word)

        return " ".join(filtered_words)

    def tokenize_list(self, text):
        """
        对文本进行分词，返回词元列表

        Args:
            text (str): 待分词的文本

        Returns:
            list: 词元列表
        """
        result = self.tokenize(text)
        return result.split() if result else []


# 全局实例，保持与原 RagTokenizer 相同的使用方式
_tknzr = None


def get_tokenizer(user_dict_path=None, stop_words_path=None):
    """获取全局分词器实例"""
    global _tknzr
    if _tknzr is None:
        _tknzr = JiebaTokenizer(user_dict_path, stop_words_path)
    return _tknzr


# 兼容原 RagTokenizer 的使用方式
def tokenize_text(text):
    """便捷函数：对文本进行分词"""
    return get_tokenizer().tokenize(text)


if __name__ == "__main__":
    # 测试。TODO：是否可以加载user_dict.txt和stopwords.txt
    tknzr = JiebaTokenizer()

    # 测试中文
    test1 = "基于动态视觉相机的光流估计研究"
    print(f"输入: {test1}")
    print(f"输出: {tknzr.tokenize(test1)}")
    print()

    # 测试中英文混合
    test2 = "图3-1 事件流输入表征。（a）事件帧；（b）时间面；（c）体素网格"
    print(f"输入: {test2}")
    print(f"输出: {tknzr.tokenize(test2)}")
    print()

    # 测试英文
    test3 = "This is a test document for tokenization."
    print(f"输入: {test3}")
    print(f"输出: {tknzr.tokenize(test3)}")
