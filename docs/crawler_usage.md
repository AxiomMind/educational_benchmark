# 爬虫与答案处理

所有命令从仓库根目录运行，先安装 Python 包：`python -m pip install -e ".[dev]"`。

## 1. 采集与解析

四个适配器位于 `src/chis_eval/crawlers/adapters/`，统一由 CLI 调用。公开来源示例：

```bash
python -m chis_eval crawl --source GAOKAO_BENCH --limit 1
python -m chis_eval parse --source GAOKAO_BENCH --output data/parsed/bench.jsonl
```

来源也可替换为 `AGIEVAL_GAOKAO` 或 `GAOKAO_MM`。这些上游以一个 JSON/JSONL 文件提供多道题，因此采集 `--limit` 不是题目数限制。组卷网的该参数表示试卷数量。

共享下载器提供限速、重试、SQLite 断点记录和原始字节保存。默认写入 `data/raw/`、`data/state/`；来源开关、域名范围和采集间隔在唯一的 `config/source_registry.yaml` 中维护。

解析与采集相互独立。使用 `parse --input 原始文件` 可以处理已有本地文件。多来源解析结果不能直接拼接成发布集：必须处理全局题号、来源追溯、题组与重复题。新采集的多模态记录还需补齐图片资源；JSONL 中出现图片路径本身不表示文件已经下载。

## 2. 组卷网交互登录

登录工具是可选的，需要 Node.js：

```bash
npm ci
npx playwright install chromium
node scripts/login.js
```

脚本打开浏览器，完成登录后回到终端按回车，将会话保存到 Git 忽略的 `data/xkw_cookies.json`。脚本不输出 Cookie 内容。

使用已有会话采集：

```bash
python -m chis_eval crawl --source ZUJUAN_XKW --authenticated --limit 2
python -m chis_eval parse --source ZUJUAN_XKW --output data/parsed/zujuan.jsonl
```

来源仍须处于 approved 状态并满足配置检查。`--authenticated` 明确启用本地登录会话，不会代替账号登录，也不改变来源授权。

## 3. 下载答案原图

```bash
python scripts/fetch_answer_images.py --limit 100
```

默认读取当前题库的 `provenance.source_question_number`，把图片保存到 `data/answer_images/`，同时记录来源 URL、获取时间和 SHA-256。已存在的原图跳过。参数支持 `--input`、`--cookies`、`--images`、`--interval`。

接口返回访问验证、错误图片或频率限制时停止本轮，检查会话后再手动执行。下载成功不代表答案内容已经审核。

## 4. 离线 OCR

安装 Tesseract 和中文/英文语言包，使 `tesseract --list-langs` 能列出 `chi_sim`、`eng`：

```bash
python scripts/batch_ocr_answers.py
```

Windows 使用 WSL 中的 Tesseract 时：

```bash
python scripts/batch_ocr_answers.py --wsl
```

脚本动态转换本机路径，不含个人用户名。缓存保存 OCR 原文、图片哈希和提取到的答案声明。声明互相冲突时答案留空，不再取最后一个字母。使用 `--force` 可重新识别图片。

## 5. 回填和检查

```bash
python scripts/apply_crawled_answers.py --input data/cleaned/zujuan.jsonl --output data/cleaned/zujuan.answered.jsonl
```

仅回填缺失答案，要求对应答案原图存在且 SHA-256 与缓存一致。已有答案保留；新 OCR 结果标记待复核。输入输出必须不同。脚本对回填结果执行校验，并从同一份校验结果生成 `data/reports/answers.json`。

本地查看候选结果后，再通过人工审核决定是否更新当前题库。仓库不再保留自动循环提交和推送脚本。
