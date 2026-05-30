from elasticsearch_dsl import UpdateByQuery, Q, Search, Index

condition = {'kb_id': ['7e5fd011c30444179a4ac7ed01fa4204'], 'doc_id': [], 'available_int': 1}

bqry = Q("bool", must=[])

print(bqry)
for k, v in condition.items():
    if k == "available_int":
        # 这个v是写死的，available_int=1,这个available_int是文档中的一个字段吗？
        if v == 0:
            bqry.filter.append(Q("range", available_int={"lt": 1}))
        else:
            # 表示文档的available_int字段必须是不小于1的，即>1
            bqry.filter.append(
                Q("bool", must_not=Q("range", available_int={"lt": 1})))
        continue
    if not v:
        continue
    if isinstance(v, list):
        # 表示kb_id必须是=['7e5fd011c30444179a4ac7ed01fa4204']，这个**的作用是解包字典
        bqry.filter.append(Q("terms", **{k: v}))
    elif isinstance(v, str) or isinstance(v, int):
        bqry.filter.append(Q("term", **{k: v}))
    else:
        raise Exception(
            f"Condition `{str(k)}={str(v)}` value type is {str(type(v))}, expected to be int, str or list.")
    
print(bqry)