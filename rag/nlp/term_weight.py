#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import logging
import math
import json
import re
import os
import numpy as np
from rag.nlp import rag_tokenizer
from api.utils.file_utils import get_project_base_directory


class Dealer:
    """
    这个 Dealer 类是一个专门为自然语言处理（NLP）设计的 文本预处理器。它的核心目标是接收一段原始文本（通常是用户的查询语句），然后通过一系列复杂的处理步骤，将其转换成一个 带有权重的关键词列表。
    """
    def __init__(self):
        # 初始化了一些停用词
        self.stop_words = set(
            [
                "请问",
                "您",
                "你",
                "我",
                "他",
                "是",
                "的",
                "就",
                "有",
                "于",
                "及",
                "即",
                "在",
                "为",
                "最",
                "有",
                "从",
                "以",
                "了",
                "将",
                "与",
                "吗",
                "吧",
                "中",
                "#",
                "什么",
                "怎么",
                "哪个",
                "哪些",
                "啥",
                "相关",
            ]
        )

        def load_dict(fnm):
            res = {}
            f = open(fnm, "r")
            while True:
                line = f.readline()
                if not line:
                    break
                arr = line.replace("\n", "").split("\t")
                if len(arr) < 2:
                    res[arr[0]] = 0
                else:
                    res[arr[0]] = int(arr[1])

            c = 0
            for _, v in res.items():
                c += v
            if c == 0:
                return set(res.keys())
            return res

        fnm = os.path.join(get_project_base_directory(), "rag/res")
        self.ne, self.df = {}, {}
        try:
            # 读取res下的ner.json文件，但是官方仓库目前不是这些内容
            self.ne = json.load(open(os.path.join(fnm, "ner.json"), "r", encoding="utf-8"))
        except Exception:
            logging.warning("Load ner.json FAIL!")
        try:
            # 没有这个文件
            self.df = load_dict(os.path.join(fnm, "term.freq"))
        except Exception:
            logging.warning("Load term.freq FAIL!")

    def pretoken(self, txt, num=False, stpwd=True):
        """
        这个函数是文本处理的第一步：初步清洗和分词
        就是将一句话，通过分词，然后再处理，形成多个词，并且这些词，英文可以直接得到，中文分出来的都是huqie.txt里面的
        """
        patt = [r"[~—\t @#%!<>,\.\?\":;'\{\}\[\]_=\(\)\|，。？》•●○↓《；‘’：“”【¥ 】…￥！、·（）×`&\\/「」\\]"]
        rewt = []
        # 这个for不会执行，因为没有rewt
        for p, r in rewt:
            txt = re.sub(p, r, txt)

        res = []
        # 使用智能的分词技术先把词给分出来
        for t in rag_tokenizer.tokenize(txt).split():
            tk = t
            # 如果说当前的这个词在我的停用词里面，或者说当前这个是不是单个数字，单个数字1，2什么的就全部干掉
            if (stpwd and tk in self.stop_words) or (re.match(r"[0-9]$", tk) and not num):
                continue
            # 如果这个词，是上面的符号中的任意一个，就把当前这个词变成#
            for p in patt:
                if re.match(p, t):
                    tk = "#"
                    break
            # tk = re.sub(r"([\+\\-])", r"\\\1", tk)
            # 否则的话，我才把当前的这个词加入到结果集里面
            if tk != "#" and tk:
                res.append(tk)
        return res

    def tokenMerge(self, tks):
        """
        用来将pretoken得到的结果再进行两两合并用的
        """
        def oneTerm(t):
            return len(t) == 1 or re.match(r"[0-9a-z]{1,2}$", t)

        res, i = [], 0
        while i < len(tks):
            j = i
            if i == 0 and oneTerm(tks[i]) and len(tks) > 1 and (len(tks[i + 1]) > 1 and not re.match(r"[0-9a-zA-Z]", tks[i + 1])):  # 多 工位
                res.append(" ".join(tks[0:2]))
                i = 2
                continue

            while j < len(tks) and tks[j] and tks[j] not in self.stop_words and oneTerm(tks[j]):
                j += 1
            if j - i > 1:
                if j - i < 5:
                    res.append(" ".join(tks[i:j]))
                    i = j
                else:
                    res.append(" ".join(tks[i : i + 2]))
                    i = i + 2
            else:
                if len(tks[i]) > 0:
                    res.append(tks[i])
                i += 1
        return [t for t in res if t]

    def ner(self, t):
        """
        传入一个词，然后去ner.json中，找到他对应的词性
        """
        if not self.ne:
            return ""
        res = self.ne.get(t, "")
        if res:
            return res

    def split(self, txt):
        """
        特殊分词方法，主要处理连续英文单词的合并
        参数:
            txt: 待分词的文本字符串

        返回:
            处理后的词条列表
        """
        tks = []
        for t in re.sub(r"[ \t]+", " ", txt).split():
            if tks and re.match(r".*[a-zA-Z]$", tks[-1]) and re.match(r".*[a-zA-Z]$", t) and tks and self.ne.get(t, "") != "func" and self.ne.get(tks[-1], "") != "func":
                tks[-1] = tks[-1] + " " + t
            else:
                tks.append(t)
        return tks

    def weights(self, tks, preprocess=True):
        """
        给一些词语进行权重打分
        ['unity3d', '开发', '经验', '测试', '开发', '工程师', 'c 双', '11 双 11', '985', '211']
        得到类似于这种结果
        [('unity3d', 0.11384547679148599), ('开发', 0.10990615630633445), ('经验', 0.10205001616189485), ('测试', 0.10990615630633445), ('开发', 0.10990615630633445), ('工程师', 0.10400160616311792), ('c 双', 0.05836850001524857), ('11 双 11', 0.05836850001524857), ('985', 0.1168237159670004), ('211', 0.1168237159670004)]
        这些得分加起来应该是1
        """
        def skill(t):
            if t not in self.sk:
                return 1
            return 6

        def ner(t):
            """
            主要是对一些实体进行打分，并且还要查询ner.json这些实体都是什么类型的实体
            """
            if re.match(r"[0-9,.]{2,}$", t):
                return 2
            if re.match(r"[a-z]{1,2}$", t):
                return 0.01
            if not self.ne or t not in self.ne:
                return 1
            # firstnm代表姓氏，toxic代表这个词汇是有毒的，stock代表这些词汇都是库存？其他的都没有
            m = {"toxic": 2, "func": 1, "corp": 3, "loca": 3, "sch": 3, "stock": 3, "firstnm": 1}
            return m[self.ne[t]]

        def postag(t):
            """
            给词性进行打分
            """
            # 得到一个词的词性，这个词性在huqie.txt里面的第三列
            t = rag_tokenizer.tag(t)
            
            if t in set(["r", "c", "d"]):
                return 0.3
            if t in set(["ns", "nt"]):
                return 3
            if t in set(["n"]):
                return 2
            if re.match(r"[0-9-]+", t):
                return 2
            return 1

        def freq(t):
            """
            获取一个词的词频，这个词频是从huqie.txt里面的第二列来获取到的
            """
            if re.match(r"[0-9. -]{2,}$", t):
                return 3
            s = rag_tokenizer.freq(t)
            if not s and re.match(r"[a-z. -]+$", t):
                return 300
            if not s:
                s = 0

            if not s and len(t) >= 4:
                s = [tt for tt in rag_tokenizer.fine_grained_tokenize(t).split() if len(tt) > 1]
                if len(s) > 1:
                    s = np.min([freq(tt) for tt in s]) / 6.0
                else:
                    s = 0

            return max(s, 10)

        def df(t):
            """
            文档频率
            词频：一篇文档中出现多少次当前这个词。 词频高，表明这个词在当前文档中比较重要。
            文档频率：一个词在多少篇文章中出现过。  文档频率高，表明这个词在很多文档中都出现过，是一个常用词，低，表示这个词比较稀有


            tf统计的范围是单篇文档。衡量当前这个词在整个语料库中的重要程度
            df统计的是整个语料库。衡量词的普遍性。
            即当前这个词在语料库df中出现的次数越多，越说明当前这个词不重要。
            只有当前这个tf比较高，并且呢，df比较少，才能突出当前这个词的重要性
            """
            if re.match(r"[0-9. -]{2,}$", t):
                return 5
            if t in self.df:
                return self.df[t] + 3
            elif re.match(r"[a-z. -]+$", t):
                return 300
            elif len(t) >= 4:
                s = [tt for tt in rag_tokenizer.fine_grained_tokenize(t).split() if len(tt) > 1]
                if len(s) > 1:
                    return max(3, np.min([df(tt) for tt in s]) / 6.0)

            return 3

        def idf(s, N):
            return math.log10(10 + ((N - s + 0.5) / (s + 0.5)))

        tw = []
        if not preprocess:
            idf1 = np.array([idf(freq(t), 10000000) for t in tks])
            idf2 = np.array([idf(df(t), 1000000000) for t in tks])
            wts = (0.3 * idf1 + 0.7 * idf2) * np.array([ner(t) * postag(t) for t in tks])
            wts = [s for s in wts]
            tw = list(zip(tks, wts))
        else:
            # 循环遍历所有传入的词汇
            for tk in tks:
                tt = self.tokenMerge(self.pretoken(tk, True))
                idf1 = np.array([idf(freq(t), 10000000) for t in tt])
                idf2 = np.array([idf(df(t), 1000000000) for t in tt])
                # 这是一个计算权重的公式，充分考虑了词频，文档频，实体分，词性分这些因素，得到的一个词语的得分
                wts = (0.3 * idf1 + 0.7 * idf2) * np.array([ner(t) * postag(t) for t in tt])
                wts = [s for s in wts]
                tw.extend(zip(tt, wts))

        
        S = np.sum([s for _, s in tw])
        # 最终再进行归一化
        return [(t, s / S) for t, s in tw]

if __name__ == '__main__':
    d = Dealer()
    res = d.pretoken("Unity3D开发经验 测试开发工程师 c++双11双11 985 211 ")
    print(res)
    "['unity3d', '开发', '经验', '测试', '开发', '工程师', 'c', '双', '11', '双', '11', '985', '211']"
    res1 = d.tokenMerge(res)
    print(res1)
    "['unity3d', '开发', '经验', '测试', '开发', '工程师', 'c 双', '11 双 11', '985', '211']"
    res2 = d.weights(res1)
    print(res2)