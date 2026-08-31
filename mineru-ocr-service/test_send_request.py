import requests
# 直接写一个脚本，然后一次去处理每张图片，把结果全部存储到一个list里面
data = {
    "file_path": '/Users/suojianhua/PyProjects/ragflow-plus-version2/mineru-ocr-service/imgs/docvqa2.jpg',
    "parse_method": "auto",
    "is_json_md_dump": True,
    "return_layout": True,
    "return_info": True,
    "return_content_list": True,
    "return_images": True
}
url = "http://localhost:8888/file_parse"
response = requests.post(url, data, timeout=800)

response.raise_for_status()


if response.status_code != 200:
    print(f"请求mineru服务出错了，错误原因:{response.text}，错误状态码:{response.status_code}")

result = response.json()
print('result', result)
text = ''
if 'content_list' in result:
    for item in result['content_list']:
        # 提取图片标题（如果有）
        if item.get('type') == 'image' and 'img_caption' in item:
            # 只有当img_caption不为空时才添加
            if item['img_caption']: 
                cap_content = '\n'.join(item['img_caption'])
                text += cap_content + '\n'
            continue
        
        # 提取正文文本
        if 'text' in item and item['text']:
            text += item['text'] + '\n'
print("*"*50)
print("*"*50)
print(text)
# md_content = result.get("md_content")
# print('md_content', md_content)
    