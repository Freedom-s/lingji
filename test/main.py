from convert_file_2_pdf import convert_html_to_pdf,convert_markdown_to_pdf,convert_office_to_pdf
import os
from typing import Optional


LIBREOFFICE_EXTS = {"doc", "docx", "ppt", "pptx", "xls", "xlsx", "txt", "csv"}
PNG_EXTS = {"jpg", "jpeg", "png", "bmp"}
HTML_EXTS = {"html"}
MARKDOWN_EXTS = {"md"}
PDF_EXTS = {"pdf"}

def convert_file(file_path: str) -> bytes:
    """
    调用对应的函数，然后返回字节流
    """

    ext = file_path.rsplit(".", 1)[-1].lower()
    if ext in LIBREOFFICE_EXTS:
        return convert_office_to_pdf(file_path)
    elif ext in HTML_EXTS:
        return convert_html_to_pdf(file_path)
    elif ext in MARKDOWN_EXTS:
        return convert_markdown_to_pdf(file_path)
    elif ext in PDF_EXTS:
        with open(file_path, "rb") as f:
            return f.read()
    else:
        raise ValueError(f"不支持的文件类型: {ext}")
    
def convert_folder(input_dir: str, output_dir: Optional[str] = None):
    input_dir = os.path.abspath(input_dir)
    output_dir = os.path.abspath(output_dir or input_dir)
    os.makedirs(output_dir, exist_ok=True)

    for filename in os.listdir(input_dir):
        src_path = os.path.join(input_dir, filename)
        if not os.path.isfile(src_path):
            continue

        name, _ = os.path.splitext(filename)
        pdf_path = os.path.join(output_dir, name + ".pdf")

        try:
            print(f"[INFO] 转换: {filename}")
            pdf_bytes = convert_file(src_path)
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
            print(f"[OK] 生成: {pdf_path}")
        except Exception as e:
            print(f"[FAIL] {filename}: {e}")

if __name__ == "__main__":
    convert_folder("./files", "./pdf_output")