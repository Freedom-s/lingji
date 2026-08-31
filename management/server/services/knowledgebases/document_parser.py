import base64
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime
from io import BytesIO, StringIO
from urllib.parse import urlparse

import requests
from database import MINIO_CONFIG, get_es_client, get_minio_client
from elasticsearch.helpers import bulk
from magic_pdf.config.enums import SupportedPdfParseMethod
from magic_pdf.data.data_reader_writer import FileBasedDataReader, FileBasedDataWriter
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.data.read_api import read_local_images, read_local_office
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze

from . import logger
from .excel_parser import parse_excel_file
from .generation import generate_all_for_document
from .jieba_tokenizer import JiebaTokenizer # 使用jieba分词来做
from .utils import _create_task_record, _update_document_progress, _update_kb_chunk_count, generate_uuid, get_bbox_from_block

# tknzr = RagTokenizer()
tknzr = JiebaTokenizer() # 改用普通的jieba分词来做

# OCR 服务地址（host/port 从 .env 读取，默认 localhost:8888）
OCR_HOST = os.getenv("OCR_HOST", "localhost")
OCR_PORT = os.getenv("OCR_PORT", "8888")
OCR_URL = f"http://{OCR_HOST}:{OCR_PORT}/file_parse"

# OCR 并发页面的最大并发数
OCR_MAX_WORKERS = 2

# Embedding 并发请求的最大并发数
EMBEDDING_MAX_WORKERS = 4

def tokenize_text(text):
    """使用分词器对文本进行分词"""
    return tknzr.tokenize(text)


@contextmanager
def capture_stdout_stderr(doc_id):
    """捕获标准输出和标准错误，并实时更新到数据库"""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    
    # 创建字符串缓冲区
    stdout_buffer = StringIO()
    stderr_buffer = StringIO()
    
    # 自定义输出类，实时捕获并更新进度
    class ProgressCapture:
        def __init__(self, original, buffer, doc_id):
            self.original = original
            self.buffer = buffer
            self.doc_id = doc_id
            self.last_update = time.time()
            # 添加必要的属性以兼容标准输出流
            self.encoding = getattr(original, 'encoding', 'utf-8')
            self.errors = getattr(original, 'errors', 'strict')
            self.mode = getattr(original, 'mode', 'w')
            
        def write(self, text):
            self.original.write(text)  # 保持原有输出
            self.buffer.write(text)
            
            # 检查是否包含进度信息
            if any(keyword in text for keyword in ['Predict:', '%|', 'Processing pages:', 'OCR-', 'MFD', 'MFR', 'Table', 'it/s]', 'INFO']):
                # 清理文本，移除ANSI转义序列和多余的空白字符
                clean_text = re.sub(r'\x1b\[[0-9;]*m', '', text.strip())
                clean_text = re.sub(r'\s+', ' ', clean_text)  # 合并多个空白字符
                
                if clean_text and len(clean_text) > 5:  # 过滤掉太短的文本
                    current_time = time.time()
                    # 限制更新频率，避免过于频繁的数据库操作
                    if current_time - self.last_update > 0.3:  # 每0.3秒最多更新一次
                        try:
                            # 提取关键信息，优先显示进度条信息
                            if '%|' in clean_text and ('Predict:' in clean_text or 'Processing' in clean_text):
                                # 这是进度条信息，直接使用
                                _update_document_progress(self.doc_id, message=clean_text[:500])
                            elif 'INFO' in clean_text and any(x in clean_text for x in ['处理', '解析', '提取']):
                                # 这是重要的处理信息
                                _update_document_progress(self.doc_id, message=clean_text[:500])
                            else:
                                # 其他信息也更新，但优先级较低
                                _update_document_progress(self.doc_id, message=clean_text[:500])
                            
                            self.last_update = current_time
                        except Exception as e:
                            logger.error(f"[Parser-ERROR] 更新进度消息失败: {e}")
            
        def flush(self):
            self.original.flush()
            
        def __getattr__(self, name):
            # 代理其他属性到原始输出流
            return getattr(self.original, name)
    
    try:
        # 替换标准输出和错误输出
        sys.stdout = ProgressCapture(old_stdout, stdout_buffer, doc_id)
        sys.stderr = ProgressCapture(old_stderr, stderr_buffer, doc_id)
        yield stdout_buffer, stderr_buffer
    finally:
        # 恢复原始输出
        sys.stdout = old_stdout
        sys.stderr = old_stderr


def _process_single_page_ocr(item, bucket_name, minio_client):
    """处理单个页面的 OCR：从 MinIO 拉取图片 → 调用 OCR 服务 → 返回结果"""
    item_id = item.get("id")
    item_file_id = item.get("file_id")
    item_location = item.get("location")
    item_page_number = item.get("page_number")
    item_minio_url = f"minio://{bucket_name}/{item_location}"

    minio_response = None
    item_base64 = None
    item_content = ""

    try:
        basename = os.path.basename(item_location)
        minio_response = minio_client.get_object(bucket_name, item_location)
        image_data = minio_response.read()
        item_base64 = base64.b64encode(image_data).decode("utf-8")
        ocr_response = requests.post(
            OCR_URL,
            files={"file": (basename, BytesIO(image_data), "image/jpeg")},
            timeout=60,
        )
        ocr_response.raise_for_status()
        item_content = ocr_response.json().get("md_content") or ""
        item_content = re.sub(r"!\[\]\(images/[^\)]+\)", "", item_content)
    except Exception as e:
        item_content = ""
        logger.error(f"[Parser-ERROR] OCR解析失败 {item_location}: {e}")
    finally:
        if minio_response:
            minio_response.close()
            minio_response.release_conn()

    item_base64_data_url = f"data:image/jpeg;base64,{item_base64}" if item_base64 else None

    return {
        "id": item_id,
        "file_id": item_file_id,
        "page_content": item_content,
        "location": item_minio_url,
        "page_number": item_page_number,
        "image_base64": item_base64_data_url,
    }


def _generate_in_background(doc_id, full_content, page_count, tenant_id):
    """在后台线程中生成课件内容（思维导图、闪卡、测验），失败不影响解析结果"""
    try:
        logger.info(f"[Parser-INFO] 后台开始为文档 {doc_id} 生成课件内容")
        generate_all_for_document(doc_id, full_content, page_count, tenant_id)
    except Exception as gen_err:
        logger.error(f"[Parser-ERROR] 课件内容生成失败（不影响解析）: {gen_err}")


def perform_parse(doc_id, doc_info, file_info, embedding_config, kb_info, pages_info):
    """
    目前以文本为中心的RAG是这样一个流程：
    1.获取embedding配置
    2.获取minio中的文件
    3.使用mineru解析整个文件
    4.获取到文件的分块情况
    5.整个文件的分块结果和向量，存储到es中

    如果我要做以文档页面为中心的流程：
    1.获取qwen3-vl的embedding配置
    2.获取minio中的图片列表
    3.遍历图片列表，然后调用qwen3-vl-embedding（或者也可以调用mineru来获取文字），将图片转化为向量。
    - 通过ocr来获取一个页面中的文字信息，然后调用qwen3-vl-textencoder来获取文字向量
    - 通过qwen3-vl-imageencoder来获取整张页面的视觉向量。
    
    4.每一页就是一个天然的chunk
    5.存入es中。

    执行文档解析的核心逻辑

    Args:
        doc_id (str): 文档ID.
        doc_info (dict): 包含文档信息的字典 (name, location, type, kb_id, parser_config, created_by).
        file_info (dict): 包含文件信息的字典 (parent_id/bucket_name).
        kb_info (dict): 包含知识库信息的字典 (created_by).

    Returns:
        dict: 包含解析结果的字典 (success, chunk_count).
    """
    temp_pdf_path = None
    temp_image_dir = None
    start_time = time.time()

    # embedding模型名字
    embedding_model_name = embedding_config.get("llm_name")
    # embedding模型的地址
    embedding_api_base = embedding_config.get("api_base")
    # embedding模型的api
    embedding_api_key = embedding_config.get("api_key")

    # 构建完整的 Embedding API URL，后面需要发送request请求
    embedding_url = None
    if embedding_api_base:
        # 删除掉末尾的/
        normalized_base_url = embedding_api_base.rstrip("/")
        if normalized_base_url.endswith("/v1"):
            embedding_url = normalized_base_url + "/embeddings"
        elif normalized_base_url.endswith("/embeddings"):
            embedding_url = normalized_base_url
        else:
            embedding_url = normalized_base_url + "/v1/embeddings"

    logger.info(f"[Parser-INFO] 使用 Embedding 配置: URL='{embedding_url}', Model='{embedding_model_name}', Key={embedding_api_key}")

    try:
        kb_id = doc_info["kb_id"]
        file_location = doc_info["location"] # 这里是不包含桶的
        _, file_extension = os.path.splitext(file_location)
        file_type = doc_info["type"].lower()
        bucket_name = file_info["parent_id"]  # 文件存储的桶是 parent_id
        tenant_id = kb_info["created_by"]  # 知识库创建者作为 tenant_id

        # 这个函数是专门用来更新document表的，更新他的progress——msg字段
        def update_progress(prog=None, msg=None):
            _update_document_progress(doc_id, progress=prog, message=msg)
            logger.info(f"[Parser-PROGRESS] Doc: {doc_id}, Progress: {prog}, Message: {msg}")

        # 1. 从 MinIO 获取文件内容
        minio_client = get_minio_client()
        if not minio_client.bucket_exists(bucket_name):
            raise Exception(f"存储桶不存在: {bucket_name}")

        update_progress(0.05, f"正在从存储中获取文件页面: {file_location}")

        # 预先把所有的页面给处理好吧
        """
        [
            id: pageid
            page_content: 页面中的所有文字信息
            file_id: 当前的这个页面所属于的文件id
            page_number: 当前属于哪个页面
            location: minio://localhost:9000/bucket/location  (提供一个完整的minio_url) 到时候传递给embedding来进行计算，直接返回结果。
        ]
        """
        # 并发 OCR：MinIO 拉取 + OCR 调用都是 I/O 密集型，并行处理大幅提速
        update_progress(0.1, f"并发处理 {len(pages_info)} 个页面的OCR...")
        file_pages_info = []
        with ThreadPoolExecutor(max_workers=OCR_MAX_WORKERS) as ocr_executor:
            futures = {
                ocr_executor.submit(_process_single_page_ocr, item, bucket_name, minio_client): item
                for item in pages_info
            }
            for future in as_completed(futures):
                file_pages_info.append(future.result())

        # 按页码排序，保持顺序一致
        file_pages_info.sort(key=lambda p: p["page_number"])
        print(f"页面ocr的结果: 共{len(file_pages_info)}个页面")
        # 打印简要信息，避免输出大量base64数据
        for page in file_pages_info[:3]:  # 只打印前3页的简要信息
            print(f"  - 页面 {page['page_number']}: ID={page['id']}, 内容长度={len(page['page_content'])}, 图片base64长度={len(page.get('image_base64', ''))}")
        if len(file_pages_info) > 3:
            print(f"  ... 以及其他 {len(file_pages_info) - 3} 个页面")
        update_progress(0.35, "文件页面已经进行了ocr解析")

        # 下一步，我需要去进行页面和文字的嵌入
        # 先去调用一次来获取embedding向量维度
        embedding_dim = None
        try:
            test_content = "test"
            headers = {"Content-Type": "application/json"}
            if embedding_api_key:
                headers["Authorization"] = f"Bearer {embedding_api_key}"
            # 这个调用qwen-vl的请求，最好有超时时间的限制，因为这个比较慢
            test_resp = requests.post(
                embedding_url,
                headers=headers,
                json={"model": embedding_model_name, "input": test_content}
            )
            test_resp.raise_for_status()
            test_data = test_resp.json()
            test_vec = test_data["data"][0]["embedding"]
            embedding_dim = len(test_vec)
            logger.info(f"[Parser-INFO] 检测到embedding维度: {embedding_dim}")
            
        except Exception as e:
            logger.error(f"[Parser-ERROR] 获取embedding维度失败: {e}")
            raise Exception(f"[Parser-ERROR] 获取embedding维度失败: {e}")

        update_progress(0.4, "获取embedding嵌入维度成功")

        # 3. 进行嵌入，保存结果 (存储到ES)
        update_progress(0.45, "准备Elasticsearch索引")
        es_client = get_es_client()
        index_name = f"ragflow_{tenant_id}" #es中的名称
        vector_text_field_name = f"text_{embedding_dim}_vec" #es的维度
        vector_image_field_name = f"image_{embedding_dim}_vec"
        # 创建es中的索引
        if not es_client.indices.exists(index=index_name):
            es_client.indices.create(
                index=index_name,
                body={
                    "settings": {
                        "number_of_shards": 1, # 这里可以设置这个索引的分片数量，后续做候选的时候有用，默认情况下是一个分片
                        "number_of_replicas": 0 # 分片副本，这个主要是给主分片做备份的，防止数据丢失和提升检索效率。但是会增加存储空间压力
                    }, #副本数量
                    "mappings": {
                        "properties": {
                            "page_id": {"type": "keyword"}, # 页面的id
                            "doc_id": {"type": "keyword"},  # 设置doc_id为关键词字段，不分词
                            "kb_id": {"type": "keyword"},  # 设置kb_id为关键词字段，也不分词
                            "content_with_weight": {"type": "text"}, 
                            vector_text_field_name: {"type": "dense_vector", "dims": embedding_dim}, # 文字的向量
                            vector_image_field_name: {"type": "dense_vector", "dims": embedding_dim} # 图片的向量
                        }
                    },
                },
            )
            logger.info(f"[Parser-INFO] 创建Elasticsearch索引: {index_name}, 向量维度: {embedding_dim}")
        else:
            # 检查现有索引是否包含当前维度的向量字段
            try:
                mapping = es_client.indices.get_mapping(index=index_name)
                existing_properties = mapping[index_name]["mappings"]["properties"]
                
                if vector_text_field_name not in existing_properties:
                    # 添加新的向量字段
                    es_client.indices.put_mapping(
                        index=index_name,
                        body={
                            "properties": {
                                vector_text_field_name: {"type": "dense_vector", "dims": embedding_dim}
                            }
                        }
                    )
                    logger.info(f"[Parser-INFO] 为索引 {index_name} 添加新向量字段: {vector_text_field_name}, 维度: {embedding_dim}")
                if vector_image_field_name not in existing_properties:
                    # 添加新的向量字段
                    es_client.indices.put_mapping(
                        index=index_name,
                        body={
                            "properties": {
                                vector_image_field_name: {"type": "dense_vector", "dims": embedding_dim}
                            }
                        }
                    )
                    logger.info(f"[Parser-INFO] 为索引 {index_name} 添加新向量字段: {vector_image_field_name}, 维度: {embedding_dim}")
            except Exception as e:
                logger.error(f"[Parser-ERROR] 更新索引映射失败: {e}")
                raise Exception(f"[Parser-ERROR] 更新索引映射失败: {e}")

        # 最后一步，调用嵌入模型，获取嵌入向量，然后存储到es里面
        # 使用并发处理提高效率
        def get_page_embedding(page_data):
            """获取单个页面的embedding向量"""
            page_id = page_data['id']
            page_content = page_data['page_content']
            page_image_base64 = page_data.get('image_base64')

            try:
                headers = {"Content-Type": "application/json"}
                if embedding_api_key:
                    headers["Authorization"] = f"Bearer {embedding_api_key}"

                embedding_resp = requests.post(
                    embedding_url,
                    headers=headers,
                    json={
                        "model": embedding_model_name,
                        "input": [page_content, page_image_base64]
                    },
                    timeout=60  # 添加超时限制
                )
                embedding_resp.raise_for_status()
                embedding_data = embedding_resp.json()
                embedding_text_vec, embedding_image_vec = embedding_data["data"][0]["embedding"], embedding_data["data"][1]["embedding"]

                # 检查向量维度是否与预期一致
                if len(embedding_text_vec) != embedding_dim or len(embedding_image_vec) != embedding_dim:
                    error_msg = f"[Parser-ERROR] Embedding向量维度不一致，预期: {embedding_dim}，实际: {len(embedding_text_vec)}"
                    return {"success": False, "error": error_msg, "page_id": page_id}

                logger.info(f"[Parser-INFO] 页面 {page_id} embedding获取成功，维度: {len(embedding_text_vec)}")
                return {
                    "success": True,
                    "page_id": page_id,
                    "embedding_text_vec": embedding_text_vec,
                    "embedding_image_vec": embedding_image_vec
                }
            except Exception as e:
                logger.error(f"[Parser-ERROR] 页面 {page_id} 获取embedding失败: {e}")
                return {"success": False, "error": str(e), "page_id": page_id}

        # 并发获取所有页面的embedding
        embedding_results = []
        update_progress(0.5, f"并发获取{len(file_pages_info)}个页面的embedding向量...")

        with ThreadPoolExecutor(max_workers=EMBEDDING_MAX_WORKERS) as executor:
            # 提交所有任务
            future_to_page = {executor.submit(get_page_embedding, page_data): page_data for page_data in file_pages_info}

            # 收集结果
            for future in as_completed(future_to_page):
                result = future.result()
                if result["success"]:
                    embedding_results.append(result)
                else:
                    # 如果有失败的任务，抛出异常
                    error_msg = result.get("error", "未知错误")
                    raise Exception(f"[Parser-ERROR] 页面 {result['page_id']} embedding获取失败: {error_msg}")

        update_progress(0.85, f"成功获取{len(embedding_results)}个页面的embedding向量")

        # 将embedding结果批量存储到ES（bulk API 比逐条 index 快数倍）
        page_ids_list = []
        page_data_map = {page["id"]: page for page in file_pages_info}

        current_time_es = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_timestamp_es = datetime.now().timestamp()

        bulk_actions = []
        for result in embedding_results:
            page_id = result["page_id"]
            page_data = page_data_map[page_id]
            chunk_id = generate_uuid()
            page_ids_list.append(chunk_id)

            bulk_actions.append({
                "_index": index_name,
                "_id": chunk_id,
                "_source": {
                    "page_id": page_id,
                    "doc_id": doc_id,
                    "kb_id": kb_id,
                    "docnm_kwd": doc_info["name"],
                    "content_with_weight": page_data["page_content"],
                    "content_ltks": tokenize_text(page_data["page_content"]),
                    "page_num_int": page_data["page_number"],
                    "create_time": current_time_es,
                    "create_timestamp_flt": current_timestamp_es,
                    "img_url": page_data["location"],
                    vector_text_field_name: result["embedding_text_vec"],
                    vector_image_field_name: result["embedding_image_vec"],
                },
            })

        if bulk_actions:
            chunk_size = 50
            success_count, errors = bulk(es_client, bulk_actions, chunk_size=chunk_size)
            if errors:
                error_details = "; ".join(str(e) for e in errors[:3])
                raise Exception(f"[Parser-ERROR] ES 批量写入失败: {error_details}")
            logger.info(f"[Parser-INFO] ES 批量写入成功，{success_count} 条记录")

        page_count = len(page_ids_list)

        # 打印匹配总结信息
        logger.info(f"[Parser-INFO] 共处理 {page_count} 个页面。")

        # 5. 更新最终状态
        process_duration = time.time() - start_time
        _update_document_progress(doc_id, progress=1.0, message="解析完成", status="1", run="3", chunk_count=page_count, process_duration=process_duration)
        _update_kb_chunk_count(kb_id, page_count)  # 更新知识库总块数
        _create_task_record(doc_id, page_ids_list)  # 创建task记录

        update_progress(1.0, "解析完成")
        logger.info(f"[Parser-INFO] 解析完成，文档ID: {doc_id}, 耗时: {process_duration:.2f}s, 块数: {page_count}")

        # 6. 启动后台线程异步生成课件内容（思维导图、闪卡、测验），不阻塞解析完成
        all_page_contents = [page["page_content"] for page in file_pages_info if page.get("page_content")]
        full_content = "\n\n".join(all_page_contents)
        if len(full_content.strip()) > 100:
            update_progress(1.0, "解析完成，课件内容将在后台生成...")
            threading.Thread(
                target=_generate_in_background,
                args=(doc_id, full_content, page_count, tenant_id),
                daemon=True,
            ).start()
        else:
            logger.warning(f"[Parser-WARNING] 文档 {doc_id} 内容过少，跳过生成")

        return {"success": True, "chunk_count": page_count}
    except Exception as e:
        process_duration = time.time() - start_time
        # error_message = f"解析失败: {str(e)}"
        logger.error(f"[Parser-ERROR] 文档 {doc_id} 解析失败: {e}")
        error_message = f"解析失败: {e}"
        # 更新文档状态为失败
        _update_document_progress(doc_id, status="1", run="0", message=error_message, process_duration=process_duration)  # status=1表示完成，run=0表示失败
        return {"success": False, "error": error_message}

    finally:
        # 清理临时文件
        try:
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
            if temp_image_dir and os.path.exists(temp_image_dir):
                shutil.rmtree(temp_image_dir, ignore_errors=True)
        except Exception as clean_e:
            logger.error(f"[Parser-WARNING] 清理临时文件失败: {clean_e}")
