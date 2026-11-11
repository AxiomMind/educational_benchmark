# 整理与维护记录

## 2026-11-11 仓库整理

整理基于提交 `21e6f0f8300ffa98381828523a488f9589064c7a`。旧文件仍可通过 Git 历史查看，未重写历史。

- 统一题库路径为 `datasets/history/`，不再用题目数量命名目录。
- 删除与当前数据完全重叠的 20 题和 400 题旧批次。
- 删除 95 个未被保留题目引用的原始文件、80 个未引用图片；保留 261 个原始文件和 365 个图片。
- 删除旧批次构建脚本、固定用户名的桌面交付脚本、旧年份回填脚本、重复答案爬取脚本、旧登录辅助脚本、自动提交循环和空占位模块。
- 来源配置统一到 `config/source_registry.yaml`；移除未被程序读取的 pipeline.yaml。
- 审核 CSV 按需生成到本地工作目录，不再跟踪重复快照。
- 答案脚本改为可传路径的入口；OCR 冲突不自动决策，回填仅补缺并核对原图哈希。
- 根 README 和操作文档改为中文。

## 确认移除的重复题

| 保留题号 | 移除题号 | 依据 |
|---|---|---|
| CHIS_000067 | CHIS_002765 | 题干与选项一致，分值前缀和格式不同 |
| CHIS_000266 | CHIS_003000 | 步辇图题，材料及选项一致，图片裁切不同 |
| CHIS_002163 | CHIS_003717 | 同一表格题，设问位置不同 |
| CHIS_000953 | CHIS_002269 | 折线图数据一致，A/B 换序，正确选项内容相同 |
| CHIS_001471 | CHIS_003856 | 同一材料题，个别字词、断行和选项顺序不同 |

保留题的来源记录已经合并。没有因为转载平台增加而将答案自动升级为 verified。配图不同的 CHIS_000273 / CHIS_002769 作为变体保留在同一题组。

CHIS_003497 / CHIS_003725 同步了表格题拆分后的题干字段，重新计算哈希。两条缺少漫画的题目仅标记问题，没有补造图像或答案。

机器可读清单在 [cleanup.json](../datasets/history/reports/cleanup.json)，包括删除文件的原路径、大小和 SHA-256。

## 后续更新步骤

1. 从当前题库生成候选文件，保留稳定题号、原始来源与修改记录。
2. 查重时先比较题干、正确选项内容和图像，不能直接按答案字母合并。
3. 将新来源原件和图片放到数据集对应目录，更新原始文件清单。
4. 校验候选文件，再由同一份候选结果生成报告。
5. 检查差异后更新正式文件，并运行完整性检查与单元测试。

```bash
python -m chis_eval validate --input data/cleaned/candidate.jsonl --output data/cleaned/candidate.validated.jsonl
python -m chis_eval report --input data/cleaned/candidate.validated.jsonl --output data/reports/candidate.json
python scripts/check_dataset.py
python -m pytest -q
```

检测近重复可以使用 CLI 的 `deduplicate` 命令。它输出候选报告，不会自动删除近重复题；当前实现逐对比较，全量数据运行可能较慢。

原始文件不必永久全部放在主分支，但删除前必须核对题目与答案证据引用，并同步 manifests。不要为了凑整数题量删除有效题目或补造标签。
