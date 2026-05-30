# 灵机AI助学平台 - 部署指南

## 快速部署

### 方法一：使用部署脚本（推荐）

```bash
./deploy.sh
```

该脚本会自动完成以下步骤：
1. 打包项目生成 dist 文件
2. 删除容器中的旧文件
3. 将新文件拷贝到容器

### 方法二：手动部署

#### 1. 打包项目

```bash
pnpm run build
```

#### 2. 删除容器中的旧文件

```bash
docker exec -it ragflowplus-management-frontend /bin/sh -c "rm -rf /usr/share/nginx/html"
```

#### 3. 拷贝新文件到容器

```bash
docker cp dist ragflowplus-management-frontend:/usr/share/nginx/html
```

## 自定义配置

### 修改 Logo

Logo 文件位于 `src/common/assets/images/layouts/` 目录：

- `logo.svg` - 侧边栏折叠时显示的小图标
- `logo-text-1.svg` - 浅色主题下的完整 Logo
- `logo-text-2.svg` - 深色主题下的完整 Logo

**注意**: 如果需要使用 PNG 格式，请：
1. 将 SVG 文件转换为 PNG
2. 修改 `src/layouts/components/Logo/index.vue` 中的导入路径

### 修改标题

编辑 `.env` 文件中的 `VITE_APP_TITLE` 参数：

```env
VITE_APP_TITLE = 灵机AI助学平台
```

### 修改页脚

编辑 `src/layouts/components/Footer/index.vue` 文件。

## 开发环境

### 启动开发服务器

```bash
pnpm run dev
```

### 构建生产版本

```bash
pnpm run build
```

### 预览生产构建

```bash
pnpm run preview
```

## 故障排查

### 容器名称不匹配

如果容器名称不是 `ragflowplus-management-frontend`，请：

1. 查看实际的容器名称：
   ```bash
   docker ps
   ```

2. 修改 `deploy.sh` 脚本中的容器名称

### 权限问题

如果遇到权限问题，请确保：
- `deploy.sh` 有执行权限：`chmod +x deploy.sh`
- Docker 命令有足够的权限

### 打包失败

检查：
- Node.js 版本是否符合要求
- 依赖是否正确安装：`pnpm install`
- 是否有语法错误
