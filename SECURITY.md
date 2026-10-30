# Security / 安全说明

此项目用于本地毕业设计演示和研究。目前 API 没有登录认证或细粒度权限控制，部分接口可以修改配置、访问日志及执行训练任务。请将后端绑定到 `127.0.0.1`，不要直接暴露到公网。正式部署前应增加身份认证、访问控制、任务隔离及网关限制。

凭据放在根目录 `.env` 中；已有系统配置页面保存到数据库的值不会自动覆盖进程环境变量。不要把真实令牌写入 SQL、截图、Issue 或日志。如果令牌曾被分享或提交，请在服务商处撤销并重新生成。

如发现漏洞，请使用仓库 **Security → Report a vulnerability**（若维护者已开启）；否则先提交不含漏洞细节的 Issue，请维护者提供私密联系渠道。不要公开可利用细节或真实密钥。

This is a local research and graduation demo. APIs currently have no authentication or granular authorization and can modify configuration, read logs and start jobs. Bind the backend to loopback. Add authentication, authorization, job isolation and gateway controls before any public deployment.

Store secrets in the root `.env`; database configuration records do not automatically override environment settings. Revoke any previously shared credentials. Report vulnerabilities through GitHub private vulnerability reporting when enabled, or request a private contact without publishing exploit details.
