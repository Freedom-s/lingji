# 得到流对象（此时数据还在网络管道里，没进内存）
minio_response = minio_client.get_object(bucket, object)

try:
    # requests 会自动调用 minio_response.read(chunk_size)
    # 像挤牙膏一样，一点点读，一点点发
    # 这里可以直接进行传输
    requests.post(url, files={"file": ("filename.jpg", minio_response, "image/jpeg")})
finally:
    minio_response.close()
    minio_response.release_conn()