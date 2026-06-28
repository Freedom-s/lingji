"""
测试 Gotenberg 能否将本地文件转为 PDF

用法:
    python test/test_gotenberg_convert.py <文件路径>

示例:
    python test/test_gotenberg_convert.py ~/Desktop/CH1.pptx
    python test/test_gotenberg_convert.py ~/Desktop/*.pptx
"""
import os
import sys
import requests

GOTENBERG_URLS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:3003",
]


def test_gotenberg(filepath: str) -> bool:
    """返回 True 表示转化成功"""
    filename = os.path.basename(filepath)
    size_mb = os.path.getsize(filepath) / 1024 / 1024

    print(f"\n{'='*60}")
    print(f"文件: {filename}")
    print(f"大小: {size_mb:.2f} MB")
    print(f"{'='*60}")

    for i, url in enumerate(GOTENBERG_URLS):
        instance = f"gotenberg-{i+1} ({url})"
        print(f"\n[{instance}] 尝试转化...", end=" ", flush=True)

        try:
            with open(filepath, "rb") as f:
                resp = requests.post(
                    f"{url}/forms/libreoffice/convert",
                    files={"files": (filename, f, "application/octet-stream")},
                    timeout=120,
                )

            status = resp.status_code
            content_type = resp.headers.get("Content-Type", "")

            if status == 200 and "application/pdf" in content_type:
                pdf_size = len(resp.content) / 1024
                # 存到输入文件同目录，同名加 .pdf
                out_path = os.path.splitext(filepath)[0] + ".pdf"
                with open(out_path, "wb") as out:
                    out.write(resp.content)
                print(f"✅ 成功! PDF 大小: {pdf_size:.0f} KB → {out_path}")
                return True
            elif status == 503:
                print(f"⏳ 503 (容器繁忙)")
            else:
                # 打印错误详情
                err = resp.text[:300] if resp.text else "(空)"
                print(f"❌ 失败! HTTP {status}: {err}")

        except requests.exceptions.ConnectionError:
            print(f"❌ 连接失败! 容器可能没启动")
        except requests.exceptions.Timeout:
            print(f"❌ 超时 (120s)")

    print(f"\n所有 4 个 Gotenberg 实例均转化失败")
    return False


def main():
    if len(sys.argv) < 2:
        print("用法: python test_gotenberg_convert.py <文件路径> [文件路径...]")
        sys.exit(1)

    paths = []
    for arg in sys.argv[1:]:
        if os.path.isfile(arg):
            paths.append(arg)
        else:
            print(f"⚠️  跳过（不存在）: {arg}")

    if not paths:
        print("没有找到可测试的文件")
        sys.exit(1)

    results = {}
    for p in paths:
        results[p] = test_gotenberg(p)

    print(f"\n{'='*60}")
    print("汇总:")
    for p, ok in results.items():
        status = "✅ 成功" if ok else "❌ 失败"
        print(f"  {status}  {os.path.basename(p)}")

    success = sum(1 for v in results.values() if v)
    print(f"\n{success}/{len(results)} 个文件转化成功")


if __name__ == "__main__":
    main()
