
import logging
import re
import math
import base64 as base64_module
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from rag.settings import TAG_FLD, PAGERANK_FLD
from rag.utils import rmSpace
from rag.nlp import rag_tokenizer, query
import numpy as np
from rag.utils.doc_store_conn import DocStoreConnection, MatchDenseExpr, FusionExpr, OrderByExpr
from rag.utils.minio_conn import MINIO


def index_name(uid):
    return f"ragflow_{uid}"


def tenant_id_from_index(index_name: str) -> str:
    """
    从 ES 索引名中提取 tenant_id

    参数:
        index_name: ES 索引名，格式为 "ragflow_{tenant_id}"

    返回:
        tenant_id: 租户ID，如果无法提取则返回空字符串
    """
    if not index_name or not index_name.startswith("ragflow_"):
        return ""
    return index_name.replace("ragflow_", "", 1)


def convert_minio_url_to_base64(image_url: str) -> str:
    """
    将 MinIO URL 转换为 base64 data URL

    参数:
        image_url: MinIO 图片 URL，格式为 minio://bucket/path/to/image.jpg

    返回:
        base64 data URL，格式为 data:image/jpeg;base64,...
        如果转换失败返回空字符串
    """
    if not image_url or not image_url.startswith("minio://"):
        return ""

    try:
        # 解析 bucket 和 object 路径
        path_without_protocol = image_url[8:]  # 移除 "minio://"
        parts = path_without_protocol.split('/', 1)
        if len(parts) != 2:
            logging.error(f"Invalid MinIO URL format: {image_url}")
            return ""

        bucket_name = parts[0]
        object_name = parts[1]

        # 从 MinIO 获取图片数据
        image_data = MINIO.get(bucket_name, object_name)
        if not image_data:
            logging.error(f"Failed to get image from MinIO: {image_url}")
            return ""

        # 转换为 base64
        base64_image = base64_module.b64encode(image_data).decode('utf-8')

        # 根据文件扩展名确定 MIME 类型
        ext = object_name.lower().split('.')[-1]
        mime_type_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'bmp': 'image/bmp'
        }
        mime_type = mime_type_map.get(ext, 'image/jpeg')

        # 构建data URL
        return f"data:{mime_type};base64,{base64_image}"

    except Exception as e:
        logging.error(f"Failed to convert MinIO URL to base64: {image_url}, error: {e}")
        return ""


# 这个类其实就是检索器的类
# 这个类的整个前端，接受别人参数的函数，就是retrieval函数
# 第二个比较重要的函数，就是search函数
class Dealer:
    def __init__(self, dataStore: DocStoreConnection):
        self.qryr = query.FulltextQueryer()
        self.dataStore = dataStore

    # 这是一个查询结果，最后用来返回的
    @dataclass
    class SearchResult:
        total: int
        ids: list[str]
        query_vector: list[float] | None = None
        field: dict | None = None
        highlight: dict | None = None
        aggregation: list | dict | None = None
        keywords: list[str] | None = None
        group_docs: list[list] | None = None

    # 这个是用来做向量检索的
    def get_vector(self, txt, emb_mdl, topk=10, similarity=0.1):
        """
        txt：就是用户输入的问题，这里的问题还是原汁原味的问题，没有进行任何的改写
        emb_mdl: 嵌入模型
        """
        qv, _ = emb_mdl.encode_queries(txt)
        shape = np.array(qv).shape
        if len(shape) > 1:
            raise Exception(f"Dealer.get_vector returned array's shape {shape} doesn't match expectation(exact one dimension).")
        # 全部转化为浮点数
        embedding_data = [float(v) for v in qv]
        # 得到嵌入纬度信息
        vector_column_name = f"image_{len(embedding_data)}_vec"
        return MatchDenseExpr(vector_column_name, embedding_data, "float", "cosine", topk, {"similarity": similarity})

    def get_filters(self, req):
        """
        构建过滤条件（注意：kb_id 通过 knowledgebaseIds 参数传递，不在这里处理）
        """
        condition = dict()
        # 只处理 doc_ids 参数（kb_ids 已通过专门的参数传递）
        if "doc_ids" in req and req["doc_ids"] is not None:
            condition["doc_id"] = req["doc_ids"]
        # TODO(yzc): `available_int` is nullable however infinity doesn't support nullable columns.
        for key in ["knowledge_graph_kwd", "available_int", "entity_kwd", "from_entity_kwd", "to_entity_kwd", "removed_kwd"]:
            if key in req and req[key] is not None:
                condition[key] = req[key]
        # 到这里的结果大概率就是{"doc_id":[xxx,xxx], "available_int": 1}
        return condition

    def search(self, req, idx_names: str | list[str], kb_ids: list[str], emb_mdl=None, highlight=False, rank_feature: dict | None = None):
        """
        这是原本的检索方法
        """
        # 1. 初始化过滤条件和排序规则
        filters = self.get_filters(req)
        # 初始化一个空的排序对象
        orderBy = OrderByExpr()

        # 2. 处理分页参数
        pg = int(req.get("page", 1)) - 1 # 0
        topk = int(req.get("topk", 1024)) # 1024
        ps = int(req.get("size", topk)) # 64
        offset, limit = pg * ps, ps # 其实位置是0，数量是64

        # 3. 设置返回字段（只返回索引中实际存在的字段）
        src = req.get(
            "fields",
            [
                "page_id", # 哪个页面
                "doc_id", # 哪个文档
                "kb_id", # 哪个知识库
                "docnm_kwd", # 所属文档的名字
                "content_with_weight", # 这个页面中的ocr文字信息
                "content_ltks", # 这个ocr文字的分词
                "page_num_int", # 页面在文档中的页码
                "create_time", # 创建时间
                "create_timestamp_flt", # 创建时间戳
                "img_url", # 页面在minio中的url，例如"minio://502b3174fd1711f0bc0e420839d2c59b/39c07d0c3b3011f1984c420839d2c59a/pages/0034.jpg"
                "text_2048_vec",  # 文本向量
                "image_2048_vec",  # 图片向量
            ],
        )
        kwds = set([])  # 初始化关键词集合

        # 4. 处理查询问题
        qst = req.get("question", "")  # 获取查询问题文本
        print(f"收到前端问题：{qst}")
        q_vec = []  # 初始化查询向量（如需向量检索）
        if not qst:
            # 4.1 若查询文本为空，执行默认排序检索（通常用于无搜索条件浏览）(注：前端测试检索时会禁止空文本的提交)
            if req.get("sort"):
                orderBy.asc("page_num_int")
                orderBy.asc("top_int")
                orderBy.desc("create_timestamp_flt")
            res = self.dataStore.search(src, [], filters, [], orderBy, offset, limit, idx_names, kb_ids)
            total = self.dataStore.getTotal(res)
            logging.debug("Dealer.search TOTAL: {}".format(total))
        else:
            # 4.2 若存在查询文本，进入全文/混合检索流程
            highlightFields = ["content_ltks", "title_tks"] if highlight else []  # highlight当前会一直为False，不起作用
            # 4.2.1 生成全文检索表达式和关键词，这里对问题进行分词，然后得到一个问题的一些关键词，并且给每个分配了一些权重信息，得到了一个权重表达式吗？
            matchText, keywords = self.qryr.question(qst, min_match=0.3)
            # 得到一个表达式类，和这个表达式类里面的关键词信息

            if emb_mdl is None:
                # 4.2.2 纯全文检索模式 （未提供向量模型，正常情况不会进入）
                matchExprs = [matchText]
                res = self.dataStore.search(src, highlightFields, filters, matchExprs, orderBy, offset, limit, idx_names, kb_ids, rank_feature=rank_feature)
                total = self.dataStore.getTotal(res)
                logging.debug("Dealer.search TOTAL: {}".format(total))
            else:
                # 4.2.3 混合检索模式（全文+向量）
                # 生成查询向量（什么叫做商品的价值，emb，64，0.2）
                # 这里得到一个向量的表达式类
                matchDense = self.get_vector(qst, emb_mdl, topk, req.get("similarity", 0.1))
                # 查询向量的纬度
                q_vec = matchDense.embedding_data
                # 在返回字段中加入查询向量字段
                src.append(f"image_{len(q_vec)}_vec")
                # 创建融合表达式：设置向量匹配为95%，全文为5%
                # 这是一个实例化的类，第一个参数是融合方法，第二个参数是1024，第三个参数是融合参数
                fusionExpr = FusionExpr("weighted_sum", topk, {"weights": "0.05, 0.95"})
                # 构建混合查询表达式，这个matchText, matchDense, fusionExpr反正都是实现类，具体的类在rag.utils.es_conn下面
                # 这这三个表达式类放到一个列表中
                matchExprs = [matchText, matchDense, fusionExpr]

                # 执行混合检索
                # 其实在混合检索之前，我可以去做一次假设性文档嵌入，让llm先帮我生成一个答案，然后我再去检索
                res = self.dataStore.search(src, highlightFields, filters, matchExprs, orderBy, offset, limit, idx_names, kb_ids, rank_feature=rank_feature)

                total = self.dataStore.getTotal(res)
                logging.debug("Dealer.search TOTAL: {}".format(total))

                print(f"共查询到: {total} 条信息")
                # print(f"查询信息结果: {res}\n")

                # 若未找到结果，则尝试降低匹配门槛后重试
                if total == 0:
                    if filters.get("doc_id"):
                        # 有特定文档ID时执行无条件查询
                        res = self.dataStore.search(src, [], filters, [], orderBy, offset, limit, idx_names, kb_ids)
                        total = self.dataStore.getTotal(res)
                        print(f"针对选中文档，共查询到: {total} 条信息")
                        # print(f"查询信息结果: {res}\n")
                    else:
                        # 否则调整全文和向量匹配参数再次搜索
                        matchText, _ = self.qryr.question(qst, min_match=0.1)
                        filters.pop("doc_id", None)
                        matchDense.extra_options["similarity"] = 0.17
                        res = self.dataStore.search(src, highlightFields, filters, [matchText, matchDense, fusionExpr], orderBy, offset, limit, idx_names, kb_ids, rank_feature=rank_feature)
                        total = self.dataStore.getTotal(res)
                        logging.debug("Dealer.search 2 TOTAL: {}".format(total))
                        print(f"再次查询，共查询到: {total} 条信息")
                        # print(f"查询信息结果: {res}\n")

            # 4.3 处理关键词（对关键词进行更细粒度的切词）
            for k in keywords:
                kwds.add(k)
                for kk in rag_tokenizer.fine_grained_tokenize(k).split():
                    if len(kk) < 2:
                        continue
                    if kk in kwds:
                        continue
                    kwds.add(kk)

        # 5. 提取检索结果中的ID、字段、聚合和高亮信息
        logging.debug(f"TOTAL: {total}")
        ids = self.dataStore.getChunkIds(res)  # 提取匹配chunk的ID
        keywords = list(kwds)  # 转为列表格式返回
        highlight = self.dataStore.getHighlight(res, keywords, "content_with_weight")  # 获取高亮内容
        aggs = self.dataStore.getAggregation(res, "docnm_kwd")  # 执行基于文档名的聚合分析
        return self.SearchResult(total=total, ids=ids, query_vector=q_vec, aggregation=aggs, highlight=highlight, field=self.dataStore.getFields(res, src), keywords=keywords)

    @staticmethod
    def trans2floats(txt):
        return [float(t) for t in txt.split("\t")]

    def insert_citations(self, answer, chunks, chunk_v, embd_mdl, tkweight=0.1, vtweight=0.9):
        assert len(chunks) == len(chunk_v)
        if not chunks:
            return answer, set([])
        pieces = re.split(r"(```)", answer)
        if len(pieces) >= 3:
            i = 0
            pieces_ = []
            while i < len(pieces):
                if pieces[i] == "```":
                    st = i
                    i += 1
                    while i < len(pieces) and pieces[i] != "```":
                        i += 1
                    if i < len(pieces):
                        i += 1
                    pieces_.append("".join(pieces[st:i]) + "\n")
                else:
                    pieces_.extend(re.split(r"([^\|][；。？!！\n]|[a-z][.?;!][ \n])", pieces[i]))
                    i += 1
            pieces = pieces_
        else:
            pieces = re.split(r"([^\|][；。？!！\n]|[a-z][.?;!][ \n])", answer)
        for i in range(1, len(pieces)):
            if re.match(r"([^\|][；。？!！\n]|[a-z][.?;!][ \n])", pieces[i]):
                pieces[i - 1] += pieces[i][0]
                pieces[i] = pieces[i][1:]
        idx = []
        pieces_ = []
        for i, t in enumerate(pieces):
            if len(t) < 5:
                continue
            idx.append(i)
            pieces_.append(t)
        logging.debug("{} => {}".format(answer, pieces_))
        if not pieces_:
            return answer, set([])

        ans_v, _ = embd_mdl.encode(pieces_)
        for i in range(len(chunk_v)):
            if len(ans_v[0]) != len(chunk_v[i]):
                chunk_v[i] = [0.0] * len(ans_v[0])
                logging.warning("The dimension of query and chunk do not match: {} vs. {}".format(len(ans_v[0]), len(chunk_v[i])))

        assert len(ans_v[0]) == len(chunk_v[0]), "The dimension of query and chunk do not match: {} vs. {}".format(len(ans_v[0]), len(chunk_v[0]))

        chunks_tks = [rag_tokenizer.tokenize(self.qryr.rmWWW(ck)).split() for ck in chunks]
        cites = {}
        thr = 0.63
        while thr > 0.3 and len(cites.keys()) == 0 and pieces_ and chunks_tks:
            for i, a in enumerate(pieces_):
                sim, tksim, vtsim = self.qryr.hybrid_similarity(ans_v[i], chunk_v, rag_tokenizer.tokenize(self.qryr.rmWWW(pieces_[i])).split(), chunks_tks, tkweight, vtweight)
                mx = np.max(sim) * 0.99
                logging.debug("{} SIM: {}".format(pieces_[i], mx))
                if mx < thr:
                    continue
                cites[idx[i]] = list(set([str(ii) for ii in range(len(chunk_v)) if sim[ii] > mx]))[:4]
            thr *= 0.8

        res = ""
        seted = set([])
        for i, p in enumerate(pieces):
            res += p
            if i not in idx:
                continue
            if i not in cites:
                continue
            for c in cites[i]:
                assert int(c) < len(chunk_v)
            for c in cites[i]:
                if c in seted:
                    continue
                res += f" ##{c}$$"
                seted.add(c)

        return res, seted

    def _rank_feature_scores(self, query_rfea, search_res):
        ## For rank feature(tag_fea) scores.
        rank_fea = []
        pageranks = []
        for chunk_id in search_res.ids:
            pageranks.append(search_res.field[chunk_id].get(PAGERANK_FLD, 0))
        pageranks = np.array(pageranks, dtype=float)

        if not query_rfea:
            return np.array([0 for _ in range(len(search_res.ids))]) + pageranks

        q_denor = np.sqrt(np.sum([s * s for t, s in query_rfea.items() if t != PAGERANK_FLD]))
        for i in search_res.ids:
            nor, denor = 0, 0
            for t, sc in eval(search_res.field[i].get(TAG_FLD, "{}")).items():
                if t in query_rfea:
                    nor += query_rfea[t] * sc
                denor += sc * sc
            if denor == 0:
                rank_fea.append(0)
            else:
                rank_fea.append(nor / np.sqrt(denor) / q_denor)
        return np.array(rank_fea) * 10.0 + pageranks

    def rerank(self, sres, query, tkweight=0.3, vtweight=0.7, cfield="content_ltks", rank_feature: dict | None = None):
        """
        对初步检索到的结果 (sres) 进行重排序。

        该方法结合了多种相似度/特征来计算每个结果的新排序分数：
        1. 文本相似度 (Token Similarity): 基于查询关键词与文档内容的词元匹配。
        2. 向量相似度 (Vector Similarity): 基于查询向量与文档向量的余弦相似度。
        3. 排序特征分数 (Rank Feature Scores): 如文档的 PageRank 值或与查询相关的标签特征得分。

        最终的排序分数是这几种分数的加权组合（或直接相加）。

        Args:
            sres (SearchResult): 初步检索的结果对象，包含查询向量、文档ID、字段内容等。
            query (str): 原始用户查询字符串。
            tkweight (float): 文本相似度在混合相似度计算中的权重。
            vtweight (float): 向量相似度在混合相似度计算中的权重。
            cfield (str): 用于提取主要文本内容以进行词元匹配的字段名，默认为 "content_ltks"。
            rank_feature (dict | None): 用于计算排序特征分数的查询侧特征，
                                        例如 {PAGERANK_FLD: 10} 表示 PageRank 权重，
                                        或包含其他标签及其权重的字典。

        Returns:
            tuple[np.ndarray, np.ndarray, np.ndarray]:
                - sim (np.ndarray): 每个文档的最终重排序分数 (混合相似度 + 排序特征分数)。
                - tksim (np.ndarray): 每个文档的纯文本相似度分数。
                - vtsim (np.ndarray): 每个文档的纯向量相似度分数。
                如果初步检索结果为空 (sres.ids is empty)，则返回三个空列表。
        """
        _, keywords = self.qryr.question(query)
        vector_size = len(sres.query_vector)
        vector_column = f"image_{vector_size}_vec"
        zero_vector = [0.0] * vector_size
        ins_embd = []
        for chunk_id in sres.ids:
            vector = sres.field[chunk_id].get(vector_column, zero_vector)
            if isinstance(vector, str):
                vector = [float(v) for v in vector.split("\t")]
            ins_embd.append(vector)
        if not ins_embd:
            return [], [], []

        for i in sres.ids:
            if isinstance(sres.field[i].get("important_kwd", []), str):
                sres.field[i]["important_kwd"] = [sres.field[i]["important_kwd"]]
        ins_tw = []
        for i in sres.ids:
            content_ltks = sres.field[i][cfield].split()
            title_tks = [t for t in sres.field[i].get("title_tks", "").split() if t]
            question_tks = [t for t in sres.field[i].get("question_tks", "").split() if t]
            important_kwd = sres.field[i].get("important_kwd", [])
            tks = content_ltks + title_tks * 2 + important_kwd * 5 + question_tks * 6
            ins_tw.append(tks)

        ## For rank feature(tag_fea) scores.
        rank_fea = self._rank_feature_scores(rank_feature, sres)

        sim, tksim, vtsim = self.qryr.hybrid_similarity(sres.query_vector, ins_embd, keywords, ins_tw, tkweight, vtweight)

        return sim + rank_fea, tksim, vtsim

    def rerank_by_model(self, rerank_mdl, sres, query, tkweight=0.3, vtweight=0.7, cfield="content_ltks", rank_feature: dict | None = None):
        _, keywords = self.qryr.question(query)

        for i in sres.ids:
            if isinstance(sres.field[i].get("important_kwd", []), str):
                sres.field[i]["important_kwd"] = [sres.field[i]["important_kwd"]]
        ins_tw = []
        for i in sres.ids:
            content_ltks = sres.field[i][cfield].split()
            title_tks = [t for t in sres.field[i].get("title_tks", "").split() if t]
            important_kwd = sres.field[i].get("important_kwd", [])
            tks = content_ltks + title_tks + important_kwd
            ins_tw.append(tks)

        tksim = self.qryr.token_similarity(keywords, ins_tw)
        vtsim, _ = rerank_mdl.similarity(query, [rmSpace(" ".join(tks)) for tks in ins_tw])
        ## For rank feature(tag_fea) scores.
        rank_fea = self._rank_feature_scores(rank_feature, sres)

        return tkweight * (np.array(tksim) + rank_fea) + vtweight * vtsim, tksim, vtsim

    def hybrid_similarity(self, ans_embd, ins_embd, ans, inst):
        return self.qryr.hybrid_similarity(ans_embd, ins_embd, rag_tokenizer.tokenize(ans).split(), rag_tokenizer.tokenize(inst).split())

    def retrieval(
        self,
        question,
        embd_mdl,
        tenant_ids,
        kb_ids,
        page,
        page_size,
        similarity_threshold=0.2,
        vector_similarity_weight=0.3,
        top=1024,
        aggs=True,
        rerank_mdl=None,
        highlight=False,
        rank_feature: dict | None = {PAGERANK_FLD: 10}, # {pagerank_fea:10}
    ):
        # print('@'*80)
        # print('retrieval函数接收到请求参数')
        # print('问题', question)
        # print('embd_mdl', embd_mdl)
        # print('tenant_ids', tenant_ids)
        # print('kb_ids', kb_ids)
        # print('page', page)
        # print('page_size', page_size)
        # print('similarity_threshold', similarity_threshold)
        # print('vector_similarity_weight', vector_similarity_weight)
        # print('top', top)
        # print('aggs', aggs)
        # print('rerank_mdl', rerank_mdl)
        # print('highlight',highlight)
        # print('rank_feature',rank_feature)
        """
        执行检索操作，根据问题查询相关文档片段

        参数说明:
        - question: 用户输入的查询问题
        - embd_mdl: 嵌入模型，用于将文本转换为向量
        - tenant_ids: 租户ID，可以是字符串或列表
        - kb_ids: 知识库ID列表
        - page: 当前页码
        - page_size: 每页结果数量
        - similarity_threshold: 相似度阈值，低于此值的结果将被过滤
        - vector_similarity_weight: 向量相似度权重
        - top: 检索的最大结果数
        - aggs: 是否聚合文档信息
        - rerank_mdl: 重排序模型
        - highlight: 是否高亮匹配内容
        - rank_feature: 排序特征，如PageRank值

        返回:
        包含检索结果的字典，包括总数、文档片段和文档聚合信息
        """
        # 初始化结果字典
        ranks = {"total": 0, "chunks": [], "doc_aggs": {}}
        if not question:
            return ranks
        # 设置重排序页面限制
        RERANK_LIMIT = 64
        # 64/8 + （64%8/8+0.5）
        RERANK_LIMIT = int(RERANK_LIMIT // page_size + ((RERANK_LIMIT % page_size) / (page_size * 1.0) + 0.5)) * page_size if page_size > 1 else 1
        if RERANK_LIMIT < 1:
            RERANK_LIMIT = 1
        # 构建检索请求参数
        req = {
            "kb_ids": kb_ids,
            "page": math.ceil(page_size * page / RERANK_LIMIT),
            "size": RERANK_LIMIT,
            "question": question,
            "vector": True,
            "topk": top,
            "similarity": similarity_threshold,
            "available_int": 1,
        }

        # 处理租户ID格式
        if isinstance(tenant_ids, str):
            tenant_ids = tenant_ids.split(",")

        # 执行搜索操作
        sres = self.search(req, [index_name(tid) for tid in tenant_ids], kb_ids, embd_mdl, highlight, rank_feature=rank_feature)

        # 执行重排序操作，默认情况下是没有充排序的
        if rerank_mdl and sres.total > 0:
            sim, tsim, vsim = self.rerank_by_model(rerank_mdl, sres, question, 1 - vector_similarity_weight, vector_similarity_weight, rank_feature=rank_feature)
        else:
            # 执行自定义的重排序吗？
            sim, tsim, vsim = self.rerank(sres, question, 1 - vector_similarity_weight, vector_similarity_weight, rank_feature=rank_feature)
        # Already paginated in search function
        idx = np.argsort(sim * -1)[(page - 1) * page_size : page * page_size]

        dim = len(sres.query_vector)
        vector_column = f"image_{dim}_vec"
        zero_vector = [0.0] * dim
        sim_np = np.array(sim)
        filtered_count = (sim_np >= similarity_threshold).sum()
        ranks["total"] = int(filtered_count)  # Convert from np.int64 to Python int otherwise JSON serializable error
        for i in idx:
            if sim[i] < similarity_threshold:
                break
            if len(ranks["chunks"]) >= page_size:
                if aggs:
                    continue
                break
            id = sres.ids[i]
            chunk = sres.field[id]
            dnm = chunk.get("docnm_kwd", "")
            did = chunk.get("doc_id", "")
            position_int = chunk.get("position_int", [])
            d = {
                "chunk_id": id,
                "content_ltks": chunk["content_ltks"],
                "content_with_weight": chunk["content_with_weight"],
                "doc_id": did,
                "docnm_kwd": dnm,
                "kb_id": chunk["kb_id"],
                "important_kwd": chunk.get("important_kwd", []),
                "image_id": chunk.get("img_id", ""),
                "similarity": sim[i],
                "vector_similarity": vsim[i],
                "term_similarity": tsim[i],
                "vector": chunk.get(vector_column, zero_vector),
                "positions": position_int,
                "doc_type_kwd": chunk.get("doc_type_kwd", ""),
            }
            if highlight and sres.highlight:
                if id in sres.highlight:
                    d["highlight"] = rmSpace(sres.highlight[id])
                else:
                    d["highlight"] = d["content_with_weight"]
            ranks["chunks"].append(d)
            if dnm not in ranks["doc_aggs"]:
                ranks["doc_aggs"][dnm] = {"doc_id": did, "count": 0}
            ranks["doc_aggs"][dnm]["count"] += 1
        ranks["doc_aggs"] = [{"doc_name": k, "doc_id": v["doc_id"], "count": v["count"]} for k, v in sorted(ranks["doc_aggs"].items(), key=lambda x: x[1]["count"] * -1)]
        ranks["chunks"] = ranks["chunks"][:page_size]

        return ranks

    def page_retrieval(
        self,
        question,
        embd_mdl,
        tenant_ids,
        kb_ids,
        page,
        page_size,
        similarity_threshold=0.2,
        vector_similarity_weight=0.3,
        top=1024,
        aggs=True,
        rerank_mdl=None,
        highlight=False,
        rank_feature: dict | None = {PAGERANK_FLD: 10},
    ):
        """
        基于文档页面的检索方法

        与普通检索不同，这个方法会：
        1. 检索时以页面为单位而不是chunk
        2. 返回完整的页面内容和页面图片
        3. 按页面进行聚合和排序

        参数说明:
        - question: 用户输入的查询问题
        - embd_mdl: 嵌入模型，用于将文本转换为向量
        - tenant_ids: 租户ID，可以是字符串或列表
        - kb_ids: 知识库ID列表
        - page: 当前页码
        - page_size: 每页结果数量
        - similarity_threshold: 相似度阈值
        - vector_similarity_weight: 向量相似度权重
        - top: 检索的最大结果数
        - aggs: 是否聚合文档信息
        - rerank_mdl: 重排序模型
        - highlight: 是否高亮匹配内容
        - rank_feature: 排序特征

        返回:
        包含检索结果的字典，包括总数、页面信息和文档聚合信息
        """
        print('@'*80)
        print('page_retrieval函数接收到请求参数')
        print('问题', question)
        print('使用页面检索模式')
        
        # 初始化结果字典
        ranks = {"total": 0, "chunks": [], "doc_aggs": {}}
        if not question:
            return ranks
            
        # 设置重排序页面限制
        RERANK_LIMIT = 64
        RERANK_LIMIT = int(RERANK_LIMIT // page_size + ((RERANK_LIMIT % page_size) / (page_size * 1.0) + 0.5)) * page_size if page_size > 1 else 1
        if RERANK_LIMIT < 1:
            RERANK_LIMIT = 1
            
        # 构建检索请求参数
        req = {
            "kb_ids": kb_ids,
            "page": math.ceil(page_size * page / RERANK_LIMIT),
            "size": RERANK_LIMIT,
            "question": question,
            "vector": True,
            "topk": top,
            "similarity": similarity_threshold,
            "available_int": 1,
        }

        # 处理租户ID格式
        if isinstance(tenant_ids, str):
            tenant_ids = tenant_ids.split(",")

        # 执行搜索操作
        sres = self.search(req, [index_name(tid) for tid in tenant_ids], kb_ids, embd_mdl, highlight, rank_feature=rank_feature)

        # 执行重排序操作
        if rerank_mdl and sres.total > 0:
            sim, tsim, vsim = self.rerank_by_model(rerank_mdl, sres, question, 1 - vector_similarity_weight, vector_similarity_weight, rank_feature=rank_feature)
        else:
            sim, tsim, vsim = self.rerank(sres, question, 1 - vector_similarity_weight, vector_similarity_weight, rank_feature=rank_feature)
            
        # 按页面聚合结果
        page_scores = {}  # {(doc_id, page_num): {"score": max_score, "chunks": [chunk_indices]}}
        
        for i, chunk_id in enumerate(sres.ids):
            if sim[i] < similarity_threshold:
                continue
                
            chunk = sres.field[chunk_id]
            doc_id = chunk.get("doc_id", "")
            page_nums = chunk.get("page_num_int", [])
            
            # 如果没有页码信息，跳过
            if not page_nums:
                continue
                
            # 对于每个页码，记录该chunk
            for page_num in page_nums:
                page_key = (doc_id, page_num)
                
                if page_key not in page_scores:
                    page_scores[page_key] = {
                        "score": sim[i],
                        "vsim": vsim[i],
                        "tsim": tsim[i],
                        "chunk_indices": [i],
                        "doc_id": doc_id,
                        "page_num": page_num,
                        "docnm_kwd": chunk.get("docnm_kwd", ""),
                        "kb_id": chunk.get("kb_id", ""),
                    }
                else:
                    # 更新页面得分（取最高分）
                    page_scores[page_key]["score"] = max(page_scores[page_key]["score"], sim[i])
                    page_scores[page_key]["vsim"] = max(page_scores[page_key]["vsim"], vsim[i])
                    page_scores[page_key]["tsim"] = max(page_scores[page_key]["tsim"], tsim[i])
                    page_scores[page_key]["chunk_indices"].append(i)
        
        # 按得分排序页面
        sorted_pages = sorted(page_scores.items(), key=lambda x: x[1]["score"], reverse=True)
        
        # 分页
        start_idx = (page - 1) * page_size
        end_idx = page * page_size
        paginated_pages = sorted_pages[start_idx:end_idx]
        
        ranks["total"] = len(sorted_pages)
        
        dim = len(sres.query_vector)
        vector_column = f"image_{dim}_vec"
        zero_vector = [0.0] * dim
        
        # 构建返回结果
        for page_key, page_info in paginated_pages:
            doc_id = page_info["doc_id"]
            page_num = page_info["page_num"]
            
            # 收集该页面的所有chunk内容
            page_contents = []
            img_url = ""
            position_int = []
            
            for chunk_idx in page_info["chunk_indices"]:
                chunk_id = sres.ids[chunk_idx]
                chunk = sres.field[chunk_id]
                page_contents.append(chunk.get("content_with_weight", ""))
                
                # 获取图片URL（如果有）
                if not img_url and chunk.get("img_url"):
                    img_url = chunk.get("img_url", "")
                    
                # 收集位置信息
                if chunk.get("position_int"):
                    position_int.extend(chunk.get("position_int", []))
            
            # 合并页面内容
            page_content = "\n\n".join(page_contents)
            
            # 构建页面结果
            d = {
                "chunk_id": f"{doc_id}_page_{page_num}",  # 生成唯一的页面ID
                "content_ltks": page_content,  # 页面的完整内容
                "content_with_weight": page_content,
                "doc_id": doc_id,
                "docnm_kwd": page_info["docnm_kwd"],
                "kb_id": page_info["kb_id"],
                "important_kwd": [],
                "image_id": img_url,  # 页面图片URL
                "page_num": page_num,  # 页码
                "similarity": float(page_info["score"]),
                "vector_similarity": float(page_info["vsim"]),
                "term_similarity": float(page_info["tsim"]),
                "vector": zero_vector,
                "positions": position_int,
                "doc_type_kwd": "page",  # 标记为页面类型
            }
            
            if highlight:
                d["highlight"] = page_content
                
            ranks["chunks"].append(d)
            
            # 文档聚合
            dnm = page_info["docnm_kwd"]
            if dnm not in ranks["doc_aggs"]:
                ranks["doc_aggs"][dnm] = {"doc_id": doc_id, "count": 0}
            ranks["doc_aggs"][dnm]["count"] += 1
        
        ranks["doc_aggs"] = [
            {"doc_name": k, "doc_id": v["doc_id"], "count": v["count"]} 
            for k, v in sorted(ranks["doc_aggs"].items(), key=lambda x: x[1]["count"] * -1)
        ]
        
        print(f"页面检索完成，共找到 {ranks['total']} 个相关页面")
        return ranks

    def sql_retrieval(self, sql, fetch_size=128, format="json"):
        tbl = self.dataStore.sql(sql, fetch_size, format)
        return tbl

    def chunk_list(self, doc_id: str, tenant_id: str, kb_ids: list[str], max_count=1024, offset=0, fields=["docnm_kwd", "content_with_weight", "img_id"]):
        condition = {"doc_id": doc_id}
        res = []
        bs = 128
        for p in range(offset, max_count, bs):
            es_res = self.dataStore.search(fields, [], condition, [], OrderByExpr(), p, bs, index_name(tenant_id), kb_ids)
            dict_chunks = self.dataStore.getFields(es_res, fields)
            for id, doc in dict_chunks.items():
                doc["id"] = id
            if dict_chunks:
                res.extend(dict_chunks.values())
            if len(dict_chunks.values()) < bs:
                break
        return res

    def all_tags(self, tenant_id: str, kb_ids: list[str], S=1000):
        if not self.dataStore.indexExist(index_name(tenant_id), kb_ids[0]):
            return []
        res = self.dataStore.search([], [], {}, [], OrderByExpr(), 0, 0, index_name(tenant_id), kb_ids, ["tag_kwd"])
        return self.dataStore.getAggregation(res, "tag_kwd")

    def all_tags_in_portion(self, tenant_id: str, kb_ids: list[str], S=1000):
        res = self.dataStore.search([], [], {}, [], OrderByExpr(), 0, 0, index_name(tenant_id), kb_ids, ["tag_kwd"])
        res = self.dataStore.getAggregation(res, "tag_kwd")
        total = np.sum([c for _, c in res])
        return {t: (c + 1) / (total + S) for t, c in res}

    def tag_content(self, tenant_id: str, kb_ids: list[str], doc, all_tags, topn_tags=3, keywords_topn=30, S=1000):
        idx_nm = index_name(tenant_id)
        match_txt = self.qryr.paragraph(doc["title_tks"] + " " + doc["content_ltks"], doc.get("important_kwd", []), keywords_topn)
        res = self.dataStore.search([], [], {}, [match_txt], OrderByExpr(), 0, 0, idx_nm, kb_ids, ["tag_kwd"])
        aggs = self.dataStore.getAggregation(res, "tag_kwd")
        if not aggs:
            return False
        cnt = np.sum([c for _, c in aggs])
        tag_fea = sorted([(a, round(0.1 * (c + 1) / (cnt + S) / max(1e-6, all_tags.get(a, 0.0001)))) for a, c in aggs], key=lambda x: x[1] * -1)[:topn_tags]
        doc[TAG_FLD] = {a: c for a, c in tag_fea if c > 0}
        return True

    def tag_query(self, question: str, tenant_ids: str | list[str], kb_ids: list[str], all_tags, topn_tags=3, S=1000):
        if isinstance(tenant_ids, str):
            idx_nms = index_name(tenant_ids)
        else:
            idx_nms = [index_name(tid) for tid in tenant_ids]
        match_txt, _ = self.qryr.question(question, min_match=0.0)
        res = self.dataStore.search([], [], {}, [match_txt], OrderByExpr(), 0, 0, idx_nms, kb_ids, ["tag_kwd"])
        aggs = self.dataStore.getAggregation(res, "tag_kwd")
        if not aggs:
            return {}
        cnt = np.sum([c for _, c in aggs])
        tag_fea = sorted([(a, round(0.1 * (c + 1) / (cnt + S) / max(1e-6, all_tags.get(a, 0.0001)))) for a, c in aggs], key=lambda x: x[1] * -1)[:topn_tags]
        return {a.replace(".", "_"): max(1, c) for a, c in tag_fea}

    def rerank_chunks(
        self,
        question: str,
        chunks: list,
        rerank_mdl,
        top_k: int = None
    ):
        """
        使用 Rerank 模型对页面进行重排序（多模态：基于图片URL）

        参数:
        - question: 用户查询问题
        - chunks: 候选页面列表
            [
                {
                    "page_id": str,
                    "doc_id": str,
                    "docnm_kwd": str,
                    "kb_id": str,
                    "page_num_int": int,
                    "img_url": str,
                    "content_with_weight": str,
                    "tenant_id": str,
                    "rrf_score": float # 因为经过了rrf，所以此时就是rrf的得分了
                }
            ]
        - rerank_mdl: rerank 模型
        - top_k: 返回的页面数量（默认返回全部）

        返回:
        - 重排序后的 chunks 列表
        """
        if not chunks or rerank_mdl is None:
            print('[RERANK] 没有候选结果或 rerank 模型为空，跳过重排序')
            return chunks

        try:
            print(f'[RERANK] 开始重排序 {len(chunks)} 个候选页面（多模态：基于图片）')

            # 准备 rerank 的图片URL列表，将 MinIO URL 转换为 base64
            img_urls = []
            for chunk in chunks:
                img_url = chunk.get("img_url", "")
                if img_url.startswith("minio://"):
                    # 将 MinIO URL 转换为 base64 data URL
                    base64_url = convert_minio_url_to_base64(img_url)
                    if base64_url:
                        img_urls.append(base64_url)
                    else:
                        # 转换失败，使用空字符串
                        img_urls.append("")
                        logging.warning(f"Failed to convert image to base64: {img_url}")
                else:
                    # 已经是 base64 或其他格式，直接使用
                    img_urls.append(img_url)

            # 调用 rerank 模型（传递 base64 格式的图片）
            rerank_scores = rerank_mdl.similarity(question, img_urls)

            if rerank_scores is None:
                print('[RERANK] Rerank 模型返回 None，使用原始向量相似度排序')
                chunks.sort(key=lambda x: x.get("rrf_score", 0.0), reverse=True)
                return chunks[:top_k] if top_k else chunks

            # 打印 rerank 前后对比
            print(f'[RERANK] 原始排序（按 similarity）:')
            for i, chunk in enumerate(chunks[:5], 1):  # 只显示前5个
                print(f"  #{i} {chunk.get('docnm_kwd', 'Unknown')} (page {chunk.get('page_num_int', 'N/A')})")
                print(f"      similarity: {chunk.get('rrf_score', 0.0):.4f}")

            # 添加 rerank 分数字段
            for i, chunk in enumerate(chunks):
                chunk["rerank_score"] = float(rerank_scores[i])

            # 按 rerank 分数降序排序
            chunks.sort(key=lambda x: x["rerank_score"], reverse=True)

            print(f'[RERANK] Rerank 后排序（按 rerank_score）:')
            for i, chunk in enumerate(chunks[:5], 1):  # 只显示前5个
                print(f"  #{i} {chunk.get('docnm_kwd', 'Unknown')} (page {chunk.get('page_num_int', 'N/A')})")
                print(f"      similarity: {chunk.get('rrf_score', 0.0):.4f} -> rerank_score: {chunk.get('rerank_score', 0.0):.4f}")

            result = chunks[:top_k] if top_k else chunks
            print(f'[RERANK] 重排序完成，返回 {len(result)} 个结果')

            return result

        except Exception as e:
            print(f'[RERANK] 重排序失败: {e}')
            import traceback
            traceback.print_exc()
            # 失败时使用原始相似度排序
            chunks.sort(key=lambda x: x.get("similarity", 0.0), reverse=True)
            return chunks[:top_k] if top_k else chunks

    def page_vector_retrieval(
        self,
        question,
        embd_mdl,
        tenant_ids,
        kb_ids,
        rerank_mdl=None,
        top_k=2,
        similarity_threshold=0.1,
        retrieval_top_k=4
    ):
        """
        纯页面向量检索方法 - 只使用 image_2048_vec 进行检索，可选 rerank 重排序

        参数:
        - question: 用户查询问题
        - embd_mdl: embedding 模型
        - tenant_ids: 租户 ID 列表
        - kb_ids: 知识库 ID 列表
        - rerank_mdl: rerank 模型（可选）
        - top_k: 返回的页面数量（默认 2）
        - similarity_threshold: 相似度阈值
        - retrieval_top_k: 向量检索返回的候选数量（默认 4）

        返回:
        {
            "total": int,
            "chunks": [
                {
                    "page_id": str, # 页面的id
                    "doc_id": str, # 文件的id
                    "docnm_kwd": str, # 这个页面所属于的文件
                    "kb_id": str, # 这个页面所属于的知识库
                    "page_num_int": int, # 页面页号
                    "img_url": str, # 页面的url
                    "content_with_weight": str, # 这张页面上的所有文字信息
                    "similarity": float  # 相似度阈值
                }
            ]
        }
        """

        ranks = {"total": 0, "chunks": []}

        if not question:
            return ranks

        # 处理租户 ID
        if isinstance(tenant_ids, str):
            tenant_ids = [tenant_ids]

        # 定义返回的字段
        src = [
            "page_id",
            "doc_id",
            "docnm_kwd",
            "kb_id",
            "page_num_int",
            "img_url",
            "content_with_weight",
            "_score",  # 添加相似度分数字段
        ]

        # 构建过滤条件（kb_id 通过 knowledgebaseIds 参数传递，不需要放在 filters 中）
        filters = {}

        try:
            # 获取查询向量
            qv = embd_mdl.encode_queries(question)
            embedding_data = [float(v) for v in qv[0]]  # 取第一个查询的向量
            vector_dim = len(embedding_data)

            print(f'[PAGE_VECTOR_RETRIEVAL] 查询向量维度: {vector_dim}')

            # 使用图片向量字段
            vector_column = f"image_{vector_dim}_vec"

            # 构建了一个向量表达式类
            matchDense = MatchDenseExpr(
                vector_column, # 匹配检索的字段
                embedding_data, # 匹配减速的向量
                "float",
                "cosine",
                retrieval_top_k, # 检索更多的候选用于 rerank
                {"similarity": similarity_threshold} # 只要>0.1的都被检索到
            )

            # 最后执行结果的时候，都是底层的存储索引进行的检索。这个类只负责提供抽象，底层的存储索引可以是不同的存储索引
            sres = self.dataStore.search(
                src,              # 返回字段
                filters,          # 过滤条件
                [matchDense],     # 只进行向量检索（不包含全文和融合）
                OrderByExpr(),    # 不需要排序
                0,                # offset = 0
                retrieval_top_k,  # limit = retrieval_top_k
                [index_name(tid) for tid in tenant_ids], # 搜索哪些索引
                kb_ids # 从单个索引中过滤哪些kb
            )
            # totol是实际情况下去检索多少条数据
            total = self.dataStore.getTotal(sres)
            # 返回命中了es的那些id
            ids = self.dataStore.getChunkIds(sres)
            # 得到具体的chunk的元数据
            fields = self.dataStore.getFields(sres, src)

            print(f'[PAGE_VECTOR_RETRIEVAL] 找到 {total} 个候选页面')

            if total == 0:
                return ranks

            # 构建候选结果（带相似度过滤）
            candidate_chunks = []
            for chunk_id in ids:
                # 获取到对应chunk的元数据
                chunk = fields.get(chunk_id, {})
                # 获取到对应chunk的得分
                similarity_score = chunk.get("_score", 0.0)
                # <阈值分数的全部都跳过
                if similarity_score < similarity_threshold:
                    continue

                # 构建页面信息
                page_info = {
                    "page_id": chunk.get("page_id", chunk_id), # 数据库表里面的file_page的id字段
                    "doc_id": chunk.get("doc_id", ""), # 数据库表document里面的id字段
                    "kb_id": chunk.get("kb_id", ""), # 数据库表knowledge的id字段
                    "docnm_kwd": chunk.get("docnm_kwd", ""), # pdf的名称
                    "page_num_int": chunk.get("page_num_int", 0), # pdf的哪个页面
                    "img_url": chunk.get("img_url", ""), # 这个页面的minio图片地址
                    "content_with_weight": chunk.get("content_with_weight", ""), # 这一页的内容
                    "similarity": float(similarity_score)  # 这个页面与query的分数
                }

                candidate_chunks.append(page_info)


            if rerank_mdl is not None and len(candidate_chunks) > 0:
                print(f'[PAGE_VECTOR_RETRIEVAL] 使用 Rerank 模型重排序 {len(candidate_chunks)} 个候选')
                candidate_chunks = self.rerank_chunks(question, candidate_chunks, rerank_mdl, top_k)
                print('重排许完毕')
                print(candidate_chunks)
            else:
                # 如果没有rerank模型，就直接截取top_k即可
                candidate_chunks.sort(key=lambda x: x["similarity"], reverse=True)
                candidate_chunks = candidate_chunks[:top_k]

            # 返回结果
            ranks["chunks"] = candidate_chunks
            ranks["total"] = len(candidate_chunks)

            return ranks

        except Exception as e:
            print(f'[PAGE_VECTOR_RETRIEVAL] 检索失败: {e}')
            import traceback
            traceback.print_exc()
            return ranks

    # ==================== 三路并行检索相关方法 ====================

    def _rrf_fusion(self, retrieval_results: dict, rrf_k: int = 60, topk: int = 4):
        """
        RRF (Reciprocal Rank Fusion) 融合算法

        融合多路检索结果，使用 RRF 算法计算综合得分并排序

        Args:
            retrieval_results: 多路检索结果
                {
                    "image": {"chunks": [...]},
                    "text": {"chunks": [...]},
                    "keyword": {"chunks": [...]}
                }
            rrf_k: RRF 常数（默认 60），控制排名对分数的影响
            topk: 返回前 N 个结果

        Returns:
            {"total": int, "chunks": list} 融合后的结果
        """
        rrf_scores = {}
        page_info = {}  # 存储 page_id -> 完整 chunk 信息的映射

        # 每路检索的权重（图片权重最高，文本次之，关键词最低）
        # weights = {"image": 1.0, "text": 0.8, "keyword": 0.6}
        weights = {"image": 1.0, "text": 1.0, "keyword": 1.0} # 先暂时设置为这样，后续方便更改

        # 为每一路检索计算 RRF 分数
        for source, weight in weights.items():
            chunks = retrieval_results.get(source, {}).get("chunks", []) # 获取到image/text/keword检索到的页面
            for rank, chunk in enumerate(chunks, start=1): # 循环这些页面
                page_id = chunk.get("page_id")

                # 保存或更新 chunk 信息
                if page_id not in page_info:
                    # 说明是第一次遇到这个page
                    # 第一次遇到，保存完整信息
                    # 不保存similarity的原因，因为三路召回的时候，不同的similarity范围事不同的，只有这7个数据事完全相同的
                    page_info[page_id] = {
                        "page_id": page_id,
                        "doc_id": chunk.get("doc_id", ""),
                        "kb_id": chunk.get("kb_id", ""),
                        "docnm_kwd": chunk.get("docnm_kwd", ""),
                        "page_num_int": chunk.get("page_num_int", 0),
                        "img_url": chunk.get("img_url", ""),
                        "content_with_weight": chunk.get("content_with_weight", ""),
                        "tenant_id": chunk.get("tenant_id", ""),  # 添加 tenant_id 字段
                    }
                else:
                    # 已存在，更新或补充信息
                    # 补充可能缺失的字段。一般情况下不会
                    existing = page_info[page_id]
                    if not existing.get("img_url") and chunk.get("img_url"):
                        existing["img_url"] = chunk["img_url"]
                    if not existing.get("content_with_weight") and chunk.get("content_with_weight"):
                        existing["content_with_weight"] = chunk["content_with_weight"]

                # RRF 公式: score = weight / (k + rank)
                rrf_scores[page_id] = rrf_scores.get(page_id, 0) + weight / (rrf_k + rank)

        # 按分数降序排序。对rrf的得分，按照从大到小进行排序
        sorted_pages = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        # 构建返回结果
        result_chunks = []
        # 只获取前5个rrf结果的页面
        for page_id, rrf_score in sorted_pages[:topk]:
            chunk = page_info[page_id].copy()
            # 拷贝一份rrf的得分，然后放进去，此时chunk就没有sililarity这个字段了
            # similarity得分变成了rrf_score
            chunk["rrf_score"] = round(rrf_score, 4)
            result_chunks.append(chunk)

        logging.info(f"[RRF_FUSION] 融合完成: {len(result_chunks)}/{len(page_info)} 页")
        return {"total": len(result_chunks), "chunks": result_chunks}


    # 三路召回：执行图片向量检索
    def _vector_retrieval_by_image(
        self,
        question,
        embd_mdl,
        tenant_ids,
        kb_ids,
        top_k=50
    ):
        """
        纯页面向量检索 - 使用 image_2048_vec 检索，按相似度降序返回

        参数:
        - question: 用户查询问题
        - embd_mdl: embedding 模型
        - tenant_ids: 租户 ID 列表。[列表]
        - kb_ids: 知识库 ID 列表。[列表]
        - top_k: 返回的页面数量（默认 50）

        返回:
        # 返回的时候，这些快的顺序应该按照从大到小的顺序去返回。
        {
            "total": int, 
            "chunks": [
                {
                    "page_id": str, # 页面的id
                    "doc_id": str, # 文件的id
                    "docnm_kwd": str, # 这个页面所属于的文件
                    "kb_id": str, # 这个页面所属于的知识库
                    "page_num_int": int, # 页面页号
                    "img_url": str, # 页面的url
                    "content_with_weight": str, # 这张页面上的所有文字信息
                    "similarity": float  # 相似度阈值，这个相似度阈值是进行embedding的相似度阈值
                }
            ]
        }
        """
        ranks = {"total": 0, "chunks": []}

        if not question:
            return ranks

        if isinstance(tenant_ids, str):
            tenant_ids = [tenant_ids]
        if isinstance(kb_ids, str):
            kb_ids = [kb_ids]

        # 这个src只影响_source字段。es的内容长这样子
        """
        {
        "hits": {
            "total": {
                "value": 42,
                "relation": "eq"
                },
            "hits": [
                {
                    "_index": "kb_finance",
                    "_id": "chunk_1",
                    "_score": 0.95,
                    "_source": {
                    "doc_id": "doc_1",
                    "kb_id": "finance_kb",
                    "content": "金融相关内容..."
                    }
                },
                {
                    "_index": "kb_legal",
                    "_id": "chunk_8",
                    "_score": 0.92,
                    "_source": {
                    "doc_id": "doc_2",
                    "kb_id": "legal_kb",
                    "content": "法律相关内容..."
                    }
                }
            ]
        }
        }
        """
        src = ["page_id", "doc_id", "docnm_kwd", "kb_id", "page_num_int", "img_url", "content_with_weight"]

        try:
            qv = embd_mdl.encode_queries(question)
            embedding_data = [float(v) for v in qv[0]]
            vector_dim = len(embedding_data)
            vector_column = f"image_{vector_dim}_vec"

            print(f'[IMAGE_VECTOR] 查询向量维度: {vector_dim}')

            # 构造向量检索类（TODO：这里可以去加上一个similarity进行检索的粗排过滤）
            matchDense = MatchDenseExpr(vector_column, embedding_data, "float", "cosine", top_k, {})

            # 真正执行干活的函数，都应该是底层的es存储索引
            sres = self.dataStore.search(
                src, [], {}, [matchDense], OrderByExpr(),
                0, top_k, [index_name(tid) for tid in tenant_ids], kb_ids
            )

            total = self.dataStore.getTotal(sres)
            ids = self.dataStore.getChunkIds(sres) # 收集所有的chunk的_id字段，为了就是给其添加分数字段
            fields = self.dataStore.getFields(sres, src) # 这里主要是做数据格式的变换

            print(f'[IMAGE_VECTOR] 找到 {total} 个页面')

            if total == 0:
                return ranks

            for chunk_id in ids:
                chunk = fields.get(chunk_id, {})
                # 从 _index 提取 tenant_id
                tenant_id = tenant_id_from_index(chunk.get("_index", ""))
                ranks["chunks"].append({
                    "page_id": chunk.get("page_id", chunk_id),
                    "doc_id": chunk.get("doc_id", ""),
                    "kb_id": chunk.get("kb_id", ""),
                    "docnm_kwd": chunk.get("docnm_kwd", ""),
                    "page_num_int": chunk.get("page_num_int", 0),
                    "img_url": chunk.get("img_url", ""),
                    "content_with_weight": chunk.get("content_with_weight", ""),
                    "similarity": float(chunk.get("_score", 0.0)), # 这个chunk的得分
                    "tenant_id": tenant_id  # 添加 tenant_id 字段
                })

            ranks["total"] = len(ranks["chunks"])
            return ranks

        except Exception as e:
            print(f'[IMAGE_VECTOR] 检索失败: {e}')
            import traceback
            traceback.print_exc()
            return ranks

    # 三路召回：执行文本向量检索
    def _vector_retrieval_by_text(
        self,
        question,
        embd_mdl,
        tenant_ids,
        kb_ids,
        top_k=50
    ):
        """
        文本向量检索 - 使用 text_2048_vec 检索，按相似度降序返回

        参数:
        - question: 用户查询问题
        - embd_mdl: embedding 模型
        - tenant_ids: 租户 ID 列表
        - kb_ids: 知识库 ID 列表
        - top_k: 返回的页面数量（默认 50）

        返回:
        {
            "total": int,
            "chunks": [...]  # ES 已按相似度降序排序
        }
        """
        ranks = {"total": 0, "chunks": []}

        if not question:
            return ranks

        if isinstance(tenant_ids, str):
            tenant_ids = [tenant_ids]
        if isinstance(kb_ids, str):
            kb_ids = [kb_ids]

        src = ["page_id", "doc_id", "docnm_kwd", "kb_id", "page_num_int", "img_url", "content_with_weight"]

        try:
            qv = embd_mdl.encode_queries(question)
            embedding_data = [float(v) for v in qv[0]]
            vector_dim = len(embedding_data)
            vector_column = f"text_{vector_dim}_vec"

            print(f'[TEXT_VECTOR] 查询向量维度: {vector_dim}')

            matchDense = MatchDenseExpr(vector_column, embedding_data, "float", "cosine", top_k, {})

            sres = self.dataStore.search(
                src, [], {}, [matchDense], OrderByExpr(),
                0, top_k, [index_name(tid) for tid in tenant_ids], kb_ids
            )

            total = self.dataStore.getTotal(sres)
            ids = self.dataStore.getChunkIds(sres)
            fields = self.dataStore.getFields(sres, src)

            print(f'[TEXT_VECTOR] 找到 {total} 个页面')

            if total == 0:
                return ranks

            for chunk_id in ids:
                chunk = fields.get(chunk_id, {})
                # 从 _index 提取 tenant_id
                tenant_id = tenant_id_from_index(chunk.get("_index", ""))
                ranks["chunks"].append({
                    "page_id": chunk.get("page_id", chunk_id),
                    "doc_id": chunk.get("doc_id", ""),
                    "kb_id": chunk.get("kb_id", ""),
                    "docnm_kwd": chunk.get("docnm_kwd", ""),
                    "page_num_int": chunk.get("page_num_int", 0),
                    "img_url": chunk.get("img_url", ""),
                    "content_with_weight": chunk.get("content_with_weight", ""),
                    "similarity": float(chunk.get("_score", 0.0)),
                    "tenant_id": tenant_id  # 添加 tenant_id 字段
                })

            ranks["total"] = len(ranks["chunks"])
            return ranks

        except Exception as e:
            print(f'[TEXT_VECTOR] 检索失败: {e}')
            import traceback
            traceback.print_exc()
            return ranks

    # 三路召回：执行bm25检索
    def _keyword_retrieval(
        self,
        question: str,
        tenant_ids: list,
        kb_ids: list,
        top_k: int = 50
    ):
        """
        关键词检索（BM25）- 使用 content_ltks 字段检索，按 BM25 分数降序返回

        参数:
        - question: 用户查询问题
        - tenant_ids: 租户 ID 列表
        - kb_ids: 知识库 ID 列表
        - top_k: 返回的页面数量（默认 50）

        返回:
        {
            "total": int,
            "chunks": [...]  # ES 已按 BM25 分数降序排序
        }
        """
        from rag.utils.doc_store_conn import MatchTextExpr, OrderByExpr
        from management.server.services.knowledgebases.jieba_tokenizer import get_tokenizer

        ranks = {"total": 0, "chunks": []}

        if not question:
            return ranks

        if isinstance(tenant_ids, str):
            tenant_ids = [tenant_ids]
        if isinstance(kb_ids, str):
            kb_ids = [kb_ids]

        src = ["page_id", "doc_id", "docnm_kwd", "kb_id", "page_num_int", "img_url", "content_with_weight"]

        try:
            # 使用与 embedding 时相同的 jieba 分词器
            tknzr = get_tokenizer()
            keywords = tknzr.tokenize(question)

            print(f'[KEYWORD] 分词结果: {keywords}')

            # 构建关键词匹配表达式
            matchText = MatchTextExpr(
                fields=["content_ltks"],
                matching_text=keywords,
                topn=top_k,
                extra_options={"minimum_should_match": "25%", "boost": 1.0}
            )

            sres = self.dataStore.search(
                src, [], {}, [matchText], OrderByExpr(),
                0, top_k, [index_name(tid) for tid in tenant_ids], kb_ids
            )


            total = self.dataStore.getTotal(sres)
            ids = self.dataStore.getChunkIds(sres)
            fields = self.dataStore.getFields(sres, src)

            print(f'[KEYWORD] 找到 {total} 个页面')

            if total == 0:
                return ranks

            for chunk_id in ids:
                chunk = fields.get(chunk_id, {})
                # 从 _index 提取 tenant_id
                tenant_id = tenant_id_from_index(chunk.get("_index", ""))
                ranks["chunks"].append({
                    "page_id": chunk.get("page_id", chunk_id),
                    "doc_id": chunk.get("doc_id", ""),
                    "kb_id": chunk.get("kb_id", ""),
                    "docnm_kwd": chunk.get("docnm_kwd", ""),
                    "page_num_int": chunk.get("page_num_int", 0),
                    "img_url": chunk.get("img_url", ""),
                    "content_with_weight": chunk.get("content_with_weight", ""),
                    "similarity": float(chunk.get("_score", 0.0)),
                    "tenant_id": tenant_id  # 添加 tenant_id 字段
                })

            ranks["total"] = len(ranks["chunks"])
            return ranks

        except Exception as e:
            print(f'[KEYWORD] 检索失败: {e}')
            import traceback
            traceback.print_exc()
            return ranks

    # 三路召回：并行执行
    def _parallel_retrieval(
        self,
        question: str,
        embd_mdl,
        tenant_ids: list,
        kb_ids: list,
        image_topk: int,
        text_topk: int,
        keyword_topk: int,
    ):
        """
        并行执行三路检索（图片向量、文本向量、关键词）

        使用 ThreadPoolExecutor 实现并行检索，提高检索效率

        Args:
            question: 用户问题
            embd_mdl: Embedding 模型
            tenant_ids: 租户ID列表
            kb_ids: 知识库ID列表
            image_topk: 图片向量检索返回数量
            text_topk: 文本向量检索返回数量
            keyword_topk: 关键词检索返回数量

        Returns:
            {
                "image": {"total": int, "chunks": list},
                "text": {"total": int, "chunks": list},
                "keyword": {"total": int, "chunks": list}
            }
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = {}

        # 执行图片向量搜索的函数
        def retrieve_image_vector():
            """图片向量检索"""
            return self._vector_retrieval_by_image(
                question, embd_mdl, tenant_ids, kb_ids, top_k=image_topk
            )

        # 执行文本向量搜索的函数
        def retrieve_text_vector():
            """文本向量检索"""
            return self._vector_retrieval_by_text(
                question, embd_mdl, tenant_ids, kb_ids, top_k=text_topk
            )

        # 执行关键词搜索的函数
        def retrieve_keyword():
            """关键词检索（BM25）"""
            return self._keyword_retrieval(
                question, tenant_ids, kb_ids, top_k=keyword_topk
            )

        # 并行执行三路检索
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(retrieve_image_vector): "image",
                executor.submit(retrieve_text_vector): "text",
                executor.submit(retrieve_keyword): "keyword"
            }

            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                    logging.info(f"[PARALLEL_RETRIEVAL] {name} 检索完成: {results[name]['total']} 页")
                except Exception as e:
                    logging.error(f"[PARALLEL_RETRIEVAL] {name} 检索失败: {e}")
                    results[name] = {"chunks": []}

        return results

    def _get_adjacent_pages(
        self,
        doc_id: str,
        page_num: int,
        tenant_id: str,
        kb_id: str,
        offset: int = 1,
        direction: str = "both"
    ):
        """
        获取相邻页面（直接在 ES 中过滤页码范围）

        Args:
            doc_id: 文档ID
            page_num: 当前页码
            tenant_id: 租户ID
            kb_id: 知识库ID
            offset: 前后各多少页
            direction: "prev", "next", 或 "both"

        Returns:
            list: 相邻页面列表
        """
        src = ["page_id", "doc_id", "docnm_kwd", "kb_id", "page_num_int", "img_url", "content_with_weight"]

        try:
            # 使用专门的 getAdjacentPages 方法，直接在 ES 中过滤
            sres = self.dataStore.getAdjacentPages(
                src, doc_id, page_num,
                index_name(tenant_id), kb_id,
                offset, direction
            )
            # 这个返回的是召回相关的信息
            ids = self.dataStore.getChunkIds(sres)
            fields = self.dataStore.getFields(sres, src)

            results = []
            for chunk_id in ids:
                chunk = fields.get(chunk_id, {})
                # 确保包含所有必要字段，使用默认值填充缺失字段
                result_chunk = {
                    "page_id": chunk.get("page_id", chunk_id),  # 如果没有 page_id，使用 chunk_id
                    "doc_id": chunk.get("doc_id", ""),
                    "docnm_kwd": chunk.get("docnm_kwd", ""),
                    "kb_id": chunk.get("kb_id", ""),
                    "page_num_int": chunk.get("page_num_int", 0),
                    "img_url": chunk.get("img_url", ""),
                    "content_with_weight": chunk.get("content_with_weight", ""),
                }
                results.append(result_chunk)

            return results
        except Exception as e:
            logging.error(f"[GET_ADJACENT_PAGES] 获取相邻页面失败: {e}")
            return []

    def _recall_context_pages(
        self,
        chunk: dict,
        chat_mdl,
        max_context_pages: int = 1
    ):
        """
        智能判断并召回前后页

        使用 LLM Function Calling 判断页面是否需要前后页上下文

        Args:
            chunk: 当前页面信息。question已经放到了这个chunk中，必须包含 tenant_id 和 kb_id 字段
            chat_mdl: Chat 模型
            max_context_pages: 最多召回前后各多少页

        Returns:
            (context_pages, evaluation): (上下文页面列表, 评估结果)
        """
        from rag.nlp.page_context import PageEvaluation, page_evaluation_tool_schema, build_page_evaluation_prompt
        import json

        # 从 chunk 中获取 tenant_id 和 kb_id
        tenant_id = chunk.get("tenant_id", "")
        if not tenant_id:
            logging.error(f"[RECALL_CONTEXT] Chunk 缺少 tenant_id 字段，无法召回前后页")
            return [], PageEvaluation(
                is_relevant=True,
                reason="缺少 tenant_id",
                needs_prev_page=False,
                needs_next_page=False
            )

        kb_id = chunk.get("kb_id", "")
        if not kb_id:
            logging.error(f"[RECALL_CONTEXT] Chunk 缺少 kb_id 字段，无法召回前后页")
            return [], PageEvaluation(
                is_relevant=True,
                reason="缺少 kb_id",
                needs_prev_page=False,
                needs_next_page=False
            )

        doc_id = chunk["doc_id"]
        page_num = chunk["page_num_int"] # 这个页码信息，其实就可以代表page_id的信息
        question = chunk.get("question", "")

        def evaluate_page():
            """调用 VLM 评估页面（支持图片+文本）"""
            system_prompt = """你是一个智能文档助手，负责评估页面是否需要额外的上下文信息。请观察页面图片，使用 evaluate_page_context 工具进行评估。"""

            # 获取图片并转换为 base64
            img_url = chunk.get("img_url", "")
            if not img_url or not img_url.startswith("minio://"):
                logging.error(f"[EVALUATE_PAGE] 缺少图片URL: {img_url}")
                return PageEvaluation(
                    is_relevant=True,
                    reason="无图片无法评估",
                    needs_prev_page=False,
                    needs_next_page=False
                )

            img_base64 = convert_minio_url_to_base64(img_url)
            if not img_base64:
                logging.error(f"[EVALUATE_PAGE] 图片转换失败: {img_url}")
                return PageEvaluation(
                    is_relevant=True,
                    reason="图片转换失败",
                    needs_prev_page=False,
                    needs_next_page=False
                )

            # 构建多模态 prompt
            user_prompt = build_page_evaluation_prompt(
                question=question,
                img_base64=img_base64
            )
            # 注册工具
            tools = [page_evaluation_tool_schema()]

            try:
                # 调用带 function calling 的聊天方法
                response = chat_mdl.chat_with_tools(
                    system=system_prompt,
                    history=[{"role": "user", "content": user_prompt}],
                    gen_conf={
                        "tools": tools,
                        "tool_choice": "auto",
                        "temperature": 0.1
                    }
                )
                # 解析 tool_calls
                if response and isinstance(response, dict):
                    if "tool_calls" in response:
                        # 直接选用第一个工具的参数即可
                        tool_call = response["tool_calls"][0]
                        if tool_call.get("function", {}).get("name") == "evaluate_page_context":
                            arguments = tool_call["function"].get("arguments", "{}")
                            if isinstance(arguments, str):
                                return PageEvaluation.model_validate_json(arguments)
                            elif isinstance(arguments, dict):
                                return PageEvaluation.model_validate(arguments)

                # 如果没有 tool_calls，返回默认值
                logging.warning(f"[EVALUATE_PAGE] LLM 未返回 tool_calls，使用默认值")
                return PageEvaluation(
                    is_relevant=True,
                    reason="LLM 未返回结构化输出",
                    needs_prev_page=False,
                    needs_next_page=False
                )

            except Exception as e:
                logging.warning(f"[EVALUATE_PAGE] 页面评估失败: {e}，使用默认值")
                return PageEvaluation(
                    is_relevant=True,
                    reason=f"评估失败: {str(e)[:30]}",
                    needs_prev_page=False,
                    needs_next_page=False
                )

        # 执行评估，获取当前这个chunk的评估，判断是否需要召回前后页
        evaluation = evaluate_page() # 评估模型
        logging.info(f"[EVALUATE_PAGE] 页面评估结果: {evaluation.model_dump()}")

        # 先检查主页面是否相关，不相关则跳过前后页召回
        if not evaluation.is_relevant:
            logging.info(f"[RECALL_CONTEXT] 主页面不相关，跳过前后页召回")
            return [], evaluation

        # 召回前后页
        context_pages = []

        # 查看评估策略并进行召回
        if evaluation.needs_prev_page and page_num > 1:
            # 这里可以保证前一页是存在的
            # tenant_id可以理解为es的索引
            # kb_id理解为这个索引中的某一个知识库
            # doc_id理解为这个知识库里面的某一个文档
            # page_num理解为这个文档的某一个页面
            # max_context_pages最多召回这个页面的前后多少个
            prev_pages = self._get_adjacent_pages(
                doc_id, page_num, tenant_id, kb_id,
                offset=max_context_pages, direction="prev"
            )
            context_pages.extend(prev_pages)
            logging.info(f"[RECALL_CONTEXT] 召回前一页: {len(prev_pages)} 页")

        if evaluation.needs_next_page:
            # 保证是否后一页存在，是通过_get_adjacent_pages这个函数内部来进行实现的
            next_pages = self._get_adjacent_pages(
                doc_id, page_num, tenant_id, kb_id,
                offset=max_context_pages, direction="next"
            )
            context_pages.extend(next_pages)
            logging.info(f"[RECALL_CONTEXT] 召回后一页: {len(next_pages)} 页")

        return context_pages, evaluation

    def hybrid_page_retrieval(
        self,
        question: str, # 用户的问题
        embd_mdl, # embedding模型
        tenant_ids, # 从哪些es索引中选择
        kb_ids, # 单个es索引的范围
        rerank_mdl=None, # rerank模型
        chat_mdl=None, # chat模型，好像是需要选出来的，因为我要通过vlm来做前后页的召回判断
        image_topk=50, # 图像向量筛选出前50张
        text_topk=50, # 文本向量筛选出前50张
        keyword_topk=50, # 关键词筛选出前50张
        rrf_k=60, # rrf融合系数
        rrf_topk=5, # rrf结果截断前5张
        rerank_final_topk=3, # 最终通过rerank模型选出3张
        similarity_threshold=0.7, # rerank选出的3张图片的阈值限定
        enable_context_recall=False, # 这个参数是干什么的？
        context_recall_max_pages=1 # 这个呢？
    ):
        """
        三路并行检索完整流程

        流程：
        1. 三路并行检索（图片向量、文本向量、关键词）
        2. RRF 融合选出前 N 张
        3. Rerank 重排序选出前 M 张
        4. 智能前后页召回（可选）

        Args:
            question: 用户问题
            embd_mdl: Embedding 模型
            tenant_ids: 租户ID列表
            kb_ids: 知识库ID列表
            rerank_mdl: Rerank 模型（可选）
            chat_mdl: Chat 模型（用于前后页评估，可选）
            image_topk: 图片向量召回数量
            text_topk: 文本向量召回数量
            keyword_topk: 关键词召回数量
            rrf_k: RRF 常数
            rrf_topk: RRF 融合后保留数量
            rerank_final_topk: Rerank 后保留数量
            similarity_threshold: 相似度阈值
            enable_context_recall: 是否启用智能前后页召回
            context_recall_max_pages: 前后页各召回多少页

        Returns:
            {
                "total": int,
                "chunks": [
                    {
                        "page_id": str,
                        "doc_id": str,
                        "docnm_kwd": str,
                        "kb_id": str,
                        "page_num_int": int,
                        "img_url": str,
                        "content_with_weight": str,
                        "similarity": float,
                        "rrf_score": float,
                        "rerank_score": float,  # 如果使用了 rerank
                        "evaluation": dict,  # 如果启用了前后页评估
                        "context_pages": list  # 召回的上下文页面
                    }
                ]
            }
        """
        import time
        start_time = time.time()

        logging.info(f"[HYBRID_RETRIEVAL] 开始三路并行检索: {question[:50]}...")

        # 1. 三路并行检索
        retrieval_results = self._parallel_retrieval(question, embd_mdl, tenant_ids, kb_ids,image_topk, text_topk, keyword_topk)

        image_count = len(retrieval_results.get("image", {}).get("chunks", []))
        text_count = len(retrieval_results.get("text", {}).get("chunks", []))
        keyword_count = len(retrieval_results.get("keyword", {}).get("chunks", []))

        logging.info(f"[HYBRID_RETRIEVAL] 三路检索完成: "
                     f"image={image_count}, text={text_count}, keyword={keyword_count}")

        # 2. RRF 融合（需要挑选出rrf_topk页）
        fused_results = self._rrf_fusion(retrieval_results, rrf_k, rrf_topk)
        """
        经过rrf之后，这些fused——results就编程了这样，并且只有5个页面
        {
            "total": int, 
            "chunks": [
                {
                    "page_id": str, # 页面的id
                    "doc_id": str, # 文件的id
                    "docnm_kwd": str, # 这个页面所属于的文件
                    "kb_id": str, # 这个页面所属于的知识库
                    "page_num_int": int, # 页面页号
                    "img_url": str, # 页面的url
                    "content_with_weight": str, # 这张页面上的所有文字信息
                    "tenant_id":这个chunk属于哪个租户,
                    "rrf_score": float  # rrf的score
                }
            ]
        }
        """

        logging.info(f"[HYBRID_RETRIEVAL] RRF融合完成: {len(fused_results['chunks'])} 页")

        # 3. Rerank 重排序
        if rerank_mdl:
            # 使用现有的 rerank_chunks 方法
            reranked_chunks = self.rerank_chunks(
                question, fused_results["chunks"], rerank_mdl, rerank_final_topk
            )
            """
            经过rerank之后，这些reranked_chunks就编程了这样，并且只有5个页面
            {
                "total": int, 
                "chunks": [
                    {
                        "page_id": str, # 页面的id
                        "doc_id": str, # 文件的id
                        "docnm_kwd": str, # 这个页面所属于的文件
                        "kb_id": str, # 这个页面所属于的知识库
                        "page_num_int": int, # 页面页号
                        "img_url": str, # 页面的url
                        "content_with_weight": str, # 这张页面上的所有文字信息
                        "tenant_id":xx,
                        "rrf_score": float,  # rrf的score
                        "rerank_score": float # rerank的score
                    }
                ]
            }
            """
            # 应用相似度阈值过滤（基于 rerank 分数）
            if similarity_threshold > 0:
                # 只保留rerank得分>similarity_threashold的页面
                filtered_chunks = [
                    chunk for chunk in reranked_chunks
                    if chunk.get("rerank_score", 0.0) >= similarity_threshold
                ]
                # 如果所有chunk都被过滤掉，返回第一个（分数最高的）
                if not filtered_chunks and reranked_chunks:
                    filtered_chunks = [reranked_chunks[0]]
                    logging.info(f"[HYBRID_RETRIEVAL] 所有chunk相似度均低于阈值{similarity_threshold}，返回最高分chunk")
                logging.info(f"[HYBRID_RETRIEVAL] 相似度阈值过滤(>={similarity_threshold}): {len(reranked_chunks)} -> {len(filtered_chunks)} 页")
                fused_results["chunks"] = filtered_chunks
            else:
                fused_results["chunks"] = reranked_chunks

            logging.info(f"[HYBRID_RETRIEVAL] Rerank完成: {len(fused_results['chunks'])} 页")
        else:
            fused_results["chunks"] = fused_results["chunks"][:rerank_final_topk]

        # 4. 智能前后页召回（可选）
        final_chunks = []
        if enable_context_recall and chat_mdl:
            
            # 这个函数就是处理单个chunk的
            def process_chunk(chunk):
                """处理单个 chunk 的函数，用于多线程并行执行"""
                chunk["question"] = question
                # 直接在这个函数入口，传递chunk信息即可，因为chunk中有tenant_id、kb_id、doc_id、page_id等信息
                context_pages, evaluation = self._recall_context_pages(
                    chunk, chat_mdl, context_recall_max_pages
                )

                # 如果主页面不相关，不返回主页面，只返回上下文页面（如果有）
                if not evaluation.is_relevant:
                    logging.info(f"[HYBRID_RETRIEVAL] 主页面不相关，跳过: page_id={chunk.get('page_id')}")
                    # 主页面不相关，但上下文页面可能仍然相关（虽然理论上不应该有）
                    ctx_pages = []
                    for ctx_page in context_pages:
                        ctx_page["is_context"] = True
                        ctx_pages.append(ctx_page)
                    return None, ctx_pages

                # main_page是主页面，ctx_pages是因为主页面而被召回的页面
                # 构建主页面结果
                main_page = {**chunk, "evaluation": evaluation.model_dump()}

                # 构建上下文页面结果
                ctx_pages = []
                for ctx_page in context_pages:
                    ctx_page["is_context"] = True # 标记这个东西是因为上下文而被召回的
                    ctx_pages.append(ctx_page)

                return main_page, ctx_pages

            # 使用线程池并行处理所有 chunks
            # 本地映射：page_id -> (main_page, ctx_pages)，用于保持顺序
            page_id_to_result = {}

            with ThreadPoolExecutor(max_workers=3) as executor:
                # 提交所有任务，记住每个chunk对应的page_id
                future_to_page_id = {
                    executor.submit(process_chunk, chunk): chunk.get("page_id")
                    for chunk in fused_results["chunks"]
                }

                # 等待所有任务完成
                for future in as_completed(future_to_page_id):
                    page_id = future_to_page_id[future]
                    main_page, ctx_pages = future.result()
                    # 存储到本地映射中
                    page_id_to_result[page_id] = (main_page, ctx_pages)

            # 按原始顺序组装结果：先父页面，再其上下文页面
            for chunk in fused_results["chunks"]:
                page_id = chunk.get("page_id")
                if page_id in page_id_to_result:
                    main_page, ctx_pages = page_id_to_result[page_id]
                    # 只添加主页面（如果存在且相关）
                    if main_page is not None:
                        final_chunks.append(main_page)
                    # 添加上下文页面（紧跟在父页面后面）
                    final_chunks.extend(ctx_pages)

            # 去重：用 page_id 去重，保留第一次出现的。这里是为了保证不发送相同的结果给vlm
            seen_page_ids = set()
            unique_chunks = []
            for chunk in final_chunks:
                page_id = chunk.get("page_id")
                if page_id not in seen_page_ids:
                    seen_page_ids.add(page_id)
                    unique_chunks.append(chunk)
            final_chunks = unique_chunks
            logging.info(f"[HYBRID_RETRIEVAL] 前后页召回完成（去重后）: 总页面数 {len(final_chunks)}")
        else:
            # 没有开启的话会直接吧上面的rrf的结果给赋值进来
            final_chunks = fused_results["chunks"]

        # 打印 final_chunks 的详细信息
        logging.info(f"[HYBRID_RETRIEVAL] final_chunks 详细信息:")
        for i, chunk in enumerate(final_chunks):
            logging.info(f"  [{i}] page_id={chunk.get('page_id')}, doc_id={chunk.get('doc_id')}, "
                       f"kb_id={chunk.get('kb_id')}, tenant_id={chunk.get('tenant_id')}, "
                       f"page_num_int={chunk.get('page_num_int')}, "
                       f"is_context={chunk.get('is_context', False)}, "
                       f"rrf_score={chunk.get('rrf_score', 'N/A')}, "
                       f"rerank_score={chunk.get('rerank_score', 'N/A')}")

        elapsed = time.time() - start_time
        logging.info(f"[HYBRID_RETRIEVAL] 检索完成，耗时: {elapsed:.2f}s")

        # 标准化返回格式，与 page_vector_retrieval 接口一致
        # 返回的时候，有些东西是必须的，上面7个字段是必须的

        # 构建返回的 chunks 列表
        chunks_list = [
            {
                "page_id": item.get("page_id", ""),
                "doc_id": item.get("doc_id", ""),
                "docnm_kwd": item.get("docnm_kwd", ""),
                "kb_id": item.get("kb_id", ""),
                "page_num_int": item.get("page_num_int", 0),
                "img_url": item.get("img_url", ""),
                "content_with_weight": item.get("content_with_weight", ""),
                "is_context": item.get('is_context', False), # 这个用于后续来进行判断，是否需要添加到mysql中给前端看
                "similarity": float(item.get("rerank_score", item.get("rrf_score", 0.0))) # 召回的页面可能并没有这个similarity
            }
            for item in final_chunks
        ]

        # total 只计算主页面的数量（不包括上下文页面）
        main_pages_count = sum(1 for chunk in chunks_list if not chunk.get("is_context", False))

        return {
            "total": main_pages_count,
            "chunks": chunks_list
        }
