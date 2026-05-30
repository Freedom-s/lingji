#!/bin/bash

# 灵机AI助学平台 - 前端部署脚本
# 使用方法: ./deploy.sh

echo "======================================"
echo "  灵机AI助学平台 - 前端部署"
echo "======================================"
echo ""

# 1. 打包项目
echo "📦 步骤 1/3: 开始打包项目..."
pnpm run build

if [ $? -ne 0 ]; then
    echo "❌ 打包失败，请检查错误信息"
    exit 1
fi

echo "✅ 打包完成"
echo ""

# 2. 删除容器中的旧文件
echo "🗑️  步骤 2/3: 删除容器中的旧文件..."
docker exec -it ragflowplus-management-frontend /bin/sh -c "rm -rf /usr/share/nginx/html"

if [ $? -ne 0 ]; then
    echo "⚠️  删除旧文件失败，容器可能不存在或未运行"
    echo "请确认容器名称是否为: ragflowplus-management-frontend"
    exit 1
fi

echo "✅ 旧文件已删除"
echo ""

# 3. 拷贝新文件到容器
echo "📤 步骤 3/3: 拷贝新文件到容器..."
docker cp dist ragflowplus-management-frontend:/usr/share/nginx/html

if [ $? -ne 0 ]; then
    echo "❌ 拷贝文件失败"
    exit 1
fi

echo "✅ 文件拷贝完成"
echo ""

echo "======================================"
echo "  🎉 部署成功！"
echo "======================================"
echo ""
echo "提示: 请刷新浏览器查看更新"
