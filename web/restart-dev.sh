#!/bin/bash

echo "🧹 清除缓存..."
rm -rf src/.umi
rm -rf node_modules/.cache

echo "✅ 缓存已清除"
echo ""
echo "🚀 请手动重启开发服务器："
echo "   1. 按 Ctrl+C 停止当前服务器"
echo "   2. 运行: npm run dev"
echo ""
echo "🌐 然后在浏览器中："
echo "   1. 按 Ctrl+Shift+R 硬刷新"
echo "   2. 或使用无痕模式 (Ctrl+Shift+N)"
