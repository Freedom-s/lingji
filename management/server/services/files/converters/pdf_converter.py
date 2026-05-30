"""
PDF 转换器

将各种格式文档转换为 PDF
"""

import os
import requests
from typing import Dict, Optional
import tempfile

DEFAULT_MD_TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>My PDF</title>
  </head>
  <body>
    {{ toHTML "%(md_name)s" }}
  </body>
</html>
"""

# 支持的文件类型
LIBREOFFICE_EXTS = {"doc", "docx", "ppt", "pptx", "xls", "xlsx", "txt", "csv"}
HTML_EXTS = {"html"}
MARKDOWN_EXTS = {"md"}
PDF_EXTS = {"pdf"}


class GotenbergConvertError(RuntimeError):
    """Gotenberg 文档转换异常"""
    pass


def convert_file(file_path: str, gotenberg_url: str = "http://localhost:3000") -> bytes:
    """
    统一入口：根据文件扩展名调用对应的转换函数
    
    :param file_path: 待转换文件路径
    :param gotenberg_url: Gotenberg 服务地址
    :return: PDF 文件二进制内容
    :raises ValueError: 不支持的文件类型
    :raises GotenbergConvertError: 转换失败

    这个最终返回的是pdf文件的字节流
    """
    ext = file_path.rsplit(".", 1)[-1].lower()
    
    if ext in LIBREOFFICE_EXTS:
        return convert_office_to_pdf(file_path, gotenberg_url=gotenberg_url)
    elif ext in HTML_EXTS:
        return convert_html_to_pdf(file_path, gotenberg_url=gotenberg_url)
    elif ext in MARKDOWN_EXTS:
        return convert_markdown_to_pdf(file_path, gotenberg_url=gotenberg_url)
    elif ext in PDF_EXTS:
        with open(file_path, "rb") as f:
            return f.read()
    else:
        raise ValueError(f"不支持的文件类型: {ext}")


def convert_office_to_pdf(
    input_file_path: str,
    *,
    gotenberg_url: str = "http://localhost:3000",
    timeout: int = 60,
    libreoffice_options: Optional[Dict[str, str]] = None,
) -> bytes:
    """
    使用 Gotenberg (LibreOffice) 将文档转换为 PDF

    :param input_file_path: 待转换文件路径（docx / xlsx / pptx 等）
    :param gotenberg_url: Gotenberg 服务地址，如 http://localhost:3000
    :param timeout: 请求超时时间（秒）
    :param libreoffice_options: LibreOffice 转换参数（必须是字符串）
    :return: PDF 文件二进制内容
    :raises FileNotFoundError: 输入文件不存在
    :raises GotenbergConvertError: 转换失败
    """

    if not os.path.isfile(input_file_path):
        raise FileNotFoundError(f"文件不存在: {input_file_path}")

    url = gotenberg_url.rstrip("/") + "/forms/libreoffice/convert"

    options = libreoffice_options or {}
    options = {k: str(v) for k, v in options.items()}

    try:
        with open(input_file_path, "rb") as f:
            files = {
                "files": (
                    os.path.basename(input_file_path),
                    f,
                    "application/octet-stream"
                )
            }

            response = requests.post(
                url,
                files=files,
                data=options,
                timeout=timeout,
            )

    except requests.RequestException as e:
        raise GotenbergConvertError(f"Gotenberg 请求失败: {e}") from e

    if response.status_code != 200:
        raise GotenbergConvertError(
            f"Gotenberg 转换失败 "
            f"(status={response.status_code}): {response.text}"
        )

    content_type = response.headers.get("Content-Type", "")
    if "application/pdf" not in content_type:
        raise GotenbergConvertError(
            f"返回内容不是 PDF，Content-Type={content_type}"
        )

    return response.content


def convert_html_to_pdf(
    html_file_path: str,
    *,
    gotenberg_url: str = "http://localhost:3000",
    timeout: int = 60,
    chromium_options: Optional[Dict[str, str]] = None,
) -> bytes:
    """
    使用 Gotenberg Chromium 将 HTML 转换为 PDF
    """

    if not os.path.isfile(html_file_path):
        raise FileNotFoundError(f"文件不存在: {html_file_path}")

    url = gotenberg_url.rstrip("/") + "/forms/chromium/convert/html"

    options = chromium_options or {}
    options = {k: str(v) for k, v in options.items()}

    try:
        with open(html_file_path, "rb") as f:
            files = {
                "files": (
                    os.path.basename(html_file_path),
                    f,
                    "text/html"
                )
            }

            response = requests.post(
                url,
                files=files,
                data=options,
                timeout=timeout,
            )

    except requests.RequestException as e:
        raise GotenbergConvertError(f"Gotenberg HTML 转换失败: {e}") from e

    if response.status_code != 200:
        raise GotenbergConvertError(
            f"HTML 转 PDF 失败 "
            f"(status={response.status_code}): {response.text}"
        )

    if "application/pdf" not in response.headers.get("Content-Type", ""):
        raise GotenbergConvertError("返回结果不是 PDF")

    return response.content


def convert_markdown_to_pdf(
    md_path: str, 
    *, 
    gotenberg_url: str = "http://localhost:3000", 
    timeout: int = 60
) -> bytes:
    """
    使用 Gotenberg 将 Markdown 转换为 PDF
    """
    if not os.path.isfile(md_path):
        raise FileNotFoundError(f"Markdown 文件不存在: {md_path}")
    
    url = f"{gotenberg_url.rstrip('/')}/forms/chromium/convert/markdown"

    md_name = os.path.basename(md_path)
    with tempfile.TemporaryDirectory() as tmp:
        html_path = os.path.join(tmp, "index.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(DEFAULT_MD_TEMPLATE % {"md_name": md_name})
        try:
            with open(html_path, "rb") as html_file, open(md_path, "rb") as md_file:
                files = [
                    ("files", (os.path.basename(html_path), html_file, "text/html")),
                    ("files", (md_name, md_file, "text/markdown")),
                ]
                response = requests.post(url, files=files, timeout=timeout)
        except Exception as e:
            raise GotenbergConvertError(f"Gotenberg Markdown 转换失败: {e}") from e

        if response.status_code != 200:
            raise GotenbergConvertError(
                f"Markdown 转 PDF 失败 "
                f"(status={response.status_code}): {response.text}"
            )

        if "application/pdf" not in response.headers.get("Content-Type", ""):
            raise GotenbergConvertError("返回结果不是 PDF")

        return response.content
