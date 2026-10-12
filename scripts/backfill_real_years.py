import json
import os
import re
from bs4 import BeautifulSoup

RAW_DIR = "GAOKAO_BENCH_BATCH_4000/raw"
QUESTIONS_FILE = "GAOKAO_BENCH_BATCH_4000/questions.jsonl"

print(">>> 正在扫描并解析 raw/ 目录下所有原始 HTML 试卷...")
text_to_info = {}

html_files = [os.path.join(RAW_DIR, f) for f in os.listdir(RAW_DIR) if f.endswith(".html")]
for rf in html_files:
    with open(rf, "r", encoding="utf-8", errors="ignore") as fp:
        html = fp.read()
    soup = BeautifulSoup(html, "html.parser")
    for item in soup.find_all(class_="tk-quest-item"):
        cnt = item.find(class_="exam-item__cnt")
        info = item.find(class_="exam-item__info")
        if cnt and info:
            clean_txt = re.sub(r"[\s\n\r\t\u3000]+", "", cnt.get_text())[:40]
            text_to_info[clean_txt] = info.get_text(strip=True)

print(f">>> 成功建立试题索引，包含 {len(text_to_info)} 条原始试题元数据记录！")

def parse_exam_item(info_text):
    if not info_text or "该试题已被下架" in info_text:
        return None, "试题已下架无引证"

    # 1. 高考统考真题首发
    m_gk = re.findall(r"(20[12]\d)年(?:[0-9一二三四五六七八九十月]+)?(?:[^\s\|]+)?高考", info_text)
    if m_gk:
        y = int(m_gk[0])
        return min(y, 2026), f"历年高考统考真题({y}年)"

    # 2. 名校考卷引用
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
        if g_yr >= 2027:
            return 2026, f"名校考卷引用：{target_exam[:45]}"
        return min(g_yr, 2026), f"名校考卷引用：{target_exam[:45]}"

    m_yr = re.search(r"(20[12]\d)年", target_exam)
    if m_yr:
        y = int(m_yr.group(1))
        return min(y, 2026), f"名校考卷引用：{target_exam[:45]}"

    # 3. 题库录入时间兜底
    m_up = re.search(r"(20[12]\d)/\d{2}/\d{2}", info_text)
    if m_up:
        y = int(m_up.group(1))
        return min(y, 2026), f"题库系统录入时间({m_up.group(0)})"

    return None, "未找到确切年份"

updated_count = 0
retained_null = 0
all_updated_records = []

with open(QUESTIONS_FILE, "r", encoding="utf-8") as fp:
    for line in fp:
        q = json.loads(line)
        if q.get("source", {}).get("year") is None:
            clean_q = re.sub(r"[\s\n\r\t\u3000]+", "", q["normalized_question"])[:40]
            info_text = text_to_info.get(clean_q)
            if not info_text:
                for k, v in text_to_info.items():
                    if clean_q[:25] in k or k[:25] in clean_q:
                        info_text = v
                        break
            yr, reason = parse_exam_item(info_text)
            if yr is not None:
                q["source"]["year"] = yr
                if q.get("source_records"):
                    q["source_records"][0]["year"] = yr
                # 记录溯源说明
                orig_note = q.get("quality", {}).get("notes", "")
                q["quality"]["notes"] = f"{orig_note}；真实年份溯源自{reason}" if orig_note else f"真实年份溯源自{reason}"
                updated_count += 1
            else:
                retained_null += 1
        all_updated_records.append(q)

print(f">>> 回填完成！成功找回并回填真实年份：{updated_count} 题，规范保留 null：{retained_null} 题！")

with open(QUESTIONS_FILE, "w", encoding="utf-8") as fp:
    for q in all_updated_records:
        fp.write(json.dumps(q, ensure_ascii=False) + "\n")

print(f">>> 已写入最新数据至 {QUESTIONS_FILE}！")
