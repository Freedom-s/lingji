# lingji-root 校园网联网流程

适用于无图形界面的 Ubuntu 宿主机 `lingji-root`（`10.15.25.201`）。宿主机通过校园网认证后，外网出口使用 `eno1`，地址通常为 `10.15.25.202`。

## 1. 确认宿主机能访问认证服务器

```bash
ssh lingji-root "ip route get 10.100.90.249"
```

应看到流量从 `eno1` 发出，源地址为 `10.15.25.202`。

## 2. 建立临时认证页面通道

SSH 服务端已对 `root` 用户单独允许 TCP 转发。建立本机 IPv4 端口转发：

```bash
ssh -N -L 127.0.0.1:8081:10.100.90.249:80 lingji-root
```

保持该终端运行，然后在本机浏览器打开：

```text
http://127.0.0.1:8081/srun_portal_pc?ac_id=1&theme=pro
```

使用校园网账号登录。必须使用 `127.0.0.1`，不要使用 `localhost`，否则部分系统会解析到 IPv6，导致认证请求连接失败。

认证完成后关闭端口转发终端即可，校园网登录状态仍保留在宿主机上。

## 3. 配置 DNS

如果宿主机能 ping 通网关，但域名解析失败，给实际出站连接 `eno1` 配置 DNS：

```bash
ssh lingji-root
nmcli connection modify eno1 \
  ipv4.ignore-auto-dns yes \
  ipv4.dns "223.5.5.5 8.8.8.8"
nmcli device reapply eno1
```

## 4. 验证外网

```bash
ssh lingji-root "getent hosts www.baidu.com"
ssh lingji-root "curl -I -L --max-time 15 https://www.baidu.com"
```

## 注意事项

- 宿主机有两个同网段网卡 `eno1` 和 `eno2`，当前默认外网出口是 `eno1`。
- 校园认证绑定的是实际出站地址 `10.15.25.202`，不是 SSH 使用的 `10.15.25.201`。
- 不要把校园网账号和密码写入脚本、配置文件或 Docker 镜像。
- 如果认证过期，重复第 2 步即可。
