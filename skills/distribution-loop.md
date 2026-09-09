---
name: paper-distribution-loop
description: 论文解读文章的表达检查、系列导航与多平台草稿分发
version: 3.0
---

# 论文文章传播流程

在文章完成后、发布前执行。遵循用户本地人设与渠道偏好；账号规模、阅读数据和私人合作关系不属于公共流程。

## 表达与导航

- 从论文证据出发提出清晰判断，避免夸张和无依据的结论。
- 为系列文章添加前后篇导航；仅使用已确认公开的文章链接，不包含后台或草稿链接中的登录参数。
- 微信正文不能依赖 Markdown 渲染，发布前检查转换后的排版、公式和图片。
- 私人转发渠道及合作联系人从本地人设文件读取；外部发送需用户明确授权。

## 平台适配与分发

使用 wechatsync CLI 和浏览器扩展完成平台认证。凭据保存在本地配置或环境变量中，禁止把 Cookie、Token、登录态导出到公共仓库。

```bash
# 检查 CLI 与扩展状态
python -m pipeline.run distribute-login
# 生成并审阅各平台版本
python -m pipeline.run distribute-adapt data/articles/article.json
# 演练
python -m pipeline.run distribute-publish data/articles/article.json --dry-run
# 用户明确要求后，分发到所选平台草稿箱
python -m pipeline.run distribute-publish data/articles/article.json --platforms zhihu,juejin,csdn,weixin
```

逐个平台确认分发结果，失败时检查登录态及返回错误；不要未经核实重试已成功的平台。草稿创建与最终公开发布应分别确认。

## 数据反馈

运行 `profile`、`strategy` 查看采集结果；策略和原始数据保留在 `data/`。提交公共示例时使用虚构数据，并移除账号标识、内部链接、个人联系方式和任务 ID。
