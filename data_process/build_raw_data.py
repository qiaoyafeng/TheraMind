"""Build raw_data_translate_{lang}.json for the TheraMind pipeline from CPsyCounR.json.

CPsyCounR stores 3134 Chinese counseling reports with Chinese field names, while
case_produce.py / data_produce.py expect a list of {patient_id: case} entries with
English field names. Patient ids are taken from new_data_translate.json so that the
session guidance and the generated medical records line up.

Usage (from the repository root):
    uv run python data_process/build_raw_data.py

The output name follows response_language in api_config.json:
    raw_data_translate_zh.json / raw_data_translate_en.json
"""
import json
from collections import defaultdict
from pathlib import Path

CONFIG = Path(__file__).parent.parent / "api_config.json"


def language_tag() -> str:
    """Read response_language from api_config.json, defaulting to en."""
    try:
        with open(CONFIG, encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        return "en"
    code = str(config.get("api_config", {}).get("openai", {}).get("response_language", "en")).lower()
    return code if code in {"zh", "en"} else "en"


TAG = language_tag()
SOURCE = "CPsyCounR.json"
GUIDANCE = next(
    (name for name in (f"new_data_translate_{TAG}.json", "new_data_translate.json") if Path(name).exists()),
    f"new_data_translate_{TAG}.json",
)
OUTPUT = f"raw_data_translate_{TAG}.json"

# Guidance category (from new_data_translate.json) -> English label + keywords used to
# classify a CPsyCounR row. The first bucket whose keywords hit wins, so more specific
# problems (addiction, severe disorders) must be listed before generic ones (mood).
CATEGORY_MAP = [
    (
        "成瘾与行为失控",
        "addiction and behavioral dyscontrol",
        ["成瘾", "网瘾", "赌博", "烟瘾", "瘾症", "暴食", "贪食", "啃噬"],
    ),
    (
        "特殊心理障碍",
        "special psychological disorders",
        ["精神分裂", "重度心理疾病", "双相", "躁郁", "偏执", "弱智", "反应性精神障碍", "幻听", "人格障碍", "自闭症"],
    ),
    (
        "儿童和青少年心理与行为问题",
        "child and adolescent psychological and behavioral issues",
        ["青少年", "中学生", "小学生", "初中生", "孩子教育", "厌学", "多动", "抽动", "早恋", "学生", "儿童", "高考", "考前", "考试压力"],
    ),
    (
        "神经症与躯体化问题",
        "neurosis and somatization",
        ["神经症", "强迫", "恐惧", "惊恐", "疑病", "躯体化", "心因性", "失眠", "睡眠障碍", "转换障碍", "焦虑症", "焦虑障碍", "焦虑性"],
    ),
    (
        "家庭与亲子关系问题",
        "family and parent-child relationship issues",
        ["亲子", "家庭", "婆媳", "夫妻", "原生家庭", "家暴"],
    ),
    (
        "情感与亲密关系问题",
        "emotional and intimate relationship issues",
        ["恋爱", "婚姻", "情感", "失恋", "两性", "伴侣", "婚前", "再婚", "第三者", "同性恋", "性心理", "性侵", "性创伤", "性变态", "恐艾", "性功能", "恋父"],
    ),
    (
        "人际关系与社会适应",
        "interpersonal relationships and social adjustment",
        ["人际", "社交", "适应", "职场", "职业", "沟通", "权威", "大学生", "面试"],
    ),
    (
        "压力与应激相关障碍",
        "stress and stress-related disorders",
        ["压力", "应激", "创伤", "哀悼", "疫情"],
    ),
    (
        "人格与成长问题",
        "personality and growth issues",
        ["成长", "人格", "自我", "人生", "督导", "分析心理学", "咨询师"],
    ),
    (
        "情绪障碍",
        "mood disorders",
        ["抑郁", "情绪", "心境", "焦虑"],
    ),
]

CATEGORY_LOOKUP = {zh: (en, keys) for zh, en, keys in CATEGORY_MAP}
MAX_PROCESS_CHARS = 2000


def first_text(value) -> str:
    """CPsyCounR fields are lists of paragraphs; return the first non-empty one."""
    if isinstance(value, list):
        for item in value:
            if str(item).strip():
                return str(item).strip()
        return ""
    return str(value or "").strip()


def join_text(value) -> str:
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def classify(row) -> str:
    """Return the guidance category this CPsyCounR row belongs to, or ''."""
    raw_categories = row.get("案例类别") or []
    if not isinstance(raw_categories, list):
        raw_categories = [raw_categories]
    joined = " ".join(str(item) for item in raw_categories)
    # Fall back to the title so rows with an empty category can still be placed.
    haystack = joined + " " + first_text(row.get("案例标题"))
    for zh, _en, keywords in CATEGORY_MAP:
        if any(keyword in haystack for keyword in keywords):
            return zh
    return ""


def build_case(row, category_zh: str) -> dict:
    summary = first_text(row.get("案例简述"))
    process = join_text(row.get("咨询经过"))
    if len(process) > MAX_PROCESS_CHARS:
        process = process[:MAX_PROCESS_CHARS] + " ..."
    return {
        "case title": first_text(row.get("案例标题")),
        "case category": CATEGORY_LOOKUP[category_zh][0],
        "case summary": summary,
        "case description": summary,
        "consultation process": process,
    }


def main():
    rows = json.load(open(SOURCE, encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"{SOURCE} should contain a list of cases")

    guidance = json.load(open(GUIDANCE, encoding="utf-8"))
    patient_ids = list(guidance)

    pools = defaultdict(list)
    unmatched = 0
    for row in rows:
        category_zh = classify(row)
        if category_zh:
            pools[category_zh].append(row)
        else:
            unmatched += 1

    print(f"{SOURCE}: {len(rows)} cases, {unmatched} without a matching category")
    for zh, _en, _keys in CATEGORY_MAP:
        print(f"  pool {zh}: {len(pools[zh])}")

    used = defaultdict(int)
    result = []
    for patient_id in patient_ids:
        category_zh = patient_id.split("_", 1)[1]
        if category_zh not in CATEGORY_LOOKUP:
            raise ValueError(f"unknown category in patient id: {patient_id}")
        pool = pools[category_zh]
        if not pool:
            raise ValueError(f"no source case for category: {category_zh}")
        row = pool[used[category_zh] % len(pool)]
        used[category_zh] += 1
        result.append({patient_id: build_case(row, category_zh)})

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(result)} patients to {OUTPUT}")


if __name__ == "__main__":
    main()
