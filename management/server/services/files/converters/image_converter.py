"""
图片转换器

将 PDF 转换为图片
"""

import fitz  # PyMuPDF
from typing import List, Tuple


def pdf_to_images(
    pdf_bytes: bytes,
    dpi: int = 150,
    image_format: str = "JPEG",
    quality: int = 85
) -> List[Tuple[bytes, int, int]]:
    """
    将 PDF 转换为图片列表
    
    Args:
        pdf_bytes: PDF 文件字节流
        dpi: 图片分辨率（默认 150）
            - 72: 低质量（文件小）
            - 150: 标准质量（推荐）
            - 300: 高质量（文件大）
        image_format: 图片格式（JPEG/PNG）
        quality: JPEG 质量（1-100，默认 85）
    
    Returns:
        List[Tuple[bytes, width, height]]: 每页的(图片字节, 宽度, 高度)
    
    Raises:
        Exception: PDF 处理失败
    """
    images = []
    
    try:
        # 从字节流打开 PDF
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            
            # 设置缩放比例（DPI 转换）
            # PDF 默认 72 DPI，zoom = target_dpi / 72
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            
            # 渲染页面为图片
            pix = page.get_pixmap(matrix=mat)
            
            # 转换为字节流
            img_bytes = pix.tobytes(output=image_format.lower())
            
            images.append((img_bytes, pix.width, pix.height))
        
        pdf_document.close()
        
    except Exception as e:
        raise Exception(f"PDF 转图片失败: {str(e)}") from e
    
    return images
