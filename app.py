# -*- coding: utf-8 -*-
"""
堅六壬 - 大六壬排盤 Streamlit App（重構版）
古風玄學視覺風格 · 互動式天地盤 · AI 斷事分析
"""
import html as html_module
import math
import os, sys, urllib, urllib.parse, calendar, json, datetime

# 將 src/ 加入模組搜尋路徑，使 kinliuren、jieqi 等模組可直接匯入
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import streamlit as st
import pendulum as pdlm
from contextlib import contextmanager, redirect_stdout
from sxtwl import fromSolar
from io import StringIO
from bidict import bidict
import streamlit.components.v1 as components
from kinliuren import kinliuren
from kinqimen import kinqimen
from jieqi import *
import jieqi
from cerebras_client import CerebrasClient, DEFAULT_MODEL as DEFAULT_CEREBRAS_MODEL

# ======================================================================
# 工具函式（與原版相同，保留後端邏輯不動）
# ======================================================================

@contextmanager
def st_capture(output_func):
    """擷取 stdout 輸出並導向 Streamlit 元件"""
    with StringIO() as stdout, redirect_stdout(stdout):
        old_write = stdout.write
        def new_write(string):
            ret = old_write(string)
            output_func(stdout.getvalue())
            return ret
        stdout.write = new_write
        yield

def get_file_content_as_string(path):
    """從 GitHub raw 取得文件內容"""
    url = 'https://raw.githubusercontent.com/kentang2017/kinliuren/master/' + path
    response = urllib.request.urlopen(url)
    return response.read().decode("utf-8")

def multi_key_dict_get(d, k):
    for keys, v in d.items():
        if k in keys:
            return v
    return None

def new_list(olist, o):
    zhihead_code = olist.index(o)
    res1 = []
    for i in range(len(olist)):
        res1.append(olist[zhihead_code % len(olist)])
        zhihead_code = zhihead_code + 1
    return res1

def weekday(y, m, d):
    cweekdays = ["星期" + i for i in list("日一二三四五六")]
    dayNumber = calendar.weekday(y, m, d)
    return dict(zip([int(i) for i in list("6012345")], cweekdays)).get(dayNumber)

def day_chin(zhi, weekday_str):
    three_zhi = "申子辰,巳酉丑,寅午戌,亥卯未".split(",")
    head = ["虛畢翼箕奎鬼氐", "房危觜軫斗婁柳", "星心室參角牛胃", "昴張尾壁井亢女"]
    cweekdays = ["星期" + i for i in list("日一二三四五六")]
    ydict = {}
    for i in range(4):
        b = {tuple(list(three_zhi[i])): dict(zip(cweekdays, list(head[i])))}
        ydict.update(b)
    return multi_key_dict_get(ydict, zhi).get(weekday_str)


# ======================================================================
# 五行顏色映射
# ======================================================================
WUXING_COLORS = {
    "木": "#4CAF50",  # 青綠
    "火": "#c8102e",  # 朱砂紅
    "土": "#d4a017",  # 金黃
    "金": "#E0E0E0",  # 銀白
    "水": "#42A5F5",  # 水藍
}

# 干支五行對照
GANZHI_WUXING = {}
for ganzhi_chars, wuxing_element in [
    ("甲寅乙卯", "木"), ("丙巳丁午", "火"), ("壬亥癸子", "水"),
    ("庚申辛酉", "金"), ("未丑戊己辰戌", "土"),
]:
    for ch in ganzhi_chars:
        GANZHI_WUXING[ch] = wuxing_element

def get_wuxing_color(char):
    """根據干支字元傳回五行顏色"""
    wx = GANZHI_WUXING.get(char, "")
    return WUXING_COLORS.get(wx, "#f5f0e8")

# 天將吉凶對照
GENERAL_FORTUNE = {
    "貴": "大吉", "后": "吉", "陰": "吉", "玄": "凶", "常": "吉", "虎": "大凶",
    "空": "凶", "龍": "大吉", "勾": "凶", "合": "吉", "雀": "凶", "蛇": "凶",
}
FORTUNE_COLORS = {
    "大吉": "#4CAF50", "吉": "#d4a017", "平": "#888888", "凶": "#FF6B6B", "大凶": "#c8102e",
}

# ======================================================================
# Cerebras AI 設定
# ======================================================================
CEREBRAS_MODEL_OPTIONS = [
    "qwen-3-235b-a22b-instruct-2507",
    "llama-4-scout-17b-16e-instruct",
    "llama3.1-8b",
    "llama-3.3-70b",
    "deepseek-r1-distill-llama-70b",
]
CEREBRAS_MODEL_DESCRIPTIONS = {
    "qwen-3-235b-a22b-instruct-2507": "Cerebras: 快速推理，適合快速迭代。",
    "llama-4-scout-17b-16e-instruct": "Cerebras: 優化導引式工作流程。",
    "llama3.1-8b": "Cerebras: 輕量快速，適合簡單任務。",
    "llama-3.3-70b": "Cerebras: 最強推理能力。",
    "deepseek-r1-distill-llama-70b": "DeepSeek 蒸餾模型。",
}

SYSTEM_PROMPTS_FILE = "system_prompts.json"
AI_MIN_MAX_TOKENS = 40000
AI_MAX_MAX_TOKENS = 200000


def load_system_prompts():
    DEFAULT_SYSTEM_PROMPT = (
        "你是一位大六壬大師，熟悉《大六壬大全》、《六壬粹言》、《壬學瑣記》等經典古籍及歷史案例。請根據提供的六壬排盤數據，進行以下操作：\n"
        "1. 解釋盤局的關鍵要素（四課、三傳、天將、天盤地盤等）。\n"
        "2. 結合六壬經典理論，分析盤局的吉凶和潛在影響。\n"
        "3. 根據日課、月課、時課的格局及三傳、四課，詳細評估當前運勢趨勢。\n"
        "4. 提供實用的建議或應對策略。\n"
        "請以清晰的結構（分段、標題）呈現，語言專業且易懂，適當引用歷史案例或經典理論。"
    )
    try:
        with open(SYSTEM_PROMPTS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        default_data = {
            "prompts": [{"name": "六壬大師", "content": DEFAULT_SYSTEM_PROMPT}],
            "selected": "六壬大師",
        }
        with open(SYSTEM_PROMPTS_FILE, "w") as f:
            json.dump(default_data, f, indent=2)
        return default_data


def save_system_prompts(prompts_data):
    try:
        with open(SYSTEM_PROMPTS_FILE, "w") as f:
            json.dump(prompts_data, f, indent=2)
        return True
    except Exception as e:
        st.error(f"錯誤儲存提示：{e}")
        return False


def format_liuren_results_for_prompt(chart_text, ltext, ltext1, ltext2, divination_purpose=""):
    """將排盤結果格式化為 AI prompt，可帶入占卜事由"""
    prompt_lines = [
        "以下是大六壬排盤的計算結果，請根據這些數據提供詳細的分析和解釋：",
        "",
        chart_text,
        "",
        "【月課詳細數據】",
        f"格局: {ltext.get('格局', '')}",
        f"三傳: 初傳{''.join(ltext.get('三傳', {}).get('初傳', []))} | 中傳{''.join(ltext.get('三傳', {}).get('中傳', []))} | 末傳{''.join(ltext.get('三傳', {}).get('末傳', []))}",
        f"四課: {ltext.get('四課', '')}",
        f"天將: {ltext.get('地轉天將', '')}",
        f"天盤: {ltext.get('地轉天盤', '')}",
        f"日馬: {ltext.get('日馬', '')}",
        "",
        "【日課詳細數據】",
        f"格局: {ltext1.get('格局', '')}",
        f"三傳: 初傳{''.join(ltext1.get('三傳', {}).get('初傳', []))} | 中傳{''.join(ltext1.get('三傳', {}).get('中傳', []))} | 末傳{''.join(ltext1.get('三傳', {}).get('末傳', []))}",
        f"四課: {ltext1.get('四課', '')}",
        f"天將: {ltext1.get('地轉天將', '')}",
        f"天盤: {ltext1.get('地轉天盤', '')}",
        f"日馬: {ltext1.get('日馬', '')}",
        "",
        "【時課詳細數據】",
        f"格局: {ltext2.get('格局', '')}",
        f"三傳: 初傳{''.join(ltext2.get('三傳', {}).get('初傳', []))} | 中傳{''.join(ltext2.get('三傳', {}).get('中傳', []))} | 末傳{''.join(ltext2.get('三傳', {}).get('末傳', []))}",
        f"四課: {ltext2.get('四課', '')}",
        f"天將: {ltext2.get('地轉天將', '')}",
        f"天盤: {ltext2.get('地轉天盤', '')}",
        f"日馬: {ltext2.get('日馬', '')}",
    ]
    if divination_purpose:
        prompt_lines.insert(0, f"【占卜事由】{divination_purpose}\n")
        prompt_lines.append(f"\n請特別針對「{divination_purpose}」這個問題進行分析和解讀。")
    return "\n".join(prompt_lines)


# ======================================================================
# 頁面設定
# ======================================================================
st.set_page_config(
    layout="wide",
    page_title="堅六壬 · 大六壬排盤",
    page_icon="icon.jpg",
)

# ======================================================================
# 全域自訂 CSS — 古風玄學主題
# ======================================================================
st.markdown("""
<style>
/* === Google Fonts === */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&family=Noto+Serif+SC:wght@400;600;700&display=swap');

/* === 全局背景與字體 === */
:root {
    --bg-primary: #0f0f0f;
    --bg-secondary: #1a1a1a;
    --gold: #d4a017;
    --gold-light: #e8c547;
    --cinnabar: #c8102e;
    --cream: #f5f0e8;
    --cream-dim: #b8b0a0;
    --wood-green: #4CAF50;
    --fire-red: #c8102e;
    --earth-yellow: #d4a017;
    --metal-white: #E0E0E0;
    --water-blue: #42A5F5;
}

.stApp {
    background-color: var(--bg-primary) !important;
    background-image: url("data:image/svg+xml,%3Csvg width='400' height='400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.04'/%3E%3C/svg%3E");
    font-family: 'Noto Sans SC', sans-serif !important;
}

/* === 標題 — 仿宋體風格 === */
h1, h2, h3 {
    font-family: 'Noto Serif SC', serif !important;
    color: var(--gold) !important;
    letter-spacing: 0.1em;
}
h1 { font-size: 2rem !important; }

/* === 側邊欄 === */
section[data-testid="stSidebar"] {
    background-color: #111111 !important;
    border-right: 1px solid #2a2a2a;
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: var(--gold) !important;
    font-size: 1.1rem !important;
}

/* === Tab 標籤 === */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background-color: var(--bg-secondary);
    border-radius: 8px;
    padding: 4px;
}
.stTabs [data-baseweb="tab"] {
    color: var(--cream-dim) !important;
    font-family: 'Noto Serif SC', serif !important;
    font-weight: 500;
    border-radius: 6px;
    padding: 8px 16px;
}
.stTabs [aria-selected="true"] {
    background-color: #2a2520 !important;
    color: var(--gold) !important;
    border-bottom: 2px solid var(--gold) !important;
}

/* === 卡片通用樣式 === */
.liuren-card {
    background: linear-gradient(135deg, #1a1815 0%, #141210 100%);
    border: 1px solid #3a3020;
    border-radius: 12px;
    padding: 20px;
    margin: 8px 0;
    transition: all 0.3s ease;
    box-shadow: 0 2px 8px rgba(0,0,0,0.4);
}
.liuren-card:hover {
    border-color: var(--gold);
    box-shadow: 0 4px 16px rgba(212,160,23,0.15);
    transform: translateY(-2px);
}
.liuren-card h4 {
    color: var(--gold) !important;
    font-family: 'Noto Serif SC', serif !important;
    margin: 0 0 12px 0;
    font-size: 1.1rem;
    border-bottom: 1px solid #3a3020;
    padding-bottom: 8px;
}

/* === 三傳垂直卡片 === */
.sanchuan-card {
    background: linear-gradient(180deg, #1e1a14 0%, #141210 100%);
    border: 1px solid #3a3020;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
    position: relative;
    margin: 6px 0;
}
.sanchuan-card .zhi-char {
    font-size: 2rem;
    font-family: 'Noto Serif SC', serif;
    font-weight: 700;
}
.sanchuan-card .general-name {
    font-size: 0.9rem;
    color: var(--cream-dim);
    margin-top: 4px;
}
.sanchuan-card .relation {
    font-size: 0.8rem;
    margin-top: 4px;
    padding: 2px 8px;
    border-radius: 4px;
    display: inline-block;
}

/* === 四課卡片 === */
.sike-card {
    background: linear-gradient(135deg, #1a1815 0%, #141210 100%);
    border: 1px solid #3a3020;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
    min-height: 120px;
}
.sike-card .ke-label {
    font-size: 0.85rem;
    color: var(--gold);
    font-family: 'Noto Serif SC', serif;
    margin-bottom: 8px;
}
.sike-card .ke-top, .sike-card .ke-bottom {
    font-size: 1.6rem;
    font-family: 'Noto Serif SC', serif;
    font-weight: 700;
    line-height: 1.4;
}
.sike-card .ke-general {
    font-size: 0.8rem;
    color: var(--cream-dim);
    margin-top: 4px;
}

/* === 神煞標籤 === */
.shensha-tag {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.85rem;
    margin: 3px 4px;
    cursor: default;
    transition: all 0.2s;
    border: 1px solid transparent;
}
.shensha-tag:hover {
    transform: scale(1.05);
    border-color: rgba(255,255,255,0.2);
}
.tag-daji { background: rgba(76,175,80,0.2); color: #4CAF50; border-color: rgba(76,175,80,0.3); }
.tag-ji { background: rgba(212,160,23,0.2); color: #d4a017; border-color: rgba(212,160,23,0.3); }
.tag-ping { background: rgba(136,136,136,0.2); color: #888; border-color: rgba(136,136,136,0.3); }
.tag-xiong { background: rgba(255,107,107,0.2); color: #FF6B6B; border-color: rgba(255,107,107,0.3); }
.tag-daxiong { background: rgba(200,16,46,0.2); color: #c8102e; border-color: rgba(200,16,46,0.3); }

/* === 連線動畫 === */
.flow-connector {
    text-align: center;
    color: var(--gold);
    font-size: 1.2rem;
    line-height: 0.8;
    opacity: 0.6;
}

/* === 排盤概覽資訊欄 === */
.info-badge {
    display: inline-block;
    background: rgba(212,160,23,0.12);
    border: 1px solid rgba(212,160,23,0.25);
    border-radius: 8px;
    padding: 6px 14px;
    margin: 4px 6px 4px 0;
    font-size: 0.9rem;
    color: var(--cream);
}
.info-badge .label {
    color: var(--gold);
    font-weight: 500;
    margin-right: 4px;
}

/* === 歷史記錄表格 === */
.history-item {
    background: var(--bg-secondary);
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 6px 0;
    cursor: pointer;
    transition: all 0.2s;
}
.history-item:hover {
    border-color: var(--gold);
    background: #1e1a14;
}

/* === 行動裝置適配 === */
@media (max-width: 768px) {
    h1 { font-size: 1.4rem !important; }
    .liuren-card { padding: 12px; }
    .sike-card .ke-top, .sike-card .ke-bottom { font-size: 1.2rem; }
    .sanchuan-card .zhi-char { font-size: 1.6rem; }
    .stTabs [data-baseweb="tab"] { padding: 6px 10px; font-size: 0.85rem; }
}

/* === 按鈕美化 === */
.stButton > button {
    border-color: var(--gold) !important;
    color: var(--gold) !important;
    transition: all 0.3s !important;
}
.stButton > button:hover {
    background-color: rgba(212,160,23,0.15) !important;
    border-color: var(--gold-light) !important;
    color: var(--gold-light) !important;
}

/* === 分隔線 === */
hr {
    border-color: #2a2520 !important;
}

/* === Expander 美化 === */
.streamlit-expanderHeader {
    font-family: 'Noto Serif SC', serif !important;
    color: var(--gold) !important;
}
</style>
""", unsafe_allow_html=True)

# ======================================================================
# Session State 初始化
# ======================================================================
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "history" not in st.session_state:
    st.session_state.history = []
if "form_key_suffix" not in st.session_state:
    st.session_state.form_key_suffix = 0

# ======================================================================
# 從 URL query params 讀取預設值（分享連結功能）
# ======================================================================
qp = st.query_params
qp_year = int(qp.get("y", 0)) if qp.get("y") else None
qp_month = int(qp.get("m", 0)) if qp.get("m") else None
qp_day = int(qp.get("d", 0)) if qp.get("d") else None
qp_hour = int(qp.get("h", 0)) if qp.get("h") else None
qp_minute = int(qp.get("mi", 0)) if qp.get("mi") else None
qp_purpose = qp.get("purpose", "")

# ======================================================================
# 側邊欄 — 輸入區
# ======================================================================
with st.sidebar:
    st.markdown("## 🔮 堅六壬")
    st.caption("大六壬排盤系統")
    st.markdown("---")

    # --- 一鍵「現在起課」 ---
    if st.button("⚡ 立即起課（現在時間）", use_container_width=True, type="primary"):
        now = pdlm.now(tz='Asia/Hong_Kong')
        st.session_state['dt_date'] = now.date()
        st.session_state['dt_time'] = now.time()
        st.rerun()

    st.markdown("---")
    st.markdown("### 📅 日期與時間")

    # 預設為當前香港時間，或 query param
    default_datetime = pdlm.now(tz='Asia/Hong_Kong')

    default_date = (
        datetime.date(qp_year, qp_month, qp_day)
        if qp_year and qp_month and qp_day
        else default_datetime.date()
    )
    default_time = (
        datetime.time(qp_hour, qp_minute)
        if qp_hour is not None and qp_minute is not None
        else default_datetime.time()
    )

    selected_date = st.date_input(
        "日期",
        value=default_date,
        min_value=datetime.date(1900, 1, 1),
        max_value=datetime.date(2100, 12, 31),
        key='dt_date',
    )
    selected_time = st.time_input(
        "時間",
        value=default_time,
        step=datetime.timedelta(minutes=1),
        key='dt_time',
    )

    y = selected_date.year
    m_val = selected_date.month
    d_val = selected_date.day
    h_val = selected_time.hour
    mi_val = selected_time.minute

    st.caption(f"🕐 {y}年{m_val}月{d_val}日 {h_val:02d}:{mi_val:02d}  (HKT)")

    st.markdown("---")
    st.markdown("### 📝 占卜事由")
    divination_purpose = st.text_area(
        "請輸入占卜事由（必填）",
        value=qp_purpose,
        height=80,
        placeholder="例：問近期事業發展方向、感情是否順利...",
        key="divination_purpose",
    )

    st.markdown("---")
    st.markdown("### 🤖 AI 設置")
    selected_model = st.selectbox(
        "AI 模型",
        options=CEREBRAS_MODEL_OPTIONS,
        index=0,
        key="cerebras_model_selector",
    )

    # --- 系統提示管理 ---
    system_prompts_data = load_system_prompts()
    prompts_list = system_prompts_data.get("prompts", [])
    prompt_names = [prompt["name"] for prompt in prompts_list]
    selected_prompt = system_prompts_data.get("selected")

    if prompt_names:
        selected_index = 0
        if selected_prompt in prompt_names:
            selected_index = prompt_names.index(selected_prompt)

        selected_name = st.selectbox(
            "選擇系統提示",
            options=prompt_names,
            index=selected_index,
            key="system_prompt_selector",
        )
        system_prompts_data["selected"] = selected_name

        selected_content = ""
        for prompt in prompts_list:
            if prompt["name"] == selected_name:
                selected_content = prompt["content"]
                break

        if 'system_prompt' not in st.session_state:
            st.session_state.system_prompt = selected_content
        elif selected_name != st.session_state.get("last_selected_prompt"):
            st.session_state.system_prompt = selected_content

        st.session_state.last_selected_prompt = selected_name

        with st.expander("✏️ 編輯提示", expanded=False):
            new_content = st.text_area(
                "系統提示內容",
                value=st.session_state.system_prompt,
                height=120,
                key="system_prompt_editor",
            )
            st.session_state.system_prompt = new_content

            col_u, col_d = st.columns(2)
            with col_u:
                if st.button("💾 更新", key="update_prompt_button", use_container_width=True):
                    for prompt in prompts_list:
                        if prompt["name"] == selected_name:
                            prompt["content"] = new_content
                            break
                    if save_system_prompts(system_prompts_data):
                        st.toast(f"✅ 已更新 '{selected_name}'")
            with col_d:
                if st.button("❌ 刪除", key="delete_prompt_button", disabled=len(prompts_list) <= 1, use_container_width=True):
                    prompts_list = [p for p in prompts_list if p["name"] != selected_name]
                    system_prompts_data["prompts"] = prompts_list
                    if selected_name == selected_prompt and prompts_list:
                        system_prompts_data["selected"] = prompts_list[0]["name"]
                    if save_system_prompts(system_prompts_data):
                        st.toast(f"✅ 已刪除 '{selected_name}'")
                        st.rerun()

    # --- 新增提示 ---
    name_key = f"new_prompt_name_{st.session_state.form_key_suffix}"
    content_key = f"new_prompt_content_{st.session_state.form_key_suffix}"
    with st.expander("➕ 新增提示", expanded=False):
        new_prompt_name = st.text_input("新提示名稱", key=name_key)
        new_prompt_content = st.text_area("新提示內容", height=80, key=content_key)
        if st.button("➕ 新增", key="add_prompt_button", disabled=not new_prompt_name or not new_prompt_content):
            if new_prompt_name in prompt_names:
                st.error(f"名稱 '{new_prompt_name}' 已存在。")
            else:
                prompts_list.append({"name": new_prompt_name, "content": new_prompt_content})
                system_prompts_data["prompts"] = prompts_list
                if save_system_prompts(system_prompts_data):
                    st.session_state.form_key_suffix += 1
                    st.toast(f"✅ 已新增 '{new_prompt_name}'")
                    st.rerun()

    # --- 高級設置 ---
    if st.toggle("🔧 高級設置", key="advanced_settings_toggle"):
        st.session_state.ai_max_tokens = st.slider(
            "最大 Tokens", AI_MIN_MAX_TOKENS, AI_MAX_MAX_TOKENS,
            st.session_state.get("ai_max_tokens", AI_MAX_MAX_TOKENS),
            key="ai_max_tokens_slider",
        )
        st.session_state.ai_temperature = st.slider(
            "溫度", 0.0, 1.5,
            st.session_state.get("ai_temperature", 0.7),
            step=0.05, key="ai_temperature_slider",
        )

    # --- 歷史記錄 ---
    if st.session_state.history:
        st.markdown("---")
        st.markdown("### 📜 歷史記錄")
        for idx, rec in enumerate(reversed(st.session_state.history[-10:])):
            purpose_display = rec['purpose'][:12] + ('...' if len(rec['purpose']) > 12 else '')
            if st.button(f"🕐 {rec['time']} — {purpose_display}", key=f"hist_{idx}", use_container_width=True):
                st.session_state['dt_date'] = datetime.date(rec['y'], rec['m'], rec['d'])
                st.session_state['dt_time'] = datetime.time(rec['h'], rec['mi'])
                st.rerun()


# ======================================================================
# 排盤計算（保留全部後端邏輯）
# ======================================================================
cm = jieqi.lunar_date_d(y, m_val, d_val).get("農曆月")
qgz = gangzhi(y, m_val, d_val, h_val, mi_val)
jq_val = jq(y, m_val, d_val, h_val, mi_val)
liuren_month = kinliuren.Liuren(jq_val, cm, qgz[1], qgz[2]).result_d(0)
liuren_day = kinliuren.Liuren(jq_val, cm, qgz[2], qgz[3]).result(0)
liuren_hour = kinliuren.Liuren(jq_val, cm, qgz[3], qgz[4]).result_m(0)

ltext = liuren_month
ltext1 = liuren_day
ltext2 = liuren_hour

dhorse1 = ltext.get("日馬")
dhorse2 = ltext1.get("日馬")
dhorse3 = ltext2.get("日馬")

dchin = day_chin(qgz[2][1], weekday(y, m_val, d_val))
zhi_list = list("子丑寅卯辰巳午未申酉戌亥")
zdict = dict(zip(zhi_list, range(1, 13)))

# 構建純文字盤面（保留向後相容性）
a_str = "日期︰{}年{}月{}日{}時{}分\n".format(y, m_val, d_val, h_val, mi_val)
b_str = "格局︰{}\n".format(ltext.get("格局")[0])
c_str = "節氣︰{}\n".format(jq_val)
d_str = "干支︰{}年 {}月 {}日 {}時 {}分\n".format(qgz[0], qgz[1], qgz[2], qgz[3], qgz[4])
d2_str = "日馬︰{}(月) {}(日) {}(時)\n\n".format(dhorse1, dhorse2, dhorse3)
chart_text = a_str + b_str + c_str + d_str + d2_str

# 存入 session state
st.session_state.chart_text = chart_text
st.session_state.chart_ltext = ltext
st.session_state.chart_ltext1 = ltext1
st.session_state.chart_ltext2 = ltext2

# 記錄歷史
if divination_purpose:
    history_entry = {
        "time": f"{y}/{m_val}/{d_val} {h_val:02d}:{mi_val:02d}",
        "purpose": divination_purpose,
        "y": y, "m": m_val, "d": d_val, "h": h_val, "mi": mi_val,
    }
    # 避免重複記錄
    if not st.session_state.history or st.session_state.history[-1].get("time") != history_entry["time"]:
        st.session_state.history.append(history_entry)
        if len(st.session_state.history) > 20:
            st.session_state.history = st.session_state.history[-20:]

# ======================================================================
# 分享連結
# ======================================================================
share_url = f"?y={y}&m={m_val}&d={d_val}&h={h_val}&mi={mi_val}"
if divination_purpose:
    # 限制事由長度避免過長 URL，並以 URL-encode 處理特殊字元
    safe_purpose = divination_purpose[:200]
    share_url += f"&purpose={urllib.parse.quote(safe_purpose)}"


# ======================================================================
# 輔助函式：生成天地盤 SVG 圓盤
# ======================================================================
def generate_sky_earth_svg(earth_to_sky, earth_to_general, width=480, height=480):
    """生成互動式天地盤 SVG 圓盤"""
    zhi_order = list("巳午未申酉戌亥子丑寅卯辰")  # 十二宮位順時針排列
    cx, cy = width // 2, height // 2
    r_outer = 200  # 外圈半徑
    r_middle = 150  # 中圈半徑
    r_inner = 100   # 內圈半徑

    svg_elements = []

    # 背景
    svg_elements.append(f'<rect width="{width}" height="{height}" fill="#0f0f0f" rx="16"/>')
    # 外圈（地盤 — 固定）
    svg_elements.append(f'<circle cx="{cx}" cy="{cy}" r="{r_outer}" fill="none" stroke="#3a3020" stroke-width="2"/>')
    # 中圈（天盤）
    svg_elements.append(f'<circle cx="{cx}" cy="{cy}" r="{r_middle}" fill="none" stroke="#d4a017" stroke-width="1.5" stroke-dasharray="4,2"/>')
    # 內圈
    svg_elements.append(f'<circle cx="{cx}" cy="{cy}" r="{r_inner}" fill="none" stroke="#2a2520" stroke-width="1"/>')

    # 中心文字
    svg_elements.append(f'<text x="{cx}" y="{cy - 10}" text-anchor="middle" fill="#d4a017" font-size="16" font-family="Noto Serif SC, serif" font-weight="700">天地盤</text>')
    svg_elements.append(f'<text x="{cx}" y="{cy + 14}" text-anchor="middle" fill="#b8b0a0" font-size="11" font-family="Noto Sans SC, sans-serif">外:地盤 中:天盤 內:天將</text>')

    for i, earth_zhi in enumerate(zhi_order):
        angle_deg = -90 + i * 30  # 從正上方開始
        angle_rad = math.radians(angle_deg)

        sky_zhi = earth_to_sky.get(earth_zhi, "?")
        general = earth_to_general.get(earth_zhi, "?")

        # 地盤（外圈）位置
        ex = cx + r_outer * math.cos(angle_rad) * 0.88
        ey = cy + r_outer * math.sin(angle_rad) * 0.88

        # 天盤（中圈）位置
        sx = cx + r_middle * math.cos(angle_rad) * 0.88
        sy = cy + r_middle * math.sin(angle_rad) * 0.88

        # 天將（內圈）位置
        gx = cx + r_inner * math.cos(angle_rad) * 0.82
        gy = cy + r_inner * math.sin(angle_rad) * 0.82

        # 地盤文字
        earth_color = get_wuxing_color(earth_zhi)
        svg_elements.append(
            f'<text x="{ex:.1f}" y="{ey:.1f}" text-anchor="middle" dominant-baseline="central" '
            f'fill="{earth_color}" font-size="16" font-family="Noto Serif SC, serif" font-weight="700">{earth_zhi}</text>'
        )

        # 天盤文字
        sky_color = get_wuxing_color(sky_zhi)
        svg_elements.append(
            f'<text x="{sx:.1f}" y="{sy:.1f}" text-anchor="middle" dominant-baseline="central" '
            f'fill="{sky_color}" font-size="14" font-family="Noto Serif SC, serif" font-weight="600">{sky_zhi}</text>'
        )

        # 天將文字
        fortune = GENERAL_FORTUNE.get(general, "平")
        gen_color = FORTUNE_COLORS.get(fortune, "#888")
        svg_elements.append(
            f'<text x="{gx:.1f}" y="{gy:.1f}" text-anchor="middle" dominant-baseline="central" '
            f'fill="{gen_color}" font-size="11" font-family="Noto Sans SC, sans-serif">{general}</text>'
        )

        # 連線
        svg_elements.append(
            f'<line x1="{ex:.1f}" y1="{ey:.1f}" x2="{sx:.1f}" y2="{sy:.1f}" '
            f'stroke="#2a2520" stroke-width="0.5" opacity="0.4"/>'
        )

    svg_content = "\n".join(svg_elements)
    return f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">{svg_content}</svg>'


def render_sanchuan_card(label, data, icon):
    """渲染三傳單張卡片"""
    zhi = data[0]
    general = data[1]
    relation = data[2]
    kong = data[3] if len(data) > 3 else ""
    zhi_color = get_wuxing_color(zhi)
    kong_str = f'<span style="color:#FF6B6B;font-size:0.75rem;">（空：{kong}）</span>' if kong and kong != "空" else ""
    # 六親的顏色
    rel_colors = {"父母": "#42A5F5", "子孫": "#4CAF50", "財妻": "#d4a017", "兄弟": "#888", "官鬼": "#c8102e"}
    rel_color = rel_colors.get(relation, "#888")

    return f"""
    <div class="sanchuan-card">
        <div style="color:#d4a017;font-size:0.8rem;font-family:'Noto Serif SC',serif;">{icon} {label}</div>
        <div class="zhi-char" style="color:{zhi_color};">{zhi}</div>
        <div class="general-name">{general}</div>
        <div class="relation" style="background:rgba(0,0,0,0.3);color:{rel_color};">{relation}</div>
        {kong_str}
    </div>
    """


def render_sike_card(label, data, general):
    """渲染四課單張卡片"""
    top_char = data[0][0]
    bottom_char = data[0][1]
    top_color = get_wuxing_color(top_char)
    bottom_color = get_wuxing_color(bottom_char)

    return f"""
    <div class="sike-card">
        <div class="ke-label">{label}</div>
        <div class="ke-top" style="color:{top_color};">{top_char}</div>
        <div style="color:#3a3020;font-size:0.8rem;">—</div>
        <div class="ke-bottom" style="color:{bottom_color};">{bottom_char}</div>
        <div class="ke-general">{general}</div>
    </div>
    """


# ======================================================================
# 主畫面 — 5 Tab 佈局
# ======================================================================
st.markdown("# 🔮 堅六壬 · 大六壬排盤")

tab1, tab2, tab3, tab4, tab5, tab_guji, tab_links, tab_update = st.tabs([
    "📊 排盤總覽", "🎴 三傳四課", "🌀 天地盤", "✨ 神煞格局", "🔍 斷事參考",
    "📚 古籍", "🔗 連結", "🆕 更新",
])

# ------------------------------------------------------------------
# Tab 1: 排盤總覽
# ------------------------------------------------------------------
with tab1:
    # 資訊摘要
    st.markdown(f"""
    <div style="margin-bottom:16px;">
        <span class="info-badge"><span class="label">日期</span>{y}年{m_val}月{d_val}日 {h_val:02d}:{mi_val:02d}</span>
        <span class="info-badge"><span class="label">節氣</span>{jq_val}</span>
        <span class="info-badge"><span class="label">農曆</span>{cm}</span>
        <span class="info-badge"><span class="label">格局</span>{ltext.get("格局")[0]}</span>
        <span class="info-badge"><span class="label">日馬</span>{dhorse1}(月) {dhorse2}(日) {dhorse3}(時)</span>
    </div>
    """, unsafe_allow_html=True)

    # 干支資訊
    st.markdown(f"""
    <div style="margin-bottom:16px;">
        <span class="info-badge"><span class="label">年柱</span>{qgz[0]}</span>
        <span class="info-badge"><span class="label">月柱</span>{qgz[1]}</span>
        <span class="info-badge"><span class="label">日柱</span>{qgz[2]}</span>
        <span class="info-badge"><span class="label">時柱</span>{qgz[3]}</span>
        <span class="info-badge"><span class="label">分柱</span>{qgz[4]}</span>
    </div>
    """, unsafe_allow_html=True)

    if divination_purpose:
        escaped_purpose = html_module.escape(divination_purpose)
        st.markdown(f"""
        <div class="info-badge" style="width:100%;display:block;margin-bottom:16px;">
            <span class="label">📝 占卜事由：</span>{escaped_purpose}
        </div>
        """, unsafe_allow_html=True)

    # 分享按鈕
    st.markdown(f"""
    <div style="margin-bottom:20px;">
        <a href="{share_url}" target="_self" style="
            display:inline-block;padding:6px 16px;
            border:1px solid #d4a017;border-radius:8px;
            color:#d4a017;text-decoration:none;font-size:0.85rem;
            transition:all 0.2s;
        ">🔗 複製分享連結</a>
    </div>
    """, unsafe_allow_html=True)

    # 三欄佈局 — 月課 / 日課 / 時課
    col_m, col_d, col_h = st.columns(3)
    for col, title, lt in [(col_m, "月課", ltext), (col_d, "日課", ltext1), (col_h, "時課", ltext2)]:
        with col:
            st.markdown(f"""<div class="liuren-card">
                <h4>{title}</h4>
                <div style="color:#d4a017;font-size:0.9rem;margin-bottom:8px;">格局：{lt.get("格局")[0]}</div>
            """, unsafe_allow_html=True)

            # 三傳簡覽
            for pass_name, icon in [("初傳", "①"), ("中傳", "②"), ("末傳", "③")]:
                p = lt.get("三傳", {}).get(pass_name, [])
                if p:
                    zhi_c = get_wuxing_color(p[0])
                    st.markdown(
                        f'<div style="margin:4px 0;"><span style="color:#888;">{icon}</span> '
                        f'<span style="color:{zhi_c};font-weight:600;font-size:1.1rem;">{p[0]}</span> '
                        f'<span style="color:#888;font-size:0.8rem;">{p[1]} {p[2]}</span></div>',
                        unsafe_allow_html=True,
                    )

            st.markdown("</div>", unsafe_allow_html=True)

    # 天地盤 SVG（日課）
    st.markdown("### 🌀 天地盤（日課）")
    svg = generate_sky_earth_svg(ltext1.get("地轉天盤", {}), ltext1.get("地轉天將", {}))
    st.markdown(f'<div style="text-align:center;">{svg}</div>', unsafe_allow_html=True)

    # 純文字排盤（可展開）
    with st.expander("📝 原始排盤文字"):
        # 構建完整文字排盤（保留原版格式）
        d1_str = "　　月課　　　　　　　日課　　　　　　　時課\n\n"
        e_str = "　{}　　　　　{}　　　　　{}\n".format("".join(ltext.get("三傳").get("初傳")), "".join(ltext1.get("三傳").get("初傳")), "".join(ltext2.get("三傳").get("初傳")))
        f_str = "　{}　　　　　{}　　　　　{}\n".format("".join(ltext.get("三傳").get("中傳")), "".join(ltext1.get("三傳").get("中傳")), "".join(ltext2.get("三傳").get("中傳")))
        g_str = "　{}　　　　　{}　　　　　{}\n\n".format("".join(ltext.get("三傳").get("末傳")), "".join(ltext1.get("三傳").get("末傳")), "".join(ltext2.get("三傳").get("末傳")))
        h_str = "　{}　　　　　{}　　　　　{}\n".format("".join([ltext.get("四課").get(i)[0][0] for i in ['四課', '三課', '二課', '一課']]), "".join([ltext1.get("四課").get(i)[0][0] for i in ['四課', '三課', '二課', '一課']]), "".join([ltext2.get("四課").get(i)[0][0] for i in ['四課', '三課', '二課', '一課']]))
        i_str = "　{}　　　　　{}　　　　　{}\n\n".format("".join([ltext.get("四課").get(i)[0][1] for i in ['四課', '三課', '二課', '一課']]), "".join([ltext1.get("四課").get(i)[0][1] for i in ['四課', '三課', '二課', '一課']]), "".join([ltext2.get("四課").get(i)[0][1] for i in ['四課', '三課', '二課', '一課']]))
        full_text = chart_text + d1_str + e_str + f_str + g_str + h_str + i_str
        st.code(full_text)

    with st.expander("🔧 原始資料（JSON）"):
        st.json({"月課": ltext, "日課": ltext1, "時課": ltext2})


# ------------------------------------------------------------------
# Tab 2: 三傳四課
# ------------------------------------------------------------------
with tab2:
    st.markdown("## 🎴 三傳四課")

    # 下拉選擇檢視課別
    course_type = st.radio("選擇課別", ["日課", "月課", "時課"], horizontal=True, key="course_selector")
    lt_selected = {"日課": ltext1, "月課": ltext, "時課": ltext2}[course_type]

    # --- 三傳 ---
    st.markdown("### 三傳")
    cols_sc = st.columns(3)
    for idx, (pass_name, icon) in enumerate([("初傳", "🔵"), ("中傳", "🟡"), ("末傳", "🔴")]):
        with cols_sc[idx]:
            pass_data = lt_selected.get("三傳", {}).get(pass_name, ["?", "?", "?", "?"])
            st.markdown(render_sanchuan_card(pass_name, pass_data, icon), unsafe_allow_html=True)

    # 連線動畫
    st.markdown("""
    <div style="text-align:center;margin:8px 0;">
        <span style="color:#d4a017;font-size:0.9rem;">初傳 → 中傳 → 末傳</span>
    </div>
    """, unsafe_allow_html=True)

    # --- 四課 ---
    st.markdown("### 四課")
    cols_sk = st.columns(4)
    for idx, ke_name in enumerate(["一課", "二課", "三課", "四課"]):
        with cols_sk[idx]:
            ke_data = lt_selected.get("四課", {}).get(ke_name, [["??"], "?"])
            ke_general = ke_data[1] if len(ke_data) > 1 else "?"
            st.markdown(render_sike_card(ke_name, ke_data, ke_general), unsafe_allow_html=True)


# ------------------------------------------------------------------
# Tab 3: 天地盤與天將（互動 SVG 圓盤）
# ------------------------------------------------------------------
with tab3:
    st.markdown("## 🌀 天地盤與天將")

    disc_course = st.radio("選擇課別", ["日課", "月課", "時課"], horizontal=True, key="disc_course_selector")
    lt_disc = {"日課": ltext1, "月課": ltext, "時課": ltext2}[disc_course]

    # 互動式 SVG 圓盤
    svg_disc = generate_sky_earth_svg(
        lt_disc.get("地轉天盤", {}),
        lt_disc.get("地轉天將", {}),
        width=520, height=520,
    )

    # 使用 HTML component 以支持互動
    disc_html = f"""
    <div style="display:flex;justify-content:center;align-items:center;padding:20px;">
        {svg_disc}
    </div>
    <div style="text-align:center;margin-top:12px;">
        <span style="color:#3a3020;font-size:0.85rem;">
            <span style="color:#d4a017;">●</span> 外圈：地盤（固定）
            <span style="margin:0 12px;">|</span>
            <span style="color:#d4a017;">●</span> 中圈：天盤（旋轉）
            <span style="margin:0 12px;">|</span>
            <span style="color:#888;">●</span> 內圈：天將
        </span>
    </div>
    """
    st.markdown(disc_html, unsafe_allow_html=True)

    # 詳細表格
    st.markdown("### 📋 天地盤對照表")
    zhi_order = list("子丑寅卯辰巳午未申酉戌亥")
    earth_sky_map = lt_disc.get("地轉天盤", {})
    earth_gen_map = lt_disc.get("地轉天將", {})

    table_rows = ""
    for z in zhi_order:
        sky_z = earth_sky_map.get(z, "?")
        gen = earth_gen_map.get(z, "?")
        fortune = GENERAL_FORTUNE.get(gen, "平")
        f_color = FORTUNE_COLORS.get(fortune, "#888")
        earth_c = get_wuxing_color(z)
        sky_c = get_wuxing_color(sky_z)
        table_rows += f"""
        <tr style="border-bottom:1px solid #2a2520;">
            <td style="padding:8px;color:{earth_c};font-weight:600;font-size:1.1rem;">{z}</td>
            <td style="padding:8px;color:{sky_c};font-weight:600;font-size:1.1rem;">{sky_z}</td>
            <td style="padding:8px;color:{f_color};">{gen}</td>
            <td style="padding:8px;"><span style="color:{f_color};font-size:0.85rem;">{fortune}</span></td>
        </tr>"""

    st.markdown(f"""
    <table style="width:100%;border-collapse:collapse;background:#141210;border-radius:8px;overflow:hidden;">
        <thead>
            <tr style="background:#1e1a14;border-bottom:2px solid #3a3020;">
                <th style="padding:10px;color:#d4a017;text-align:left;">地盤</th>
                <th style="padding:10px;color:#d4a017;text-align:left;">天盤</th>
                <th style="padding:10px;color:#d4a017;text-align:left;">天將</th>
                <th style="padding:10px;color:#d4a017;text-align:left;">吉凶</th>
            </tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
    </table>
    """, unsafe_allow_html=True)


# ------------------------------------------------------------------
# Tab 4: 神煞格局
# ------------------------------------------------------------------
with tab4:
    st.markdown("## ✨ 神煞與格局")

    sha_course = st.radio("選擇課別", ["日課", "月課", "時課"], horizontal=True, key="sha_course_selector")
    lt_sha = {"日課": ltext1, "月課": ltext, "時課": ltext2}[sha_course]

    # 格局
    st.markdown("### 📐 格局")
    geju = lt_sha.get("格局", ["", ""])
    st.markdown(f"""
    <div class="liuren-card">
        <div style="font-size:1.3rem;color:#d4a017;font-family:'Noto Serif SC',serif;font-weight:700;">
            {geju[0]}
        </div>
        <div style="color:#b8b0a0;margin-top:8px;font-size:0.9rem;">
            {geju[1] if len(geju) > 1 else ""}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 天將吉凶一覽
    st.markdown("### 🏷️ 天將吉凶")
    earth_gen_sha = lt_sha.get("地轉天將", {})
    tags_html = ""
    for z in zhi_order:
        gen = earth_gen_sha.get(z, "?")
        fortune = GENERAL_FORTUNE.get(gen, "平")
        tag_class = {
            "大吉": "tag-daji", "吉": "tag-ji", "平": "tag-ping",
            "凶": "tag-xiong", "大凶": "tag-daxiong",
        }.get(fortune, "tag-ping")
        emoji = {"大吉": "🟢", "吉": "🟡", "平": "⚪", "凶": "🔴", "大凶": "🔴"}.get(fortune, "⚪")
        tags_html += f'<span class="shensha-tag {tag_class}" title="{z}宮 - {gen} ({fortune})">{emoji} {gen}({z}) — {fortune}</span>'

    st.markdown(f'<div style="margin:12px 0;">{tags_html}</div>', unsafe_allow_html=True)

    # 四課關係
    st.markdown("### 🔄 四課關係")
    sike_info = lt_sha.get("四課", {})
    for ke_name in ["一課", "二課", "三課", "四課"]:
        ke = sike_info.get(ke_name, [["??"], "?"])
        top = ke[0][0] if ke[0] else "?"
        bottom = ke[0][1] if len(ke[0]) > 1 else "?"
        gen = ke[1] if len(ke) > 1 else "?"
        top_c = get_wuxing_color(top)
        bottom_c = get_wuxing_color(bottom)
        st.markdown(
            f'<span class="info-badge"><span class="label">{ke_name}</span>'
            f'<span style="color:{top_c};font-weight:600;">{top}</span>'
            f'<span style="color:#3a3020;"> / </span>'
            f'<span style="color:{bottom_c};font-weight:600;">{bottom}</span>'
            f' <span style="color:#888;font-size:0.8rem;">({gen})</span></span>',
            unsafe_allow_html=True,
        )

    # 日馬
    st.markdown("### 🐎 日馬")
    st.markdown(f"""
    <div style="margin:8px 0;">
        <span class="info-badge"><span class="label">月課日馬</span>{dhorse1}</span>
        <span class="info-badge"><span class="label">日課日馬</span>{dhorse2}</span>
        <span class="info-badge"><span class="label">時課日馬</span>{dhorse3}</span>
    </div>
    """, unsafe_allow_html=True)


# ------------------------------------------------------------------
# Tab 5: 斷事參考（AI 解讀）
# ------------------------------------------------------------------
with tab5:
    st.markdown("## 🔍 斷事參考")

    if not divination_purpose:
        st.warning("⚠️ 請在左側輸入「占卜事由」，以獲得更精準的 AI 分析。")

    # 課體提示
    st.markdown("### 📖 課體提示")
    geju_day = ltext1.get("格局", ["", ""])
    st.markdown(f"""
    <div class="liuren-card">
        <h4>日課格局：{geju_day[0]}</h4>
        <div style="color:#b8b0a0;line-height:1.8;">
            {geju_day[1] if len(geju_day) > 1 else "（無詳細說明）"}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # AI 分析按鈕
    if st.button("🤖 使用 AI 分析排盤結果", use_container_width=True, type="primary"):
        with st.spinner("AI 正在分析六壬排盤結果，請稍候..."):
            cerebras_api_key = st.secrets.get("CEREBRAS_API_KEY") or os.getenv("CEREBRAS_API_KEY")
            if not cerebras_api_key:
                st.error("CEREBRAS_API_KEY 未設置，請先在 .streamlit/secrets.toml 設置，或設置環境變量 CEREBRAS_API_KEY。")
            else:
                try:
                    client = CerebrasClient(api_key=cerebras_api_key)
                    liuren_prompt = format_liuren_results_for_prompt(
                        chart_text, ltext, ltext1, ltext2,
                        divination_purpose=divination_purpose,
                    )
                    messages = [
                        {"role": "system", "content": st.session_state.system_prompt},
                        {"role": "user", "content": liuren_prompt},
                    ]
                    api_params = {
                        "messages": messages,
                        "model": selected_model,
                        "max_tokens": st.session_state.get("ai_max_tokens", AI_MAX_MAX_TOKENS),
                        "temperature": st.session_state.get("ai_temperature", 0.7),
                    }
                    response = client.get_chat_completion(**api_params)
                    raw_response = response.choices[0].message.content
                    st.markdown(f"""
                    <div class="liuren-card">
                        <h4>🤖 AI 分析結果</h4>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown(raw_response)
                except Exception as e:
                    st.error(f"調用 AI 時發生錯誤：{e}")

    # AI 問答
    st.markdown("---")
    st.markdown("### 💬 AI 六壬問答")

    if "chart_text" not in st.session_state:
        st.info("請先選擇日期時間以生成排盤。")

    chat_container = st.container(height=350)
    with chat_container:
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if user_input := st.chat_input("輸入您的六壬問題...", key="chat_input"):
        st.session_state.chat_messages.append({"role": "user", "content": user_input})

        cerebras_api_key = st.secrets.get("CEREBRAS_API_KEY") or os.getenv("CEREBRAS_API_KEY")
        if not cerebras_api_key:
            err_msg = "CEREBRAS_API_KEY 未設置。"
            st.session_state.chat_messages.append({"role": "assistant", "content": err_msg})
        else:
            chart_context = ""
            if "chart_text" in st.session_state:
                liuren_prompt = format_liuren_results_for_prompt(
                    st.session_state.chart_text,
                    st.session_state.chart_ltext,
                    st.session_state.chart_ltext1,
                    st.session_state.chart_ltext2,
                    divination_purpose=divination_purpose,
                )
                chart_context = f"\n\n以下是當前的六壬排盤數據供參考：\n{liuren_prompt}"

            system_content = st.session_state.get("system_prompt", "") + chart_context

            api_messages = [{"role": "system", "content": system_content}]
            for msg in st.session_state.chat_messages:
                api_messages.append({"role": msg["role"], "content": msg["content"]})

            try:
                client = CerebrasClient(api_key=cerebras_api_key)
                api_params = {
                    "messages": api_messages,
                    "model": st.session_state.get("cerebras_model_selector", CEREBRAS_MODEL_OPTIONS[0]),
                    "max_tokens": st.session_state.get("ai_max_tokens", AI_MAX_MAX_TOKENS),
                    "temperature": st.session_state.get("ai_temperature", 0.7),
                }
                response = client.get_chat_completion(**api_params)
                assistant_reply = response.choices[0].message.content
                st.session_state.chat_messages.append({"role": "assistant", "content": assistant_reply})
            except Exception as e:
                err_msg = f"調用 AI 時發生錯誤：{e}"
                st.session_state.chat_messages.append({"role": "assistant", "content": err_msg})

        st.rerun()

    if st.session_state.chat_messages:
        if st.button("🗑️ 清除對話記錄", key="clear_chat"):
            st.session_state.chat_messages = []
            st.rerun()


# ------------------------------------------------------------------
# Tab 6/7/8: 古籍 / 連結 / 更新（保留原有內容）
# ------------------------------------------------------------------
with tab_guji:
    st.markdown("## 📚 古籍")
    st.markdown(get_file_content_as_string("docs/guji.md"))

with tab_links:
    st.markdown("## 🔗 連結")
    st.markdown(get_file_content_as_string("docs/contact.md"), unsafe_allow_html=True)

with tab_update:
    st.markdown("## 🆕 更新")
    st.markdown(get_file_content_as_string("docs/changelog.md"))
