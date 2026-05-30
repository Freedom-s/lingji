import logging
import re
import json
import time
import os

import copy
from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch_dsl import UpdateByQuery, Q, Search, Index
from elastic_transport import ConnectionTimeout
from rag import settings
from rag.settings import TAG_FLD, PAGERANK_FLD
from rag.utils import singleton
from api.utils.file_utils import get_project_base_directory
from rag.utils.doc_store_conn import DocStoreConnection, MatchExpr, OrderByExpr, MatchTextExpr, MatchDenseExpr, \
    FusionExpr
from rag.nlp import is_english, rag_tokenizer

ATTEMPT_TIME = 2

logger = logging.getLogger('ragflow.es_conn')

# 这个mapping.json是在做什么，是进行检索的时候才使用的这个？

# 单例模式，初始化了一个es的连接对象
# 这个es连接对象中有各种各样的方法可供我们使用
# 这个DocStoreConnection是一个抽象类，所以ESConnection必须谁先其中的一些方法
@singleton
class ESConnection(DocStoreConnection):
    def __init__(self):
        self.info = {}
        logger.info(f"Use Elasticsearch {settings.ES['hosts']} as the doc engine.")
        # 两次尝试去跟es建立连接
        for _ in range(ATTEMPT_TIME):
            try:
                # 为当前这个类初始化一个es的客户端
                self.es = Elasticsearch(
                    settings.ES["hosts"].split(","),
                    basic_auth=(settings.ES["username"], settings.ES[
                        "password"]) if "username" in settings.ES and "password" in settings.ES else None,
                    verify_certs=False,
                    timeout=600
                )
                if self.es:
                    self.info = self.es.info()
                    break
            except Exception as e:
                logger.warning(f"{str(e)}. Waiting Elasticsearch {settings.ES['hosts']} to be healthy.")
                time.sleep(5)
        # 没有与es建立连接，报错
        if not self.es.ping():
            msg = f"Elasticsearch {settings.ES['hosts']} is unhealthy in 120s."
            logger.error(msg)
            raise Exception(msg)
        
        # 检查es的版本号
        v = self.info.get("version", {"number": "8.11.3"})
        v = v["number"].split(".")[0]
        if int(v) < 8:
            msg = f"Elasticsearch version must be greater than or equal to 8, current version: {v}"
            logger.error(msg)
            raise Exception(msg)

    """
    Database operations
    """
    def dbType(self) -> str:
        """
        返回当前的db类型
        """
        return "elasticsearch"

    def health(self) -> dict:
        """
        检测当前的es集群是否健康
        """
        health_dict = dict(self.es.cluster.health())
        health_dict["type"] = "elasticsearch"
        return health_dict

    """
    Table operations
    """
    def createIdx(self, indexName: str, knowledgebaseId: str, vectorSize: int):
        raise NotImplementedError("Not implemented")

    def deleteIdx(self, indexName: str, knowledgebaseId: str):
        if len(knowledgebaseId) > 0:
            # The index need to be alive after any kb deletion since all kb under this tenant are in one index.
            return
        try:
            self.es.indices.delete(index=indexName, allow_no_indices=True)
        except NotFoundError:
            pass
        except Exception:
            logger.exception("ESConnection.deleteIdx error %s" % (indexName))

    def indexExist(self, indexName: str, knowledgebaseId: str = None) -> bool:
        """
        判断es的索引是否存在
        """
        s = Index(indexName, self.es)
        for i in range(ATTEMPT_TIME):
            try:
                return s.exists()
            except Exception as e:
                logger.exception("ESConnection.indexExist got exception")
                if str(e).find("Timeout") > 0 or str(e).find("Conflict") > 0:
                    continue
                break
        return False

    """
    CRUD operations
    """

    def search(
            self,
            selectFields: list[str], # 需要从es中检索哪些字段出来
            highlightFields: list[str] = None, # 需要高亮的字段
            condition: dict = None, # 需要filter哪些字段
            matchExprs: list[MatchExpr] = None, # 向量数据
            orderBy: OrderByExpr = None, # 按照什么字段来排序，暂时是空的
            offset: int = 0, # 从第0页开始
            limit: int = 30, # 检索数量
            indexNames: str | list[str] = None, # 需要检索哪些索引
            knowledgebaseIds: list[str] = None, # kb_ids,这是索引中的一个字段，需要进行filter
            rank_feature: dict = None, # rank feature 参数
    ):

        # 处理默认参数
        if highlightFields is None:
            highlightFields = []
        if condition is None:
            condition = {}
        if matchExprs is None:
            matchExprs = []
        if orderBy is None:
            from rag.utils.doc_store_conn import OrderByExpr
            orderBy = OrderByExpr()

        # 构建布尔查询
        bqry = Q("bool", must=[])

        # 过滤索引中kb_ids字段，也就是说。索引是租户级别的概念，租户可能创建多个知识库，然后选取dialog的时候，只用其中几个知识库。
        # 这里面的kb_ids是一个数组列表，相当于kb_id in (kb1,kb2,kb3)
        if knowledgebaseIds:
            bqry.filter.append(Q("terms", kb_id=knowledgebaseIds))

        # 添加其他过滤条件（doc_id 等），暂时是一个空的
        for k, v in condition.items():
            if not v:
                continue
            if isinstance(v, list):
                bqry.filter.append(Q("terms", **{k: v}))
            elif isinstance(v, str) or isinstance(v, int):
                bqry.filter.append(Q("term", **{k: v}))
            else:
                raise Exception(
                    f"Condition `{str(k)}={str(v)}` value type is {str(type(v))}, expected to be int, str or list.")

        # 创建搜索对象
        s = Search()

        # 处理向量检索表达式（MatchDenseExpr）
        for m in matchExprs:
            if isinstance(m, MatchDenseExpr):
                similarity = 0.0
                if "similarity" in m.extra_options:
                    similarity = m.extra_options["similarity"]

                # 执行 knn 向量检索
                s = s.knn(
                    m.vector_column_name,  # 向量字段名（如 image_2048_vec）
                    m.topn,              # 返回 topn 个结果
                    m.topn * 2,           # 候选数量，这个参数是针对多个分片才管用的
                    query_vector=m.embedding_data,  # 查询向量
                    filter=bqry.to_dict(),  # 过滤条件
                    similarity=similarity,  # 最小分数阈值
                )
                # KNN 检索只能有一个，找到后继续处理其他表达式
                break

        # 处理文本检索表达式（MatchTextExpr）- BM25 关键词检索
        for m in matchExprs:
            if isinstance(m, MatchTextExpr):
                # 我这里其实匹配的只有一个列需要进行这种关键词匹配
                fields = m.fields or ["content_ltks"]
                bm25_field = fields[0]  # 真正需要进行关键词匹配的字段，content_ltks
                min_match_val = m.extra_options.get("minimum_should_match", "25%")
                boost_val = m.extra_options.get("boost", 1.0)

                single_match_query = Q("match", **{
                    bm25_field: {
                        "query": m.matching_text,
                        "minimum_should_match": min_match_val,
                        "boost": boost_val
                    }
                })
                bqry.must.append(single_match_query)

        # 如果没有 KNN 检索但有布尔查询条件，添加到 Search 对象
        has_knn = any(isinstance(m, MatchDenseExpr) for m in matchExprs)
        if not has_knn and (bqry.must or bqry.filter):
            s = s.query(bqry)

        # 处理排序（如果有），暂时传入的是一个空的排序字段
        if orderBy and orderBy.fields:
            orders = list()
            for field, order in orderBy.fields:
                order_dir = "asc" if order == 0 else "desc"

                # 只对已知存在的数值字段进行排序
                # 对于 text 字段，尝试使用 .keyword 子字段
                if field in ["page_num_int", "create_timestamp_flt"]:
                    # 数值字段，直接排序
                    order_info = {"order": order_dir}
                    orders.append({field: order_info})
                elif field.endswith("_kwd") or field.endswith("_tks"):
                    # text 类型字段，使用 .keyword 子字段排序
                    keyword_field = f"{field}.keyword"
                    order_info = {"order": order_dir, "unmapped_type": "keyword"}
                    orders.append({keyword_field: order_info})
                else:
                    # 其他字段，尝试使用 keyword 子字段
                    keyword_field = f"{field}.keyword"
                    order_info = {"order": order_dir, "unmapped_type": "keyword"}
                    orders.append({keyword_field: order_info})

            if orders:  # 只有在有有效排序字段时才添加排序
                s = s.sort(*orders)

        # 相当于向底层发送参数。{"from": 10, "size": 10}
        if limit > 0:
            s = s[offset:offset + limit]

        # 转换为字典并执行查询
        q = s.to_dict()

        # 尝试两次进行检索
        for i in range(ATTEMPT_TIME):
            try:
                res = self.es.search(
                    index=indexNames, # 搜索哪个索引
                    body=q, # 检索的参数
                    timeout="60s", # 时间限制
                    track_total_hits=True, # 强制说明总计有多少条数据
                    _source=selectFields if selectFields else True  # 返回哪些字段，相当于sql中的select col1，col2
                )
                if str(res.get("timed_out", "")).lower() == "true":
                    raise Exception("Es Timeout.")
                return res
            except Exception as e:
                if str(e).find("Timeout") > 0:
                    continue
                raise e

        raise Exception("ESConnection.search timeout.")

    def get(self, chunkId: str, indexName: str, knowledgebaseIds: list[str]) -> dict | None:
        for i in range(ATTEMPT_TIME):
            try:
                res = self.es.get(index=(indexName),
                                  id=chunkId, source=True, )
                if str(res.get("timed_out", "")).lower() == "true":
                    raise Exception("Es Timeout.")
                chunk = res["_source"]
                chunk["id"] = chunkId
                return chunk
            except NotFoundError:
                return None
            except Exception as e:
                logger.exception(f"ESConnection.get({chunkId}) got exception")
                if str(e).find("Timeout") > 0:
                    continue
                raise e
        logger.error("ESConnection.get timeout for 3 times!")
        raise Exception("ESConnection.get timeout.")

    def insert(self, documents: list[dict], indexName: str, knowledgebaseId: str = None) -> list[str]:
        # Refers to https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-bulk.html
        operations = []
        for d in documents:
            assert "_id" not in d
            assert "id" in d
            d_copy = copy.deepcopy(d)
            meta_id = d_copy.pop("id", "")
            operations.append(
                {"index": {"_index": indexName, "_id": meta_id}})
            operations.append(d_copy)

        res = []
        for _ in range(ATTEMPT_TIME):
            try:
                res = []
                r = self.es.bulk(index=(indexName), operations=operations,
                                 refresh=False, timeout="60s")
                if re.search(r"False", str(r["errors"]), re.IGNORECASE):
                    return res

                for item in r["items"]:
                    for action in ["create", "delete", "index", "update"]:
                        if action in item and "error" in item[action]:
                            res.append(str(item[action]["_id"]) + ":" + str(item[action]["error"]))
                return res
            except Exception as e:
                res.append(str(e))
                logger.warning("ESConnection.insert got exception: " + str(e))
                res = []
                if re.search(r"(Timeout|time out)", str(e), re.IGNORECASE):
                    res.append(str(e))
                    time.sleep(3)
                    continue
        return res

    def update(self, condition: dict, newValue: dict, indexName: str, knowledgebaseId: str) -> bool:
        doc = copy.deepcopy(newValue)
        doc.pop("id", None)
        if "id" in condition and isinstance(condition["id"], str):
            # update specific single document
            chunkId = condition["id"]
            for i in range(ATTEMPT_TIME):
                try:
                    self.es.update(index=indexName, id=chunkId, doc=doc)
                    return True
                except Exception as e:
                    logger.exception(
                        f"ESConnection.update(index={indexName}, id={id}, doc={json.dumps(condition, ensure_ascii=False)}) got exception")
                    if re.search(r"(timeout|connection)", str(e).lower()):
                        continue
                    break
            return False

        # update unspecific maybe-multiple documents
        bqry = Q("bool")
        for k, v in condition.items():
            if not isinstance(k, str) or not v:
                continue
            if k == "exists":
                bqry.filter.append(Q("exists", field=v))
                continue
            if isinstance(v, list):
                bqry.filter.append(Q("terms", **{k: v}))
            elif isinstance(v, str) or isinstance(v, int):
                bqry.filter.append(Q("term", **{k: v}))
            else:
                raise Exception(
                    f"Condition `{str(k)}={str(v)}` value type is {str(type(v))}, expected to be int, str or list.")
        scripts = []
        params = {}
        for k, v in newValue.items():
            if k == "remove":
                if isinstance(v, str):
                    scripts.append(f"ctx._source.remove('{v}');")
                if isinstance(v, dict):
                    for kk, vv in v.items():
                        scripts.append(f"int i=ctx._source.{kk}.indexOf(params.p_{kk});ctx._source.{kk}.remove(i);")
                        params[f"p_{kk}"] = vv
                continue
            if k == "add":
                if isinstance(v, dict):
                    for kk, vv in v.items():
                        scripts.append(f"ctx._source.{kk}.add(params.pp_{kk});")
                        params[f"pp_{kk}"] = vv.strip()
                continue
            if not isinstance(k, str) or not v:
                continue
            if isinstance(v, str):
                v = re.sub(r"(['\n\r]|\\.)", " ", v)
                params[f"pp_{k}"] = v
                scripts.append(f"ctx._source.{k}=params.pp_{k};")
            elif isinstance(v, int) or isinstance(v, float):
                scripts.append(f"ctx._source.{k}={v};")
            elif isinstance(v, list):
                scripts.append(f"ctx._source.{k}=params.pp_{k};")
                params[f"pp_{k}"] = json.dumps(v, ensure_ascii=False)
            else:
                raise Exception(
                    f"newValue `{str(k)}={str(v)}` value type is {str(type(v))}, expected to be int, str.")
        ubq = UpdateByQuery(
            index=indexName).using(
            self.es).query(bqry)
        ubq = ubq.script(source="".join(scripts), params=params)
        ubq = ubq.params(refresh=True)
        ubq = ubq.params(slices=5)
        ubq = ubq.params(conflicts="proceed")

        for _ in range(ATTEMPT_TIME):
            try:
                _ = ubq.execute()
                return True
            except Exception as e:
                logger.error("ESConnection.update got exception: " + str(e) + "\n".join(scripts))
                if re.search(r"(timeout|connection|conflict)", str(e).lower()):
                    continue
                break
        return False

    def delete(self, condition: dict, indexName: str, knowledgebaseId: str) -> int:
        qry = None
        assert "_id" not in condition
        if "id" in condition:
            chunk_ids = condition["id"]
            if not isinstance(chunk_ids, list):
                chunk_ids = [chunk_ids]
            qry = Q("ids", values=chunk_ids)
        else:
            qry = Q("bool")
            for k, v in condition.items():
                if k == "exists":
                    qry.filter.append(Q("exists", field=v))

                elif k == "must_not":
                    if isinstance(v, dict):
                        for kk, vv in v.items():
                            if kk == "exists":
                                qry.must_not.append(Q("exists", field=vv))

                elif isinstance(v, list):
                    qry.must.append(Q("terms", **{k: v}))
                elif isinstance(v, str) or isinstance(v, int):
                    qry.must.append(Q("term", **{k: v}))
                else:
                    raise Exception("Condition value must be int, str or list.")
        logger.debug("ESConnection.delete query: " + json.dumps(qry.to_dict()))
        for _ in range(ATTEMPT_TIME):
            try:
                #print(Search().query(qry).to_dict(), flush=True)
                res = self.es.delete_by_query(
                    index=indexName,
                    body=Search().query(qry).to_dict(),
                    refresh=True)
                return res["deleted"]
            except Exception as e:
                logger.warning("ESConnection.delete got exception: " + str(e))
                if re.search(r"(timeout|connection)", str(e).lower()):
                    time.sleep(3)
                    continue
                if re.search(r"(not_found)", str(e), re.IGNORECASE):
                    return 0
        return 0

    """
    Helper functions for search result
    """
    def getTotal(self, res):
        if isinstance(res["hits"]["total"], type({})):
            return res["hits"]["total"]["value"]
        return res["hits"]["total"]

    def getChunkIds(self, res):
        return [d["_id"] for d in res["hits"]["hits"]]

    def __getSource(self, res):
        rr = []
        for d in res["hits"]["hits"]:
            # 这里就是把外面的信息加入到里面
            """
            {
                "_index": "kb_finance",
                "_id": "chunk_1",
                "_score": 0.95,
                "_source": {
                    "doc_id": "doc_1",
                    "kb_id": "finance_kb",
                    "content": "金融相关内容..."
                }
            } 
            """
            d["_source"]["id"] = d["_id"]
            d["_source"]["_score"] = d["_score"]
            d["_source"]["_index"] = d.get("_index", "")  # 添加索引名，用于推断 tenant_id
            rr.append(d["_source"])
        return rr

    def getFields(self, res, fields: list[str]) -> dict[str, dict]:
        res_fields = {}
        if not fields:
            return {}
        # 自动包含 _score 和 _index 元数据字段
        fields_with_metadata = list(fields) + ["_score", "_index"]
        for d in self.__getSource(res):
            m = {n: d.get(n) for n in fields_with_metadata if d.get(n) is not None}
            if m:
                res_fields[d["id"]] = m
        return res_fields

    def getHighlight(self, res, keywords: list[str], fieldnm: str):
        ans = {}
        for d in res["hits"]["hits"]:
            hlts = d.get("highlight")
            if not hlts:
                continue
            txt = "...".join([a for a in list(hlts.items())[0][1]])
            if not is_english(txt.split()):
                ans[d["_id"]] = txt
                continue

            txt = d["_source"][fieldnm]
            txt = re.sub(r"[\r\n]", " ", txt, flags=re.IGNORECASE | re.MULTILINE)
            txts = []
            for t in re.split(r"[.?!;\n]", txt):
                for w in keywords:
                    t = re.sub(r"(^|[ .?/'\"\(\)!,:;-])(%s)([ .?/'\"\(\)!,:;-])" % re.escape(w), r"\1<em>\2</em>\3", t,
                               flags=re.IGNORECASE | re.MULTILINE)
                if not re.search(r"<em>[^<>]+</em>", t, flags=re.IGNORECASE | re.MULTILINE):
                    continue
                txts.append(t)
            ans[d["_id"]] = "...".join(txts) if txts else "...".join([a for a in list(hlts.items())[0][1]])

        return ans

    def getAggregation(self, res, fieldnm: str):
        agg_field = "aggs_" + fieldnm
        if "aggregations" not in res or agg_field not in res["aggregations"]:
            return list()
        bkts = res["aggregations"][agg_field]["buckets"]
        return [(b["key"], b["doc_count"]) for b in bkts]

    def getAdjacentPages(
        self,
        selectFields: list[str],
        doc_id: str,
        page_num: int,
        indexName: str,
        knowledgebaseId: str,
        offset: int = 1,
        direction: str = "both"
    ):
        """
        获取文档的相邻页面（直接在 ES 中过滤页码范围）

        Args:
            selectFields: 需要返回的字段列表
            doc_id: 文档ID
            page_num: 当前页码
            indexName: 索引名称
            knowledgebaseId: 知识库ID
            offset: 前后各多少页
            direction: "prev", "next", 或 "both"

        Returns:
            ES 原始响应结果
        """
        # 构建布尔查询
        bqry = Q("bool", must=[])

        # 索引是最后进行定位的。1、定位知识库、2、定位文档、3、定位页面

        # 过滤知识库（使用 term 因为 knowledgebaseId 是单个字符串）
        if knowledgebaseId:
            bqry.filter.append(Q("term", kb_id=knowledgebaseId))

        # 过滤文档
        bqry.filter.append(Q("term", doc_id=doc_id))

        # 确定页码范围
        if direction == "prev":
            page_min, page_max = max(1, page_num - offset), page_num - 1
        elif direction == "next":
            page_min, page_max = page_num + 1, page_num + offset
        else:  # both
            page_min, page_max = max(1, page_num - offset), page_num + offset

        # 添加页码范围过滤（直接在 ES 中过滤）
        bqry.filter.append(Q("range", page_num_int={"gte": page_min, "lte": page_max}))

        # 创建搜索对象
        s = Search()
        s = s.query(bqry)
        s = s.sort("page_num_int")  # 按页码排序

        # 限制返回数量（避免返回过多数据）
        limit = offset * 2
        s = s[0:limit]

        # 转换为字典并执行查询
        q = s.to_dict()

        for i in range(ATTEMPT_TIME):
            try:
                res = self.es.search(
                    index=indexName,
                    body=q,
                    timeout="60s",
                    track_total_hits=True,
                    _source=selectFields if selectFields else True
                )
                if str(res.get("timed_out", "")).lower() == "true":
                    raise Exception("Es Timeout.")
                return res
            except Exception as e:
                if str(e).find("Timeout") > 0:
                    continue
                raise e

        raise Exception("ESConnection.getAdjacentPages timeout.")

    def sql(self, sql: str, fetch_size: int, format: str):
        logger.debug(f"ESConnection.sql get sql: {sql}")
        sql = re.sub(r"[ `]+", " ", sql)
        sql = sql.replace("%", "")
        replaces = []
        for r in re.finditer(r" ([a-z_]+_l?tks)( like | ?= ?)'([^']+)'", sql):
            fld, v = r.group(1), r.group(3)
            match = " MATCH({}, '{}', 'operator=OR;minimum_should_match=30%') ".format(
                fld, rag_tokenizer.fine_grained_tokenize(rag_tokenizer.tokenize(v)))
            replaces.append(
                ("{}{}'{}'".format(
                    r.group(1),
                    r.group(2),
                    r.group(3)),
                 match))

        for p, r in replaces:
            sql = sql.replace(p, r, 1)
        logger.debug(f"ESConnection.sql to es: {sql}")

        for i in range(ATTEMPT_TIME):
            try:
                res = self.es.sql.query(body={"query": sql, "fetch_size": fetch_size}, format=format,
                                        request_timeout="2s")
                return res
            except ConnectionTimeout:
                logger.exception("ESConnection.sql timeout")
                continue
            except Exception:
                logger.exception("ESConnection.sql got exception")
                return None
        logger.error("ESConnection.sql timeout for 3 times!")
        return None
