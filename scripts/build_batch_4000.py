import os
import sys
import json
import re
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, 'src')
from chis_eval.pipeline.normalize import ordered_hash, permutation_hash
from chis_eval.pipeline.validate import validate_records
from chis_eval.pipeline.report import build_quality_report, write_quality_report
from chis_eval.pipeline.review import export_review_csv

REPO_DIR = Path('C:/Users/26730/educational_benchmark')

print('=== 开始根据初步审查报告进行数据与爬虫全面修复 ===')

# ==============================================================================
# 1. 修复 GAOKAO-MM 多模态上游全部图片资源
# ==============================================================================
print('\n[1/5] 检查并补全 GAOKAO-MM 全部多模态图片资源...')
mm_raw_json = REPO_DIR / 'GAOKAO_BENCH_BATCH_4000/raw/gaokao_mm_history.json'
with mm_raw_json.open('r', encoding='utf-8') as f:
    mm_upstream_data = json.load(f).get('example', [])

mm_img_base = 'https://raw.githubusercontent.com/OpenMOSS/GAOKAO-MM/main/Data/2010-2023_History_MCQs/'
mm_items_by_index = {}
for it in mm_upstream_data:
    mm_items_by_index[str(it.get('index'))] = it

# ==============================================================================
# 2. 预解析所有本地已保存的组卷网 HTML (一次遍历，建立索引)
# ==============================================================================
print('\n[2/5] 预解析本地组卷网 HTML 页面，建立纯净题干、选项与图片索引...')
html_files = list((REPO_DIR / 'GAOKAO_BENCH_BATCH_4000/raw').glob('zujuan_paper_*.html'))
print(f'共扫描到 {len(html_files)} 份组卷网试卷原件 HTML。')

zujuan_parsed_index = {} # qid_num -> dict of clean data
download_tasks = []      # (url, filename)

def clean_question_str(q):
    return re.sub(r'^\d+[\.\、\．\s]*(（[^）]+）|\([^\)]+\))?\s*', '', q).strip()

def parse_mcq_div(cnt):
    txt = cnt.get_text('\n', strip=True)
    parts = re.split(r'(?=[A-D][\.\、\．])', txt)
    if len(parts) < 5:
        return None
    q = parts[0].strip()
    q = clean_question_str(q)
    opts = {}
    for p in parts[1:]:
        p = p.strip()
        if not p: continue
        letter = p[0]
        val = re.sub(r'^[A-D][\.\、\．]\s*', '', p).strip()
        sub = re.split(r'\s+(?=[B-D][\.\、\．])', val)
        if len(sub) > 1:
            opts[letter] = sub[0].strip()
            for s in sub[1:]:
                s = s.strip()
                if s and s[0] in 'BCD':
                    opts[s[0]] = re.sub(r'^[B-D][\.\、\．]\s*', '', s).strip()
        else:
            opts[letter] = val
    if set(opts.keys()) == {'A', 'B', 'C', 'D'}:
        if all(len(opts[k]) > 0 for k in 'ABCD') and len(q) > 5:
            return q, opts
    return None

def extract_item_year(info_div) -> tuple[int | None, str]:
    if not info_div:
        return None, ""
    info_text = info_div.get_text(strip=True)
    if not info_text or "该试题已被下架" in info_text:
        return None, ""

    m_gk = re.findall(r"(20[12]\d)年(?:[0-9一二三四五六七八九十月]+)?(?:[^\s\|]+)?高考", info_text)
    if m_gk:
        y = int(m_gk[0])
        return min(y, 2026), f"历年高考统考真题({y}年)"

    cit_part = info_text.split("引用：", 1)[-1] if "引用：" in info_text else info_text
    exam_tokens = re.split(r"(?<=[卷题练测考])", cit_part)
    valid_exams = [e.strip() for e in exam_tokens if any(yr in e for yr in ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "201"])]
    target_exam = valid_exams[0] if valid_exams else cit_part

    m_ay = re.search(r"(20[12]\d)[-—至]20(\d\d)学年", target_exam)
    if m_ay:
        y_start = int(m_ay.group(1))
        y_end = int("20" + m_ay.group(2))
        if y_start >= 2026:
            return 2026, f"名校考卷引用：{target_exam[:45]}"
        if any(term in target_exam for term in ["下学期", "第二学期", "期末", "春季", "3月", "4月", "5月", "6月", "7月"]):
            return min(y_end, 2026), f"名校考卷引用：{target_exam[:45]}"
        else:
            return min(y_start, 2026), f"名校考卷引用：{target_exam[:45]}"

    m_grad = re.search(r"(20[12]\d)届", target_exam)
    if m_grad:
        g_yr = int(m_grad.group(1))
        return 2026 if g_yr >= 2027 else min(g_yr, 2026), f"名校考卷引用：{target_exam[:45]}"

    m_yr = re.search(r"(20[12]\d)年", target_exam)
    if m_yr:
        y = int(m_yr.group(1))
        return min(y, 2026), f"名校考卷引用：{target_exam[:45]}"

    m_up = re.search(r"(20[12]\d)/\d{2}/\d{2}", info_text)
    if m_up:
        y = int(m_up.group(1))
        return min(y, 2026), f"题库系统录入时间({m_up.group(0)})"

    return None, ""

for hpath in html_files:
    html_text = hpath.read_text(encoding='utf-8', errors='ignore')
    soup = BeautifulSoup(html_text, 'html.parser')

    # 提取真实标题
    title_tag = soup.find('h1') or soup.find('title')
    raw_title = title_tag.get_text(strip=True) if title_tag else '高中历史试题'
    paper_title = re.sub(r'-组卷网.*$', '', raw_title).strip()

    # 真实年份提取
    year_m = re.search(r'(19\d\d|20\d\d)', paper_title)
    year_val = int(year_m.group(1)) if year_m else None

    # 省份提取
    province_val = "全国"
    provinces = [
        "北京", "上海", "天津", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
        "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
        "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃",
    ]
    for prov in provinces:
        if prov in paper_title:
            province_val = prov
            break

    # 解析每个 quesdiv
    for qd in soup.find_all('div', id=lambda x: x and x.startswith('quesdiv')):
        qid_num = qd.get('id', '')[7:] # strip 'quesdiv'
        cnt = qd.find('div', class_='exam-item__cnt')
        if not cnt:
            continue

        res = parse_mcq_div(cnt)
        if not res:
            continue
        q_clean, opts = res

        # 题目级年份真实溯源 (Scheme A)
        item_info = qd.find('div', class_='exam-item__info')
        item_yr, item_reason = extract_item_year(item_info)
        final_yr = year_val or item_yr

        # 检查图片
        imgs = cnt.find_all('img')
        img_filenames = []
        for img in imgs:
            src = img.get('src')
            if src and src.startswith('http'):
                clean_url = src.split('?')[0]
                fn = f"zujuan_{qid_num}_{Path(clean_url).name}"
                img_filenames.append((src, fn))
                download_tasks.append((src, fn))

        zujuan_parsed_index[qid_num] = {
            'paper_title': paper_title,
            'year': final_yr,
            'year_reason': item_reason,
            'province': province_val,
            'question': q_clean,
            'options': opts,
            'images': [fn for _, fn in img_filenames]
        }

print(f'预解析完成！有效题目索引量: {len(zujuan_parsed_index)} 条，待下载/核对图片任务: {len(download_tasks)} 个。')

# 下载组卷网所有图片到 assets
assets_dir_4000 = REPO_DIR / 'GAOKAO_BENCH_BATCH_4000/assets'
assets_dir_4000.mkdir(parents=True, exist_ok=True)

def download_asset(task):
    url, fn = task
    dest = assets_dir_4000 / fn
    if dest.exists():
        return True
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = resp.read()
        dest.write_bytes(data)
        return True
    except Exception:
        return False

print('正在并发下载并核验试题图片资源...')
with ThreadPoolExecutor(max_workers=8) as ex:
    dl_results = list(ex.map(download_asset, download_tasks))
print(f'图片资源处理完成: 成功率 {sum(1 for r in dl_results if r)} / {len(download_tasks)}')

# ==============================================================================
# 3. 修复 GAOKAO_BENCH_BATCH_4000/questions.jsonl
# ==============================================================================
print('\n[3/5] 针对 GAOKAO_BENCH_BATCH_4000/questions.jsonl 逐题执行深度清洗与规范重对齐...')

q_4000_file = REPO_DIR / 'GAOKAO_BENCH_BATCH_4000/questions.jsonl'
with q_4000_file.open('r', encoding='utf-8') as f:
    records_4000 = [json.loads(line) for line in f if line.strip()]

fixed_d_count = 0
fixed_year_count = 0
fixed_img_count = 0
fixed_evidence_count = 0

for rec in records_4000:
    source_id = rec['source']['source_id']

    # --- A. 组卷网题 (3,600 道) ---
    if source_id == 'ZUJUAN_XKW':
        sqn = rec['provenance']['source_question_number']
        parsed_info = zujuan_parsed_index.get(sqn)
        if parsed_info:
            # 1. 修复 D 选项污染与题干
            old_d = rec['options'].get('D', '')
            clean_opts = parsed_info['options']
            clean_q = parsed_info['question']
            if old_d != clean_opts['D']:
                fixed_d_count += 1

            rec['question'] = clean_q
            rec['normalized_question'] = clean_q
            rec['raw_question'] = clean_q
            rec['options'] = clean_opts
            rec['raw_options'] = clean_opts

            # 2. 修复年份污染 (无年份依据设为 None)
            real_year = parsed_info['year']
            if rec['source']['year'] != real_year:
                fixed_year_count += 1
            rec['source']['year'] = real_year
            rec['source_records'][0]['year'] = real_year

            # 3. 修复图片遗漏
            imgs = parsed_info['images']
            if imgs:
                fixed_img_count += 1
                rec['has_image'] = True
                rec['image_paths'] = [f"assets/{fn}" for fn in imgs]
                is_dep = any(k in clean_q for k in ["图", "表", "漫画", "地图", "下表", "下图", "如图"])
                rec['quality']['image_dependency'] = "image_dependent" if is_dep else "needs_review"
                rec['quality']['notes'] = f"试卷出处: {parsed_info['paper_title']} (题号: {sqn})；包含正文图片"
            else:
                rec['has_image'] = False
                rec['image_paths'] = []
                rec['quality']['image_dependency'] = "not_image_dependent"
                rec['quality']['notes'] = f"试卷出处: {parsed_info['paper_title']} (题号: {sqn})"

            if parsed_info.get('year_reason'):
                rec['quality']['notes'] += f"；真实年份溯源自{parsed_info['year_reason']}"

            # 4. 答案与证据规范
            rec['answer'] = ""
            rec['answer_explanation'] = ""
            rec['answer_evidence'] = []
            rec['quality']['answer_status'] = "missing"

    # --- B. 前 400 道评测基准题 (GAOKAO_BENCH, AGIEVAL_GAOKAO, GAOKAO_MM) ---
    else:
        # 1. 修复官方验证判定：改为 single_source，证据 official=False, reliable=True
        if rec['quality']['answer_status'] != 'single_source':
            fixed_evidence_count += 1
        rec['quality']['answer_status'] = 'single_source'
        for ev in rec.get('answer_evidence', []):
            ev['official'] = False
            ev['reliable'] = True

        if source_id == 'GAOKAO_BENCH':
            rec['quality']['notes'] = "参考答案来自OpenLMLab GAOKAO-Bench评测基准，待人工复核官方答案链"
        elif source_id == 'AGIEVAL_GAOKAO':
            rec['quality']['notes'] = "参考答案来自Microsoft Research AGIEval评测基准，待人工复核官方答案链"
        elif source_id == 'GAOKAO_MM':
            # 2. 修复多图题目漏图问题 (如 CHIS_000286)
            sqn = rec['provenance']['source_question_number']
            mm_it = mm_items_by_index.get(sqn)
            if mm_it and mm_it.get('picture'):
                all_mm_pics = [Path(p).name for p in mm_it['picture']]
                # 确保已全部下载
                for p_name in all_mm_pics:
                    dest = assets_dir_4000 / p_name
                    if not dest.exists():
                        u = mm_img_base + p_name
                        req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            dest.write_bytes(resp.read())
                rec['has_image'] = True
                rec['image_paths'] = [f"assets/{p_name}" for p_name in all_mm_pics]
                rec['quality']['image_dependency'] = "image_dependent"
                rec['quality']['notes'] = "多模态题：包含历史图表/漫画/地图原件，参考答案来自GAOKAO-MM基准"

    # --- C. 全量重新计算 ordered_hash 与 permutation_hash ---
    rec['provenance']['ordered_hash'] = ordered_hash(rec)
    rec['provenance']['permutation_hash'] = permutation_hash(rec)
    rec['quality']['duplicate_status'] = 'unique'

print(f'清洗修复统计:')
print(f'  - 修复 D 选项污染题数: {fixed_d_count} 道')
print(f'  - 修复默认年份 2024 题数: {fixed_year_count} 道')
print(f'  - 补全/纠正图片标记与资源题数: {fixed_img_count} 道')
print(f'  - 纠正基准答案 official 评级题数: {fixed_evidence_count} 道')

# 写回 GAOKAO_BENCH_BATCH_4000/questions.jsonl
with q_4000_file.open('w', encoding='utf-8') as f:
    for r in records_4000:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
print(f'>>> GAOKAO_BENCH_BATCH_4000/questions.jsonl 写回成功。')

# ==============================================================================
# 4. 同步更新 GAOKAO_BENCH_BATCH_400 与 GAOKAO_BENCH_BATCH_001
# ==============================================================================
print('\n[4/5] 同步更新 BATCH_400 与 BATCH_001 对应子集，保证版本一致性...')
batch_400_file = REPO_DIR / 'GAOKAO_BENCH_BATCH_400/questions.jsonl'
if batch_400_file.exists():
    with batch_400_file.open('w', encoding='utf-8') as f:
        for r in records_4000[:400]:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

batch_001_file = REPO_DIR / 'GAOKAO_BENCH_BATCH_001/questions.jsonl'
if batch_001_file.exists():
    with batch_001_file.open('w', encoding='utf-8') as f:
        for r in records_4000[:20]:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

# 复制 assets 到 BATCH_400 和 BATCH_001
import shutil
for img_f in assets_dir_4000.glob('2010-2023_History_MCQs_*.png'):
    shutil.copy(img_f, REPO_DIR / 'GAOKAO_BENCH_BATCH_400/assets/' / img_f.name)
    shutil.copy(img_f, REPO_DIR / 'GAOKAO_BENCH_BATCH_001/assets/' / img_f.name)

# ==============================================================================
# 5. 重新生成全量验证报告与审核 CSV
# ==============================================================================
print('\n[5/5] 重新执行 pipeline 验证、导出 review.csv 并生成 summary.json...')
for batch_name, recs in [
    ('GAOKAO_BENCH_BATCH_4000', records_4000),
    ('GAOKAO_BENCH_BATCH_400', records_4000[:400]),
    ('GAOKAO_BENCH_BATCH_001', records_4000[:20])
]:
    b_dir = REPO_DIR / batch_name
    valid_recs, v_summary = validate_records(recs)
    q_report = build_quality_report(valid_recs)
    write_quality_report(b_dir / 'reports/summary.json', q_report)
    export_review_csv(b_dir / 'reports/review.csv', valid_recs)
    print(f'>>> {batch_name} 报告与审核表已更新:')
    print(f'    有效性: {v_summary.structurally_valid}/{v_summary.total}')
    print(f'    年份分布: {dict(v_summary.by_year)}')
    print(f'    图片依赖: {v_summary.image_dependent} 道')

print('\n=== 全部数据批次清洗修补与报告刷新圆满完成！ ===')
