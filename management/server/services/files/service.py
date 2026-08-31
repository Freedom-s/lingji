import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from database import get_db_connection, get_minio_client, get_redis_connection

from .utils import FileSource, FileType, get_uuid

# redis配置参数
UPLOAD_TEMP_DIR = os.getenv("UPLOAD_TEMP_DIR", tempfile.gettempdir())
CHUNK_EXPIRY_SECONDS = 3600 * 24  # 分块24小时过期

temp_dir = tempfile.gettempdir()
UPLOAD_FOLDER = os.path.join(temp_dir, "uploads")
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "jpg", "jpeg", "png", "bmp", "txt", "md", "html", "csv", "mp4", "webm", "mov"}
IMAGE_EXTES = {"jpg", "jpeg", "png", "bmp"}
VIDEO_EXTES = {"mp4", "webm", "mov"}


def allowed_file(filename):
    """Check if the file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def filename_type(filename):
    """根据文件名确定文件类型"""
    ext = os.path.splitext(filename)[1].lower()

    if ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp"]:
        return FileType.VISUAL.value
    elif ext in [".pdf"]:
        return FileType.PDF.value
    elif ext in [".doc", ".docx"]:
        return FileType.WORD.value
    elif ext in [".xls", ".xlsx", ".csv"]:
        return FileType.EXCEL.value
    elif ext in [".ppt", ".pptx"]:
        return FileType.PPT.value
    elif ext in [".txt", ".md"]:
        return FileType.TEXT.value
    elif ext in [".html"]:
        return FileType.HTML.value
    elif ext in [".mp4", ".webm", ".mov"]:
        return FileType.VIDEO.value

    return FileType.OTHER.value


def get_files_list(current_page, page_size, name_filter="", sort_by="create_time", sort_order="desc"):
    """
    获取文件列表

    Args:
        current_page: 当前页码
        page_size: 每页大小
        name_filter: 文件名过滤条件
        sort_by: 排序字段
        sort_order: 排序方式

    Returns:
        tuple: (文件列表, 总数)
    """
    try:
        # 获取当前登录用户ID
        from auth import get_current_user
        current_user = get_current_user()
        if not current_user:
            return [], 0

        user_id = current_user['user_id']

        # 计算偏移量
        offset = (current_page - 1) * page_size

        # 连接数据库
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 构建查询条件
        where_clause = "WHERE f.type != 'folder' AND f.tenant_id = %s"  # 排除文件夹类型，只查询当前用户的文件
        params = [user_id]

        if name_filter:
            where_clause += " AND f.name LIKE %s"
            params.append(f"%{name_filter}%")

        # 验证排序字段
        valid_sort_fields = ["name", "size", "type", "create_time", "create_date"]
        if sort_by not in valid_sort_fields:
            sort_by = "create_time"

        # 构建排序子句
        sort_clause = f"ORDER BY f.{sort_by} {sort_order.upper()}"

        # 查询总数
        count_query = f"""
            SELECT COUNT(*) as total
            FROM file f
            {where_clause}
        """
        cursor.execute(count_query, params)
        total = cursor.fetchone()["total"]

        # 查询文件列表
        query = f"""
            SELECT f.id, f.name, f.parent_id, f.type, f.size, f.location, f.source_type, f.create_time, f.create_date
            FROM file f
            {where_clause}
            {sort_clause}
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [page_size, offset])
        files = cursor.fetchall()

        # 格式化 create_date
        for file_item in files:
            if isinstance(file_item.get("create_date"), datetime):
                file_item["create_date"] = file_item["create_date"].strftime("%Y-%m-%d %H:%M:%S")

        cursor.close()
        conn.close()

        return files, total

    except Exception as e:
        raise e


def get_file_info(file_id):
    """
    获取文件信息

    Args:
        file_id: 文件ID

    Returns:
        dict: 文件信息
    """
    try:
        # 连接数据库
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 查询文件信息
        cursor.execute(
            """
            SELECT id, name, parent_id, type, size, location, source_type
            FROM file
            WHERE id = %s
        """,
            (file_id,),
        )

        file = cursor.fetchone()
        cursor.close()
        conn.close()

        return file

    except Exception as e:
        raise e


def download_file_from_minio(file_id):
    """
    从MinIO下载文件

    Args:
        file_id: 文件ID

    Returns:
        tuple: (文件数据, 文件名)
    """
    try:
        # 获取当前登录用户ID
        from auth import get_current_user
        current_user = get_current_user()
        if not current_user:
            raise Exception("获取当前用户信息失败")

        user_id = current_user['user_id']

        # 获取文件信息，添加租户过滤
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, parent_id, name, location, type
            FROM file
            WHERE id = %s AND tenant_id = %s
        """,
            (file_id, user_id),
        )

        file = cursor.fetchone()
        cursor.close()
        conn.close()

        if not file:
            raise Exception(f"文件 {file_id} 不存在或无权访问")

        # 从MinIO下载文件
        minio_client = get_minio_client()

        # 使用parent_id作为存储桶
        storage_bucket = file["parent_id"]
        storage_location = file["location"]

        # 检查bucket是否存在
        if not minio_client.bucket_exists(storage_bucket):
            raise Exception(f"存储桶 {storage_bucket} 不存在")

        # 下载文件
        response = minio_client.get_object(storage_bucket, storage_location)
        file_data = response.read()

        return file_data, file["name"]

    except Exception as e:
        raise e


def delete_file(file_id):
    """
    删除文件

    Args:
        file_id: 文件ID

    Returns:
        bool: 是否删除成功
    """
    try:
        # 获取当前登录用户ID
        from auth import get_current_user
        current_user = get_current_user()
        if not current_user:
            raise Exception("获取当前用户信息失败")

        user_id = current_user['user_id']

        # 连接数据库
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 查询文件信息，添加租户过滤
        cursor.execute(
            """
            SELECT id, parent_id, name, location, type
            FROM file
            WHERE id = %s AND tenant_id = %s
        """,
            (file_id, user_id),
        )

        file = cursor.fetchone()
        if not file:
            cursor.close()
            conn.close()
            return False

        # 如果是文件夹，直接返回成功（不处理文件夹）
        if file["type"] == FileType.FOLDER.value:
            cursor.close()
            conn.close()
            return True

        # 查询关联的document记录
        cursor.execute(
            """
            SELECT f2d.document_id, d.kb_id, d.location
            FROM file2document f2d
            JOIN document d ON f2d.document_id = d.id
            WHERE f2d.file_id = %s
        """,
            (file_id,),
        )

        document_mappings = cursor.fetchall()

        # 查询关联的file_page记录（页面图片）
        cursor.execute(
            """
            SELECT location
            FROM file_page
            WHERE file_id = %s
        """,
            (file_id,),
        )

        page_mappings = cursor.fetchall()

        # 创建MinIO客户端
        minio_client = get_minio_client()

        # 开始事务
        try:
            cursor.execute("START TRANSACTION")

            # 1. 先删除file表中的记录
            cursor.execute("DELETE FROM file WHERE id = %s", (file_id,))

            # 2. 删除关联的file2document记录
            cursor.execute("DELETE FROM file2document WHERE file_id = %s", (file_id,))

            # 3. 删除关联的file_page记录（页面图片）
            cursor.execute("DELETE FROM file_page WHERE file_id = %s", (file_id,))

            # 4. 删除关联的document记录
            for doc_mapping in document_mappings:
                cursor.execute("DELETE FROM document WHERE id = %s", (doc_mapping["document_id"],))

            # 提交事务
            cursor.execute("COMMIT")

            # 从MinIO删除文件（在事务提交后进行）
            try:
                # 检查bucket是否存在，如果不存在则跳过MinIO删除操作
                parent_id = file.get("parent_id")
                if parent_id and minio_client.bucket_exists(parent_id):
                    try:
                        # 删除原始文件（source）
                        minio_client.remove_object(parent_id, file["location"])
                        print(f"从MinIO删除原始文件成功: {parent_id}/{file['location']}")
                    except Exception as e:
                        print(f"从MinIO删除原始文件失败: {parent_id}/{file['location']} - {str(e)}")

                    # 删除所有页面图片（pages）
                    for page_mapping in page_mappings:
                        page_location = page_mapping.get("location")
                        if page_location:
                            try:
                                minio_client.remove_object(parent_id, page_location)
                                print(f"从MinIO删除页面图片成功: {parent_id}/{page_location}")
                            except Exception as e:
                                print(f"从MinIO删除页面图片失败: {parent_id}/{page_location} - {str(e)}")
                else:
                    print(f"存储桶不存在，跳过MinIO删除操作: {parent_id}")

                # 如果有关联的document，也删除document存储的文件
                for doc_mapping in document_mappings:
                    kb_id = doc_mapping.get("kb_id")
                    doc_location = doc_mapping.get("location")
                    if kb_id and doc_location and minio_client.bucket_exists(kb_id):
                        try:
                            minio_client.remove_object(kb_id, doc_location)
                            print(f"从MinIO删除document文件成功: {kb_id}/{doc_location}")
                        except Exception as e:
                            print(f"从MinIO删除document文件失败: {kb_id}/{doc_location} - {str(e)}")
                    else:
                        print(f"document存储桶不存在或位置为空，跳过MinIO删除操作: {kb_id}/{doc_location}")
            except Exception as e:
                # 即使MinIO删除失败，也不影响数据库操作的成功
                print(f"MinIO操作失败，但不影响数据库删除: {str(e)}")

            return True

        except Exception as e:
            # 回滚事务
            try:
                cursor.execute("ROLLBACK")
            except:  # noqa: E722
                pass
            raise e

        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        print(f"删除文件时发生错误: {str(e)}")
        raise e


def batch_delete_files(file_ids):
    """
    批量删除文件

    Args:
        file_ids: 文件ID列表

    Returns:
        int: 成功删除的文件数量
    """
    if not file_ids:
        return 0

    try:
        # 获取当前登录用户ID
        from auth import get_current_user
        current_user = get_current_user()
        if not current_user:
            raise Exception("获取当前用户信息失败")

        user_id = current_user['user_id']

        # 连接数据库
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 创建MinIO客户端
        minio_client = get_minio_client()

        # 第一步：收集所有需要删除的文件信息（在删除前）
        files_to_delete = []
        for file_id in file_ids:
            cursor.execute(
                """
                SELECT id, parent_id, name, location, type
                FROM file
                WHERE id = %s AND tenant_id = %s
                """,
                (file_id, user_id),
            )
            file = cursor.fetchone()
            if not file or file["type"] == FileType.FOLDER.value:
                continue

            # 查询关联的document记录
            cursor.execute(
                """
                SELECT f2d.document_id, d.kb_id, d.location
                FROM file2document f2d
                JOIN document d ON f2d.document_id = d.id
                WHERE f2d.file_id = %s
            """,
                (file_id,),
            )
            document_mappings = cursor.fetchall()

            # 查询关联的file_page记录（页面图片）
            cursor.execute(
                """
                SELECT location
                FROM file_page
                WHERE file_id = %s
            """,
                (file_id,),
            )
            page_mappings = cursor.fetchall()

            files_to_delete.append({
                "file": file,
                "documents": document_mappings,
                "pages": page_mappings
            })

        # 第二步：开始事务删除数据库记录
        try:
            cursor.execute("START TRANSACTION")

            for file_info in files_to_delete:
                file_id = file_info["file"]["id"]

                # 1. 删除file表中的记录
                cursor.execute("DELETE FROM file WHERE id = %s", (file_id,))

                # 2. 删除关联的file2document记录
                cursor.execute("DELETE FROM file2document WHERE file_id = %s", (file_id,))

                # 3. 删除关联的file_page记录
                cursor.execute("DELETE FROM file_page WHERE file_id = %s", (file_id,))

                # 4. 删除关联的document记录
                for doc_mapping in file_info["documents"]:
                    cursor.execute("DELETE FROM document WHERE id = %s", (doc_mapping["document_id"],))

            # 提交事务
            cursor.execute("COMMIT")

            # 第三步：从MinIO删除文件（在事务提交后进行）
            for file_info in files_to_delete:
                file = file_info["file"]
                parent_id = file.get("parent_id")

                if parent_id and minio_client.bucket_exists(parent_id):
                    try:
                        # 删除原始文件（source）
                        minio_client.remove_object(parent_id, file["location"])
                        print(f"从MinIO删除原始文件成功: {parent_id}/{file['location']}")
                    except Exception as e:
                        print(f"从MinIO删除原始文件失败: {parent_id}/{file['location']} - {str(e)}")

                    # 删除所有页面图片（pages）
                    for page_mapping in file_info["pages"]:
                        page_location = page_mapping.get("location")
                        if page_location:
                            try:
                                minio_client.remove_object(parent_id, page_location)
                                print(f"从MinIO删除页面图片成功: {parent_id}/{page_location}")
                            except Exception as e:
                                print(f"从MinIO删除页面图片失败: {parent_id}/{page_location} - {str(e)}")

                # 删除document存储的文件
                for doc_mapping in file_info["documents"]:
                    kb_id = doc_mapping.get("kb_id")
                    doc_location = doc_mapping.get("location")
                    if kb_id and doc_location and minio_client.bucket_exists(kb_id):
                        try:
                            minio_client.remove_object(kb_id, doc_location)
                            print(f"从MinIO删除document文件成功: {kb_id}/{doc_location}")
                        except Exception as e:
                            print(f"从MinIO删除document文件失败: {kb_id}/{doc_location} - {str(e)}")

            return len(files_to_delete)

        except Exception as e:
            # 回滚事务
            try:
                cursor.execute("ROLLBACK")
            except:  # noqa: E722
                pass
            raise e

        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        print(f"批量删除文件时发生错误: {str(e)}")
        raise e

# 上传文件，反正只有租户可以创建文件，那我是不是可以这样做呢？还是以租户的id作为桶的名字呢？
# 这样的话，这个用户上传的所有文件，就都放到了自己的桶里面。跟es是一种类似的效果

def upload_files_to_server(files, parent_id=None, user_id=None):
    """
    处理文件上传到服务器的核心逻辑
    
    新功能：
    1. 自动将文档转换为 PDF
    2. 将 PDF 按页拆分为图片
    3. MinIO 分层存储（source/ + pages/）
    4. 保存 file 和 file_page 记录
    
    MinIO 存储结构：
    {parent_id}/                    # Bucket
    └── {file_id}/                  # 文件目录
        ├── source/                 # 原始文件
        │   └── document.pdf
        └── pages/                  # 页面图片
            ├── 0001.jpg
            ├── 0002.jpg
            └── ...
    """
    results = []

    for file in files:
        if file.filename == "":
            continue

        if file and allowed_file(file.filename):
            original_filename = file.filename
            # 修复文件名处理逻辑，保留中文字符
            name, ext = os.path.splitext(original_filename)

            # 只替换文件系统不安全的字符，保留中文和其他Unicode字符
            safe_name = re.sub(r'[\\/:*?"<>|]', "_", name)

            # 如果处理后文件名为空，则使用随机字符串
            if not safe_name or safe_name.strip() == "":
                safe_name = f"file_{get_uuid()[:8]}"

            filename = safe_name + ext.lower()
            filepath = os.path.join(UPLOAD_FOLDER, filename)

            try:
                # 1. 保存文件到本地临时目录
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(filepath)
                print(f"文件已保存到临时目录: {filepath}")

                # 2. 判断文件类型，图片/视频文件特殊处理
                file_ext = ext.lower().lstrip('.')
                is_image = file_ext in IMAGE_EXTES
                is_video = file_ext in VIDEO_EXTES

                if is_video:
                    # 视频文件：直接存储原始文件，不做转换
                    print(f"检测到视频文件: {filename}，跳过 PDF/图片转换")
                    page_images = []  # 视频没有页面图片

                elif is_image:
                    # 图片文件：直接读取，不转换为 PDF
                    print(f"检测到图片文件: {filename}，跳过 PDF 转换")
                    from PIL import Image
                    
                    # 读取图片信息
                    with Image.open(filepath) as img:
                        width, height = img.size
                        img_format = img.format or "JPEG"
                        
                        # 读取图片字节数据
                        with open(filepath, 'rb') as f:
                            img_bytes = f.read()
                    
                    # 构造页面图片列表（只有一页）
                    page_images = [(img_bytes, width, height)]
                    print(f"图片信息: {width}x{height}, 格式: {img_format}, 大小: {len(img_bytes)} 字节")
                else:
                    # 非图片文件：转换为 PDF，再转为图片
                    from services.files.converters.pdf_converter import convert_file
                    print(f"开始转换文件为 PDF: {filename}")
                    pdf_bytes = convert_file(filepath)
                    print(f"PDF 转换完成，大小: {len(pdf_bytes)} 字节")

                    # 3. PDF 转图片
                    from services.files.converters.image_converter import pdf_to_images
                    print(f"开始生成页面图片: {filename}")
                    page_images = pdf_to_images(pdf_bytes, dpi=150)
                    print(f"生成 {len(page_images)} 页图片")

                # 上面主要是为了生成这样一个图片数组[(img_bytes, width, height)]
                # 4. 生成文件ID和时间戳
                file_id = get_uuid()
                current_time = int(datetime.now().timestamp())
                current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # 5. 上传到 MinIO
                minio_client = get_minio_client()

                # 确保 bucket 存在
                bucket_created = False
                if not minio_client.bucket_exists(parent_id):
                    minio_client.make_bucket(parent_id)
                    bucket_created = True
                    print(f"创建 MinIO 存储桶: {parent_id}")
                
                # 设置桶的公共访问权限（允许读取所有对象）
                if bucket_created or True:  # 每次都设置，确保权限正确
                    import json
                    policy = {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"AWS": "*"},
                                "Action": ["s3:GetObject"],
                                "Resource": [f"arn:aws:s3:::{parent_id}/*"]
                            }
                        ]
                    }
                    minio_client.set_bucket_policy(parent_id, json.dumps(policy))
                    print(f"设置 MinIO 存储桶公共访问权限: {parent_id}")

                # 5.1 上传原始文件到 source/
                source_location = f"{file_id}/source/{filename}"

                # 根据文件扩展名确定 Content-Type
                ext = os.path.splitext(filename)[1].lower()
                content_type_map = {
                    '.pdf': 'application/pdf',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.bmp': 'image/bmp',
                    '.webp': 'image/webp',
                    '.mp4': 'video/mp4',
                    '.webm': 'video/webm',
                    '.mov': 'video/quicktime',
                }
                content_type = content_type_map.get(ext, 'application/octet-stream')

                with open(filepath, "rb") as file_data:
                    minio_client.put_object(
                        bucket_name=parent_id,
                        object_name=source_location,
                        data=file_data,
                        length=os.path.getsize(filepath),
                        content_type=content_type,
                        metadata={'Content-Disposition': 'inline'}  # 设置为inline，浏览器会预览
                    )
                print(f"原始文件已上传: {parent_id}/{source_location}, Content-Type: {content_type}")

                # 5.2 上传页面图片到 pages/
                from io import BytesIO
                page_records = []
                for idx, (img_bytes, width, height) in enumerate(page_images, start=1):
                    # 图片文件使用原始文件名，其他文件使用页码命名
                    if is_image:
                        page_filename = filename
                    else:
                        page_filename = f"{idx:04d}.jpg"
                    
                    page_location = f"{file_id}/pages/{page_filename}"
                    
                    img_stream = BytesIO(img_bytes)
                    minio_client.put_object(
                        bucket_name=parent_id,
                        object_name=page_location,
                        data=img_stream,
                        length=len(img_bytes),
                        content_type="image/jpeg"
                    )
                    print(f"页面图片已上传: {parent_id}/{page_location}")
                    
                    # 准备 page 记录
                    page_records.append({
                        "id": get_uuid(),
                        "file_id": file_id,
                        "page_number": idx,
                        "location": page_location,
                        "size": len(img_bytes),
                        "width": width,
                        "height": height,
                        "format": "JPEG",
                        "create_time": current_time,
                        "create_date": current_date,
                        "update_time": current_time,
                        "update_date": current_date,
                    })

                # 6. 保存数据库记录（事务）
                filetype = filename_type(filename)
                file_record = {
                    "id": file_id,
                    "parent_id": parent_id,
                    "tenant_id": user_id,
                    "created_by": user_id,
                    "name": filename,
                    "type": filetype,
                    "size": os.path.getsize(filepath),
                    "location": source_location,
                    "source_type": FileSource.LOCAL.value,
                    "create_time": current_time,
                    "create_date": current_date,
                    "update_time": current_time,
                    "update_date": current_date,
                }

                conn = get_db_connection()
                try:
                    cursor = conn.cursor()

                    # 6.1 插入 file 记录
                    columns = ", ".join(file_record.keys())
                    placeholders = ", ".join(["%s"] * len(file_record))
                    query = f"INSERT INTO file ({columns}) VALUES ({placeholders})"
                    cursor.execute(query, list(file_record.values()))
                    print(f"文件记录已保存: {file_id}")

                    # 6.2 批量插入 file_page 记录
                    if page_records:
                        columns = ", ".join(page_records[0].keys())
                        placeholders = ", ".join(["%s"] * len(page_records[0]))
                        query = f"INSERT INTO file_page ({columns}) VALUES ({placeholders})"
                        
                        for page_record in page_records:
                            cursor.execute(query, list(page_record.values()))
                        print(f"页面记录已保存: {len(page_records)} 条")

                    conn.commit()

                    results.append({
                        "id": file_id,
                        "name": filename,
                        "size": file_record["size"],
                        "type": filetype,
                        "pages": len(page_images),
                        "status": "success"
                    })

                except Exception as e:
                    conn.rollback()
                    print(f"数据库操作失败: {str(e)}")
                    
                    # 清理 MinIO 中已上传的文件
                    cleanup_minio_files(minio_client, parent_id, file_id)
                    
                    raise
                finally:
                    cursor.close()
                    conn.close()

            except Exception as e:
                results.append({
                    "name": filename,
                    "error": str(e),
                    "status": "failed"
                })
                print(f"文件上传过程中出错: {filename}, 错误: {str(e)}")
            finally:
                # 删除临时文件
                if os.path.exists(filepath):
                    os.remove(filepath)
        else:
            results.append({
                "name": file.filename if file else "unknown",
                "error": "不支持的文件类型",
                "status": "failed"
            })

    return {
        "code": 0,
        "data": results,
        "message": f"成功上传 {len([r for r in results if r['status'] == 'success'])}/{len(files)} 个文件"
    }


def cleanup_minio_files(minio_client, bucket, file_id):
    """
    清理 MinIO 中的文件（上传失败时回滚）
    
    Args:
        minio_client: MinIO 客户端
        bucket: 存储桶名称
        file_id: 文件ID
    """
    try:
        # 删除 source 目录
        objects = minio_client.list_objects(bucket, prefix=f"{file_id}/source/", recursive=True)
        for obj in objects:
            minio_client.remove_object(bucket, obj.object_name)
            print(f"已清理: {bucket}/{obj.object_name}")
        
        # 删除 pages 目录
        objects = minio_client.list_objects(bucket, prefix=f"{file_id}/pages/", recursive=True)
        for obj in objects:
            minio_client.remove_object(bucket, obj.object_name)
            print(f"已清理: {bucket}/{obj.object_name}")
    except Exception as e:
        print(f"清理 MinIO 文件失败: {e}")


def handle_chunk_upload(chunk_file, chunk_index, total_chunks, upload_id, file_name, parent_id=None):
    """
    处理分块上传

    Args:
        chunk_file: 上传的文件分块
        chunk_index: 分块索引
        total_chunks: 总分块数
        upload_id: 上传ID
        file_name: 文件名
        parent_id: 父目录ID

    Returns:
        dict: 上传结果
    """
    try:
        # 创建临时目录存储分块
        upload_dir = Path(UPLOAD_TEMP_DIR) / "chunks" / upload_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        # 保存分块
        chunk_path = upload_dir / f"{chunk_index}.chunk"
        chunk_file.save(str(chunk_path))

        # 使用Redis记录上传状态
        r = get_redis_connection()

        # 记录文件信息
        if int(chunk_index) == 0:
            r.hmset(f"upload:{upload_id}:info", {"file_name": file_name, "total_chunks": total_chunks, "parent_id": parent_id or "", "status": "uploading"})
            r.expire(f"upload:{upload_id}:info", CHUNK_EXPIRY_SECONDS)

        # 记录分块状态
        r.setbit(f"upload:{upload_id}:chunks", int(chunk_index), 1)
        r.expire(f"upload:{upload_id}:chunks", CHUNK_EXPIRY_SECONDS)

        # 检查是否所有分块都已上传
        is_complete = True
        for i in range(int(total_chunks)):
            if not r.getbit(f"upload:{upload_id}:chunks", i):
                is_complete = False
                break

        return {"code": 0, "data": {"upload_id": upload_id, "chunk_index": chunk_index, "is_complete": is_complete}, "message": "分块上传成功"}
    except Exception as e:
        print(f"分块上传失败: {str(e)}")
        return {"code": 500, "message": f"分块上传失败: {str(e)}"}


def merge_chunks(upload_id, file_name, total_chunks, parent_id=None):
    """
    合并文件分块

    Args:
        upload_id: 上传ID
        file_name: 文件名
        total_chunks: 总分块数
        parent_id: 父目录ID

    Returns:
        dict: 合并结果
    """
    try:
        r = get_redis_connection()

        # 检查上传状态
        if not r.exists(f"upload:{upload_id}:info"):
            return {"code": 404, "message": "上传任务不存在或已过期"}

        # 检查所有分块是否都已上传
        for i in range(int(total_chunks)):
            if not r.getbit(f"upload:{upload_id}:chunks", i):
                return {"code": 400, "message": f"分块 {i} 未上传，无法合并"}

        # 获取上传信息
        upload_info = r.hgetall(f"upload:{upload_id}:info")
        if not upload_info:
            return {"code": 404, "message": "上传信息不存在"}

        # 将字节字符串转换为普通字符串
        upload_info = {k.decode("utf-8"): v.decode("utf-8") for k, v in upload_info.items()}

        # 使用存储的信息，如果参数中没有提供
        file_name = file_name or upload_info.get("file_name")

        # 创建临时文件用于合并
        upload_dir = Path(UPLOAD_TEMP_DIR) / "chunks" / upload_id
        merged_path = Path(UPLOAD_TEMP_DIR) / f"merged_{upload_id}_{file_name}"

        # 合并文件
        with open(merged_path, "wb") as merged_file:
            for i in range(int(total_chunks)):
                chunk_path = upload_dir / f"{i}.chunk"
                with open(chunk_path, "rb") as chunk_file:
                    merged_file.write(chunk_file.read())

        # 使用上传函数处理合并后的文件
        with open(merged_path, "rb") as file_obj:
            # 创建FileStorage对象
            class MockFileStorage:
                def __init__(self, file_obj, filename):
                    self.file = file_obj
                    self.filename = filename

                def save(self, dst):
                    with open(dst, "wb") as f:
                        f.write(self.file.read())
                        self.file.seek(0)  # 重置文件指针

            mock_file = MockFileStorage(file_obj, file_name)
            result = upload_files_to_server([mock_file])

        # 更新状态为已完成
        r.hset(f"upload:{upload_id}:info", "status", "completed")

        # 清理临时文件
        try:
            if os.path.exists(merged_path):
                os.remove(merged_path)
            if upload_dir.exists():
                shutil.rmtree(upload_dir)
        except Exception as e:
            print(f"清理临时文件失败: {str(e)}")

        return result
    except Exception as e:
        print(f"合并分块失败: {str(e)}")
        return {"code": 500, "message": f"合并分块失败: {str(e)}"}



def get_file_pages_list(file_id):
    """
    获取文件的页面列表

    Args:
        file_id: 文件ID

    Returns:
        list: 页面列表
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, page_number, location, size, width, height, format
            FROM file_page
            WHERE file_id = %s
            ORDER BY page_number ASC
        """, (file_id,))

        pages = cursor.fetchall()
        cursor.close()
        conn.close()

        return pages
    except Exception as e:
        raise e


def get_file_preview_url(file_id):
    """
    获取文件预览URL

    Args:
        file_id: 文件ID

    Returns:
        str: 预览URL
    """
    try:
        # 获取当前登录用户ID
        from auth import get_current_user
        current_user = get_current_user()
        if not current_user:
            raise Exception("获取当前用户信息失败")

        user_id = current_user['user_id']

        # 连接数据库
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 查询文件信息，添加租户过滤
        cursor.execute(
            """
            SELECT id, parent_id, name, location, type
            FROM file
            WHERE id = %s AND tenant_id = %s
        """,
            (file_id, user_id),
        )

        file = cursor.fetchone()
        cursor.close()
        conn.close()

        if not file:
            raise Exception(f"文件 {file_id} 不存在或无权访问")

        # 获取MinIO配置
        # 注意：预览URL是返回给浏览器（客户端）访问的，必须用 MINIO_VISIT_HOST（对外访问地址），
        # 不能用 MINIO_HOST（服务器内部连接 MinIO 的地址，默认 localhost）。
        minio_host = os.getenv("MINIO_VISIT_HOST", "localhost")
        minio_port = os.getenv("MINIO_PORT", "9000")

        # 构造预览URL：http://{host}:{port}/{bucket}/{location}
        preview_url = f"http://{minio_host}:{minio_port}/{file['parent_id']}/{file['location']}"

        return preview_url

    except Exception as e:
        raise e


def download_page_image(file_id, page_number):
    """
    下载特定页面的图片
    
    Args:
        file_id: 文件ID
        page_number: 页码
    
    Returns:
        tuple: (图片数据, 文件名)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 查询页面信息
        cursor.execute("""
            SELECT fp.location, fp.format, f.parent_id, f.name
            FROM file_page fp
            JOIN file f ON fp.file_id = f.id
            WHERE fp.file_id = %s AND fp.page_number = %s
        """, (file_id, page_number))
        
        page = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not page:
            raise Exception(f"页面不存在: file_id={file_id}, page_number={page_number}")
        
        # 从 MinIO 下载图片
        minio_client = get_minio_client()
        response = minio_client.get_object(page["parent_id"], page["location"])
        image_data = response.read()
        
        # 生成文件名
        filename = f"{page['name']}_page_{page_number}.{page['format'].lower()}"
        
        return image_data, filename
    except Exception as e:
        raise e
