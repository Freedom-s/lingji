import requests
import os

# 1. 准备你要上传的本地图片路径（仅仅是为了读取它，不是传路径给服务端）
local_image_path = '/Users/suojianhua/PyProjects/qwen3-vl-embd/mineru-ocr-service/123.jpg'
file_name = os.path.basename(local_image_path)


url = "http://localhost:8888/file_parse"

try:
    # 3. 打开文件并构建 files 字典
    # 关键点：
    #   - 字典的 key "file" 必须对应 FastAPI 函数参数名 `file: UploadFile`
    #   - 字典的 value 是一个元组: (文件名, 文件对象, MIME类型)
    with open(local_image_path, 'rb') as f:
        files_payload = {
            "file": (file_name, f, "image/jpeg")
        }

        # 4. 发送请求
        # 使用 files 参数时，requests 会自动将 Content-Type 设为 multipart/form-data
        response = requests.post(
            url, 
            files=files_payload, 
            timeout=60
        )

    # 5. 检查结果
    response.raise_for_status()

    if response.status_code != 200:
        print(f"出错: {response.text}")
        exit()

    result = response.json()
    print('@@@',result)

except Exception as e:
    print(f"请求发生异常: {e}")