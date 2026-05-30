from abc import ABC, abstractmethod
from dataclasses import dataclass
import numpy as np

DEFAULT_MATCH_VECTOR_TOPN = 10
DEFAULT_MATCH_SPARSE_TOPN = 10
VEC = list | np.ndarray


@dataclass
class SparseVector:
    indices: list[int]
    values: list[float] | list[int] | None = None

    def __post_init__(self):
        assert (self.values is None) or (len(self.indices) == len(self.values))

    def to_dict_old(self):
        d = {"indices": self.indices}
        if self.values is not None:
            d["values"] = self.values
        return d

    def to_dict(self):
        if self.values is None:
            raise ValueError("SparseVector.values is None")
        result = {}
        for i, v in zip(self.indices, self.values):
            result[str(i)] = v
        return result

    @staticmethod
    def from_dict(d):
        return SparseVector(d["indices"], d.get("values"))

    def __str__(self):
        return f"SparseVector(indices={self.indices}{'' if self.values is None else f', values={self.values}'})"

    def __repr__(self):
        return str(self)

# 文本表达式类
class MatchTextExpr(ABC):
    def __init__(
        self,
        fields: list[str],
        matching_text: str,
        topn: int,
        extra_options: dict = dict(),
    ):
        """
        [
            "title_tks^10", # 给这个字段的得分*10
            "title_sm_tks^5", # 给这个字段的得分*5
            "important_kwd^30", # *30
            "important_tks^20", # *20
            "question_tks^20",
            "content_ltks^2",
            "content_sm_ltks",
        ]
        """
        self.fields = fields
        # es中特有的带权重的一个表达式
        self.matching_text = matching_text
        # 100
        self.topn = topn
        # 一些格外的参数{"minimum_should_match": 0.3}
        self.extra_options = extra_options

# 向量表达式类
class MatchDenseExpr(ABC):
    def __init__(
        self,
        vector_column_name: str,
        embedding_data: VEC,
        embedding_data_type: str,
        distance_type: str,
        topn: int = DEFAULT_MATCH_VECTOR_TOPN,
        extra_options: dict = dict(),
    ):
        self.vector_column_name = vector_column_name
        self.embedding_data = embedding_data
        self.embedding_data_type = embedding_data_type
        self.distance_type = distance_type
        self.topn = topn
        self.extra_options = extra_options


class MatchSparseExpr(ABC):
    def __init__(
        self,
        vector_column_name: str,
        sparse_data: SparseVector | dict,
        distance_type: str,
        topn: int,
        opt_params: dict | None = None,
    ):
        self.vector_column_name = vector_column_name
        self.sparse_data = sparse_data
        self.distance_type = distance_type
        self.topn = topn
        self.opt_params = opt_params

# 向量表达式类
class MatchTensorExpr(ABC):
    def __init__(
        self,
        column_name: str,
        query_data: VEC,
        query_data_type: str,
        topn: int,
        extra_option: dict | None = None,
    ):
        self.column_name = column_name
        self.query_data = query_data
        self.query_data_type = query_data_type
        self.topn = topn
        self.extra_option = extra_option

# 融合表达式类
class FusionExpr(ABC):
    def __init__(self, method: str, topn: int, fusion_params: dict | None = None):
        # weighted_sum
        self.method = method
        # 1024
        self.topn = topn
        # {"weights": "0.05, 0.95"}
        self.fusion_params = fusion_params


MatchExpr = MatchTextExpr | MatchDenseExpr | MatchSparseExpr | MatchTensorExpr | FusionExpr

# 这个类也被使用到了
class OrderByExpr(ABC):
    def __init__(self):
        self.fields = list()
    def asc(self, field: str):
        """
        升序排序
        """
        self.fields.append((field, 0))
        return self
    def desc(self, field: str):
        """
        降序排序
        """
        self.fields.append((field, 1))
        return self
    def fields(self):
        # 返回排序字段
        return self.fields

# 当前的这个类是一个抽象类，集成这个类的必须起实现这个类中的一些方法，全部都是抽象方法
class DocStoreConnection(ABC):
    """
    Database operations
    """

    @abstractmethod
    def dbType(self) -> str:
        """
        Return the type of the database.
        """
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def health(self) -> dict:
        """
        Return the health status of the database.
        """
        raise NotImplementedError("Not implemented")

    """
    Table operations
    """

    @abstractmethod
    def createIdx(self, indexName: str, knowledgebaseId: str, vectorSize: int):
        """
        Create an index with given name
        """
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def deleteIdx(self, indexName: str, knowledgebaseId: str):
        """
        Delete an index with given name
        """
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def indexExist(self, indexName: str, knowledgebaseId: str) -> bool:
        """
        Check if an index with given name exists
        """
        raise NotImplementedError("Not implemented")

    """
    CRUD operations
    """

    @abstractmethod
    def search(
        self, 
        selectFields: list[str], # 需要返回哪些字段
        condition: dict, # 一些过滤的条件
        matchExprs: list[MatchExpr],
        orderBy: OrderByExpr,
        offset: int,
        limit: int,
        indexNames: str|list[str],
        knowledgebaseIds: list[str]
    ):
        """
        Search with given conjunctive equivalent filtering condition and return all fields of matched documents
        """
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def get(self, chunkId: str, indexName: str, knowledgebaseIds: list[str]) -> dict | None:
        """
        Get single chunk with given id
        """
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def insert(self, rows: list[dict], indexName: str, knowledgebaseId: str = None) -> list[str]:
        """
        Update or insert a bulk of rows
        """
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def update(self, condition: dict, newValue: dict, indexName: str, knowledgebaseId: str) -> bool:
        """
        Update rows with given conjunctive equivalent filtering condition
        """
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def delete(self, condition: dict, indexName: str, knowledgebaseId: str) -> int:
        """
        Delete rows with given conjunctive equivalent filtering condition
        """
        raise NotImplementedError("Not implemented")

    """
    Helper functions for search result
    """

    @abstractmethod
    def getTotal(self, res):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def getChunkIds(self, res):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def getFields(self, res, fields: list[str]) -> dict[str, dict]:
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def getHighlight(self, res, keywords: list[str], fieldnm: str):
        raise NotImplementedError("Not implemented")

    @abstractmethod
    def getAggregation(self, res, fieldnm: str):
        raise NotImplementedError("Not implemented")

    @abstractmethod
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
        Get adjacent pages of a document (directly filter by page number range in database)

        Args:
            selectFields: Fields to return
            doc_id: Document ID
            page_num: Current page number
            indexName: Index name
            knowledgebaseId: Knowledge base ID
            offset: How many pages before/after
            direction: "prev", "next", or "both"

        Returns:
            Raw database response
        """
        raise NotImplementedError("Not implemented")

    """
    SQL
    """
    @abstractmethod
    def sql(sql: str, fetch_size: int, format: str):
        """
        Run the sql generated by text-to-sql
        """
        raise NotImplementedError("Not implemented")
