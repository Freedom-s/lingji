# 前后页召回 400 错误审查

## 现象

线上每次知识库问答都会出现：

```text
[EVALUATE_PAGE] 页面评估失败: 'NoneType' object is not subscriptable，使用默认值
```

页面评估失败后，代码返回默认值 `needs_prev_page=False`、`needs_next_page=False`，因此前后页不会被召回；主检索和最终回答仍可能成功，所以表面上容易被误判为“召回偶发失败”。

## 根因

前后页评估调用 `chat_mdl.chat_with_tools()` 时传入了：

```python
"tool_choice": "auto"
```

但线上 VLLM 进程实际以如下参数启动：

```text
vllm serve /root/siton-tmp/models/Qwen3-VL-4B-Instruct \
  --served-model-name Qwen3-VL-4B-Instruct \
  --host 0.0.0.0 --port 8000 \
  --max-model-len 32768 --gpu-memory-utilization 0.95
```

启动参数中没有 `--enable-auto-tool-choice` 和 `--tool-call-parser`。

## 复现证据

在线上环境向 `http://10.15.25.201:27100/v1` 发送相同的最小工具调用请求，VLLM 返回：

```text
400 BadRequestError:
"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set
```

应用层 `Base.chat_with_tools()` 将该错误包装成：

```python
{
    "content": "**ERROR**: Error code: 400 ...",
    "tool_calls": None,
}
```

而 `_recall_context_pages()` 只判断了 `"tool_calls" in response`，没有判断其值是否为列表，随后执行 `response["tool_calls"][0]`，于是产生误导性的：

```text
TypeError: 'NoneType' object is not subscriptable
```

## 排除项

- 线上 ES 的相邻页范围查询正常：同一文档第 1 页可以查询到第 2 页。
- 失败发生在 VLLM 工具调用请求阶段，早于前后页 ES 查询。
- 不是模型“没有判断出需要前后页”，而是模型服务根本没有接受本次工具调用请求。

## 修复建议（本次未执行）

1. 重启 VLLM 时启用自动工具调用，并指定与当前 Qwen3 模型匹配的 parser。当前安装包提供 `qwen3_xml`，建议优先在停机窗口验证：

   ```text
   --enable-auto-tool-choice --tool-call-parser qwen3_xml
   ```

2. 同时修正应用层防御逻辑：只有当 `tool_calls` 是非空列表时才访问 `[0]`，否则记录完整错误并走默认值，避免再次出现 `NoneType` 掩盖真实错误。

3. 重启后用一条带图片的页面评估请求验证：应返回 `evaluate_page_context` 的工具调用，并在日志中看到前页或后页的 ES 查询记录。

## 状态

已完成根因定位和线上复现；未修改线上服务、未重启 VLLM、未部署修复。
