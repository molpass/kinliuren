"""
堅六壬 — 大六壬排盤 Streamlit App（重構版）
=============================================
古風玄學視覺主題 · 三傳四課視覺化 · AI 問答整合
保留原有 kinliuren 後端邏輯，僅重構前端顯示與互動體驗。
"""
import os, sys, urllib, calendar, json, datetime

# 將 src/ 加入模組搜尋路徑，以便按名稱匯入程式庫模組
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

# ========== 工具函式（保留原始邏輯） ==========

@contextmanager
def st_capture(output_func):
    """擷取 stdout 輸出並即時更新 Streamlit 元件"""
    with StringIO() as stdout, redirect_stdout(stdout):
        old_write = stdout.write
        def new_write(string):
            ret = old_write(string)
            output_func(stdout.getvalue())
            return ret
        stdout.write = new_write
        yield

def get_file_content_as_string(path):
    """從 GitHub 原始檔案 URL 取得 markdown 內容"""
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

def weekday_str(y, m, d):
    """取得中文星期幾"""
    cweekdays = ["星期" + i for i in list("日一二三四五六")]
    dayNumber = calendar.weekday(y, m, d)
    return dict(zip([int(i) for i in list("6012345")], cweekdays)).get(dayNumber)

def day_chin(zhi, wd):
    three_zhi = "申子辰,巳酉丑,寅午戌,亥卯未".split(",")
    head = ["虛畢翼箕奎鬼氐", "房危觜軫斗婁柳", "星心室參角牛胃", "昴張尾壁井亢女"]
    cweekdays = ["星期" + i for i in list("日一二三四五六")]
    ydict = {}
    for i in range(4):
        b = {tuple(list(three_zhi[i])): dict(zip(cweekdays, list(head[i])))}
        ydict.update(b)
    return multi_key_dict_get(ydict, zhi).get(wd)

# ========== 五行顏色映射 ==========

# 地支→五行映射
ZHI_WUXING = {
    '子': '水', '丑': '土', '寅': '木', '卯': '木',
    '辰': '土', '巳': '火', '午': '火', '未': '土',
    '申': '金', '酉': '金', '戌': '土', '亥': '水'
}
# 天干→五行映射
GAN_WUXING = {
    '甲': '木', '乙': '木', '丙': '火', '丁': '火',
    '戊': '土', '己': '土', '庚': '金', '辛': '金',
    '壬': '水', '癸': '水'
}

def wuxing_color(char):
    """根據干支字元返回對應五行顏色"""
    wx = GAN_WUXING.get(char) or ZHI_WUXING.get(char) or ''
    color_map = {
        '木': '#4ade80',  # 青/綠
        '火': '#f87171',  # 紅
        '土': '#fbbf24',  # 黃
        '金': '#e2e8f0',  # 白
        '水': '#60a5fa',  # 藍
    }
    return color_map.get(wx, '#f5f0e8')

def colored_gz(gz_str):
    """為干支字串中的每個字元加上五行顏色 HTML span"""
    parts = []
    for ch in gz_str:
        c = wuxing_color(ch)
        parts.append(f'<span style="color:{c};font-weight:700">{ch}</span>')
    return ''.join(parts)

# ========== 天將吉凶等級 ==========

GENERAL_FORTUNE = {
    '貴': ('大吉', '🟢'), '蛇': ('凶', '🔴'), '雀': ('凶', '🔴'),
    '合': ('吉', '🟡'), '勾': ('平', '⚪'), '龍': ('大吉', '🟢'),
    '空': ('凶', '🔴'), '虎': ('凶', '🔴'), '常': ('吉', '🟡'),
    '玄': ('凶', '🔴'), '陰': ('吉', '🟡'), '后': ('吉', '🟡'),
}

def fortune_badge(general_char):
    """返回天將吉凶彩色標籤 HTML"""
    info = GENERAL_FORTUNE.get(general_char, ('平', '⚪'))
    level, icon = info
    bg_map = {'大吉': '#166534', '吉': '#854d0e', '平': '#374151', '凶': '#991b1b'}
    border_map = {'大吉': '#22c55e', '吉': '#eab308', '平': '#6b7280', '凶': '#ef4444'}
    bg = bg_map.get(level, '#374151')
    border = border_map.get(level, '#6b7280')
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:9999px;'
        f'font-size:0.75rem;background:{bg};border:1px solid {border};color:#fff;'
        f'margin:1px">{icon}{general_char} {level}</span>'
    )

# ========== AI 設定常數 ==========

CEREBRAS_MODEL_OPTIONS = [
    "qwen-3-235b-a22b-instruct-2507",
    "llama-4-scout-17b-16e-instruct",
    "llama3.1-8b",
    "llama-3.3-70b",
    "deepseek-r1-distill-llama-70b"
]
CEREBRAS_MODEL_DESCRIPTIONS = {
    "qwen-3-235b-a22b-instruct-2507": "Cerebras: Fast inference, great for rapid iteration.",
    "llama-4-scout-17b-16e-instruct": "Cerebras: Optimized for guided workflows.",
    "llama3.1-8b": "Cerebras: Light and fast for quick tasks.",
    "llama-3.3-70b": "Cerebras: Most capable for complex reasoning.",
    "deepseek-r1-distill-llama-70b": "DeepSeek distilled model.",
}

SYSTEM_PROMPTS_FILE = "system_prompts.json"
AI_MIN_MAX_TOKENS = 40000
AI_MAX_MAX_TOKENS = 200000

# ========== 系統提示管理 ==========

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
            "selected": "六壬大師"
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
    """將排盤結果格式化為 AI 提示"""
    prompt_lines = [
        "以下是大六壬排盤的計算結果，請根據這些數據提供詳細的分析和解釋：",
        "",
    ]
    if divination_purpose:
        prompt_lines.append(f"【占卜事由】{divination_purpose}")
        prompt_lines.append("")
    prompt_lines.extend([
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
    ])
    return "\n".join(prompt_lines)

# ========== 頁面設定 ==========

st.set_page_config(
    layout="wide",
    page_title="堅六壬 — 大六壬排盤",
    page_icon="icon.jpg"
)

# ========== 全域自訂 CSS（古風玄學主題） ==========

st.markdown("""
<style>
/* ---------- Google Fonts 載入 ---------- */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700;900&family=Noto+Serif+SC:wght@400;600;700;900&family=Ma+Shan+Zheng&display=swap');

/* ---------- 全域基礎 ---------- */
html, body, [data-testid="stAppViewContainer"], .main, .block-container {
    font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif !important;
    line-height: 1.8;
}

/* ---------- 宣紙水墨背景 ---------- */
[data-testid="stAppViewContainer"]::before {
    content: "";
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: radial-gradient(ellipse at 20% 50%, rgba(212,160,23,0.04) 0%, transparent 70%),
                radial-gradient(ellipse at 80% 20%, rgba(200,16,46,0.03) 0%, transparent 60%),
                radial-gradient(ellipse at 50% 80%, rgba(212,160,23,0.02) 0%, transparent 50%);
    pointer-events: none;
    z-index: 0;
}

/* ---------- 標題篆書風格 ---------- */
h1, h2, h3 {
    font-family: 'Ma Shan Zheng', 'Noto Serif SC', serif !important;
    color: #d4a017 !important;
    letter-spacing: 0.15em;
}
h1 { font-size: 2.5rem !important; text-shadow: 0 0 20px rgba(212,160,23,0.3); }

/* ---------- 側邊欄 ---------- */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a0a0a 0%, #141414 100%) !important;
    border-right: 1px solid rgba(212,160,23,0.2);
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    font-family: 'Ma Shan Zheng', serif !important;
    color: #d4a017 !important;
}

/* ---------- 卡片基礎樣式 ---------- */
.gufeng-card {
    background: linear-gradient(145deg, rgba(26,26,42,0.95), rgba(15,15,15,0.98));
    border: 1px solid rgba(212,160,23,0.25);
    border-radius: 12px;
    padding: 1.2rem;
    margin: 0.5rem 0;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5), inset 0 1px 0 rgba(212,160,23,0.1);
    transition: transform 0.2s, box-shadow 0.2s;
}
.gufeng-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(212,160,23,0.15), inset 0 1px 0 rgba(212,160,23,0.2);
}

/* ---------- 三傳卡片與連線動畫 ---------- */
.sanchuan-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0;
    position: relative;
}
.sanchuan-card {
    background: linear-gradient(145deg, rgba(26,26,42,0.95), rgba(15,15,15,0.98));
    border: 1px solid rgba(212,160,23,0.35);
    border-radius: 10px;
    padding: 0.8rem 1.2rem;
    text-align: center;
    width: 100%;
    max-width: 240px;
    position: relative;
    z-index: 1;
}
.sanchuan-card .sc-label {
    font-family: 'Ma Shan Zheng', serif;
    color: #d4a017;
    font-size: 0.85rem;
    margin-bottom: 4px;
}
.sanchuan-card .sc-zhi {
    font-size: 1.6rem;
    font-weight: 900;
    letter-spacing: 0.1em;
}
.sanchuan-card .sc-info {
    font-size: 0.8rem;
    color: #a0a0a0;
    margin-top: 4px;
}
.sanchuan-connector {
    width: 2px;
    height: 28px;
    background: linear-gradient(180deg, #d4a017, rgba(212,160,23,0.2));
    position: relative;
    z-index: 0;
    animation: flowDown 2s ease-in-out infinite;
}
@keyframes flowDown {
    0%, 100% { opacity: 0.4; }
    50% { opacity: 1; }
}

/* ---------- 四課卡片 ---------- */
.sike-card {
    background: linear-gradient(145deg, rgba(26,26,42,0.95), rgba(15,15,15,0.98));
    border: 1px solid rgba(212,160,23,0.3);
    border-radius: 10px;
    padding: 1rem;
    text-align: center;
    min-width: 80px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.4);
}
.sike-card .sk-label {
    font-family: 'Ma Shan Zheng', serif;
    color: #d4a017;
    font-size: 0.85rem;
    margin-bottom: 6px;
}
.sike-card .sk-top, .sike-card .sk-bottom {
    font-size: 1.3rem;
    font-weight: 700;
    letter-spacing: 0.05em;
}
.sike-card .sk-general {
    font-size: 0.8rem;
    color: #a0a0a0;
    margin-top: 4px;
}
.sike-card .sk-divider {
    height: 1px;
    background: rgba(212,160,23,0.3);
    margin: 6px 0;
}

/* ---------- 天地盤格子 ---------- */
.tianpan-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 2px;
    max-width: 400px;
    margin: 0 auto;
}
.tianpan-cell {
    background: rgba(20,20,35,0.9);
    border: 1px solid rgba(212,160,23,0.2);
    padding: 6px 4px;
    text-align: center;
    font-size: 0.9rem;
}
.tianpan-cell .tp-label {
    font-size: 0.65rem;
    color: #888;
}

/* ---------- info-bar ---------- */
.info-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    padding: 12px 16px;
    background: rgba(20,20,35,0.8);
    border: 1px solid rgba(212,160,23,0.2);
    border-radius: 10px;
    margin-bottom: 1rem;
    align-items: center;
}
.info-bar .info-item {
    font-size: 0.95rem;
    color: #f5f0e8;
}
.info-bar .info-label {
    color: #d4a017;
    font-weight: 600;
    margin-right: 4px;
}

/* ---------- 歷史記錄 ---------- */
.history-item {
    background: rgba(20,20,35,0.7);
    border: 1px solid rgba(212,160,23,0.15);
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 8px;
    cursor: pointer;
    transition: background 0.2s;
}
.history-item:hover {
    background: rgba(30,30,50,0.9);
}

/* ---------- 手機適配 ---------- */
@media (max-width: 768px) {
    .block-container { padding: 0.5rem 0.5rem !important; }
    h1 { font-size: 1.6rem !important; }
    .sike-card { min-width: 60px; padding: 0.6rem; }
    .sike-card .sk-top, .sike-card .sk-bottom { font-size: 1rem; }
    .sanchuan-card { max-width: 180px; padding: 0.6rem 0.8rem; }
    .sanchuan-card .sc-zhi { font-size: 1.2rem; }
    .info-bar { flex-direction: column; gap: 6px; }
    .tianpan-grid { max-width: 100%; }
}

/* ---------- 聊天區域 ---------- */
[data-testid="stChatMessage"] {
    border: 1px solid rgba(212,160,23,0.1) !important;
    border-radius: 8px !important;
    margin-bottom: 8px !important;
}

/* ---------- Expander ---------- */
[data-testid="stExpander"] {
    border: 1px solid rgba(212,160,23,0.2) !important;
    border-radius: 8px !important;
}

/* ---------- 按鈕 ---------- */
.stButton>button {
    border: 1px solid rgba(212,160,23,0.4) !important;
    transition: all 0.2s !important;
}
.stButton>button:hover {
    border-color: #d4a017 !important;
    box-shadow: 0 0 15px rgba(212,160,23,0.2) !important;
}

/* ---------- 分隔線 ---------- */
hr {
    border-color: rgba(212,160,23,0.2) !important;
}
</style>
""", unsafe_allow_html=True)

# ========== 讀取 URL query params 以支援分享連結 ==========

qp = st.query_params
qp_year = int(qp.get("y", 0))
qp_month = int(qp.get("m", 0))
qp_day = int(qp.get("d", 0))
qp_hour = int(qp.get("h", -1))
qp_minute = int(qp.get("mi", -1))
qp_purpose = qp.get("purpose", "")

# ========== 側邊欄 ==========

with st.sidebar:
    st.markdown("## 🔮 起課設定")

    # 預設使用北京時間
    default_datetime = pdlm.now(tz='Asia/Shanghai')

    # 「立即起課」按鈕 — 使用當前北京時間
    if st.button("⚡ 立即起課（北京時間）", type="primary", use_container_width=True):
        now = pdlm.now(tz='Asia/Shanghai')
        st.session_state['dt_date'] = now.date()
        st.session_state['dt_time'] = now.time()
        st.rerun()

    st.markdown("---")
    st.markdown("### 📅 日期時間")

    # 若有 query params 則使用
    init_date = (datetime.date(qp_year, qp_month, qp_day)
                 if qp_year and qp_month and qp_day
                 else default_datetime.date())
    init_time = (datetime.time(qp_hour, qp_minute)
                 if qp_hour >= 0 and qp_minute >= 0
                 else default_datetime.time())

    selected_date = st.date_input(
        "日期", value=init_date,
        min_value=datetime.date(1900, 1, 1),
        max_value=datetime.date(2100, 12, 31),
        key='dt_date', help="點擊選擇日期"
    )
    selected_time = st.time_input(
        "時間", value=init_time,
        step=datetime.timedelta(minutes=1),
        key='dt_time', help="點擊選擇時間"
    )

    sel_y = selected_date.year
    sel_m = selected_date.month
    sel_d = selected_date.day
    sel_h = selected_time.hour
    sel_mi = selected_time.minute

    st.caption(f"已選擇：{sel_y}年{sel_m}月{sel_d}日 {sel_h:02d}:{sel_mi:02d}　⏱ 時區 Asia/Shanghai")

    st.markdown("---")
    st.markdown("### 📝 占卜事由")
    divination_purpose = st.text_area(
        "請描述您的占卜事由（必填）",
        value=qp_purpose,
        height=100,
        placeholder="例：問事業前途、問感情走向、問健康狀況…",
        key="divination_purpose"
    )

    st.markdown("---")
    st.markdown("### 🤖 AI 設置")

    selected_model = st.selectbox(
        "AI 模型", options=CEREBRAS_MODEL_OPTIONS, index=0,
        key="cerebras_model_selector",
        help="\n".join(f"• {k}: {v}" for k, v in CEREBRAS_MODEL_DESCRIPTIONS.items())
    )

    system_prompts_data = load_system_prompts()
    prompts_list = system_prompts_data.get("prompts", [])
    prompt_names = [prompt["name"] for prompt in prompts_list]
    selected_prompt = system_prompts_data.get("selected")

    if prompt_names:
        selected_index = 0
        if selected_prompt in prompt_names:
            selected_index = prompt_names.index(selected_prompt)

        selected_name = st.selectbox(
            "選擇系統提示", options=prompt_names, index=selected_index,
            key="system_prompt_selector",
            help="選擇用於AI模型的系統提示"
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

        new_content = st.text_area(
            "編輯系統提示", value=st.session_state.system_prompt,
            height=150, placeholder="範例：你是一位大六壬專家…",
            key="system_prompt_editor"
        )
        st.session_state.system_prompt = new_content

        col_u, col_d = st.columns(2)
        with col_u:
            if st.button("💾 更新提示", key="update_prompt_button"):
                for prompt in prompts_list:
                    if prompt["name"] == selected_name:
                        prompt["content"] = new_content
                        break
                if save_system_prompts(system_prompts_data):
                    st.toast(f"✅ 已更新系統提示 '{selected_name}'！")
        with col_d:
            if st.button("❌ 刪除提示", key="delete_prompt_button",
                         disabled=len(prompts_list) <= 1):
                prompts_list = [p for p in prompts_list if p["name"] != selected_name]
                system_prompts_data["prompts"] = prompts_list
                if selected_name == selected_prompt and prompts_list:
                    system_prompts_data["selected"] = prompts_list[0]["name"]
                if save_system_prompts(system_prompts_data):
                    st.toast(f"✅ 已刪除系統提示 '{selected_name}'！")
                    st.rerun()

    if "form_key_suffix" not in st.session_state:
        st.session_state.form_key_suffix = 0
    name_key = f"new_prompt_name_{st.session_state.form_key_suffix}"
    content_key = f"new_prompt_content_{st.session_state.form_key_suffix}"

    with st.expander("➕ 新增提示", expanded=False):
        new_prompt_name = st.text_input("新提示名稱", key=name_key)
        new_prompt_content = st.text_area(
            "新提示內容", height=100, placeholder="輸入AI分析指令…", key=content_key
        )
        if st.button("➕ 新增提示", key="add_prompt_button",
                     disabled=not new_prompt_name or not new_prompt_content):
            if new_prompt_name in prompt_names:
                st.error(f"提示名稱 '{new_prompt_name}' 已存在。")
            else:
                prompts_list.append({"name": new_prompt_name, "content": new_prompt_content})
                system_prompts_data["prompts"] = prompts_list
                if save_system_prompts(system_prompts_data):
                    st.session_state.form_key_suffix += 1
                    st.toast(f"✅ 已新增系統提示 '{new_prompt_name}'！")
                    st.rerun()

    if st.toggle("🔧 高級設置", key="advanced_settings_toggle"):
        st.session_state.ai_max_tokens = st.slider(
            "最大生成 Tokens",
            AI_MIN_MAX_TOKENS, AI_MAX_MAX_TOKENS,
            st.session_state.get("ai_max_tokens", AI_MAX_MAX_TOKENS),
            key="ai_max_tokens_slider", help="控制AI回應的最大長度"
        )
        st.session_state.ai_temperature = st.slider(
            "溫度 (專注 vs. 創意)", 0.0, 1.5,
            st.session_state.get("ai_temperature", 0.7),
            step=0.05, key="ai_temperature_slider",
            help="較低值 (如 0.2) 更確定性；較高值 (如 0.8) 更隨機"
        )

    # 歷史記錄區
    st.markdown("---")
    st.markdown("### 📜 歷史記錄")
    if "history" not in st.session_state:
        st.session_state.history = []
    if st.session_state.history:
        for idx, rec in enumerate(reversed(st.session_state.history[-10:])):
            if st.button(f"🕐 {rec['time']} | {rec['purpose'][:12]}…" if len(rec.get('purpose', '')) > 12
                         else f"🕐 {rec['time']} | {rec.get('purpose', '無事由')}",
                         key=f"hist_{idx}"):
                st.session_state['dt_date'] = datetime.date(rec['y'], rec['m'], rec['d'])
                st.session_state['dt_time'] = datetime.time(rec['h'], rec['mi'])
                st.session_state['divination_purpose'] = rec.get('purpose', '')
                st.rerun()
    else:
        st.caption("尚無歷史記錄")

# ========== 主頁面標題 ==========

st.markdown(
    '<h1 style="text-align:center;margin-bottom:0">堅六壬</h1>'
    '<p style="text-align:center;color:#a0a0a0;font-size:0.95rem;margin-top:0">'
    '大六壬排盤系統 · 古法今用</p>',
    unsafe_allow_html=True
)

# ========== 頁籤 ==========

pan, example_tab, guji, links, update = st.tabs(
    ['🧮 排盤', '📜 案例', '📚 古籍', '🔗 連結', '🆕 更新']
)

# ---------- 古籍 / 連結 / 更新（保留原始內容） ----------
with guji:
    st.header('古籍')
    st.markdown(get_file_content_as_string("docs/guji.md"))

with links:
    st.header('連結')
    st.markdown(get_file_content_as_string("docs/contact.md"), unsafe_allow_html=True)

with update:
    st.header('更新')
    st.markdown(get_file_content_as_string("docs/changelog.md"))

# ========== 排盤主體 ==========

with pan:
    # --- 計算六壬排盤（保留原始後端邏輯） ---
    cm = jieqi.lunar_date_d(sel_y, sel_m, sel_d).get("農曆月")
    qgz = gangzhi(sel_y, sel_m, sel_d, sel_h, sel_mi)
    current_jq = jq(sel_y, sel_m, sel_d, sel_h, sel_mi)
    liuren_month = kinliuren.Liuren(current_jq, cm, qgz[1], qgz[2]).result_d(0)
    liuren_day = kinliuren.Liuren(current_jq, cm, qgz[2], qgz[3]).result(0)
    liuren_hour = kinliuren.Liuren(current_jq, cm, qgz[3], qgz[4]).result_m(0)
    dhorse1 = liuren_month.get("日馬")
    dhorse2 = liuren_day.get("日馬")
    dhorse3 = liuren_hour.get("日馬")
    ltext = liuren_month
    ltext1 = liuren_day
    ltext2 = liuren_hour
    dchin = day_chin(qgz[2][1], weekday_str(sel_y, sel_m, sel_d))
    zhi_list = list("子丑寅卯辰巳午未申酉戌亥")
    zdict = dict(zip(zhi_list, range(1, 13)))
    chin_list = list('角亢氐房心尾箕斗牛女虛危室壁奎婁胃昴畢觜參井鬼柳星張翼軫')

    # 保留原文字版排盤以供 AI 讀取
    txt_a = f"日期︰{sel_y}年{sel_m}月{sel_d}日{sel_h}時{sel_mi}分\n"
    txt_b = f"格局︰{ltext.get('格局')[0]}\n"
    txt_c = f"節氣︰{current_jq}\n"
    txt_d = f"干支︰{qgz[0]}年 {qgz[1]}月 {qgz[2]}日 {qgz[3]}時 {qgz[4]}分\n"
    txt_d2 = f"日馬︰{dhorse1}(月) {dhorse2}(日) {dhorse3}(時)\n\n"
    txt_d1 = "　　月課　　　　　　　日課　　　　　　　時課\n\n"
    txt_e = "　{}　　　　　{}　　　　　{}\n".format("".join(ltext.get("三傳").get("初傳")), "".join(ltext1.get("三傳").get("初傳")), "".join(ltext2.get("三傳").get("初傳")))
    txt_f = "　{}　　　　　{}　　　　　{}\n".format("".join(ltext.get("三傳").get("中傳")), "".join(ltext1.get("三傳").get("中傳")), "".join(ltext2.get("三傳").get("中傳")))
    txt_g = "　{}　　　　　{}　　　　　{}\n\n".format("".join(ltext.get("三傳").get("末傳")), "".join(ltext1.get("三傳").get("末傳")), "".join(ltext2.get("三傳").get("末傳")))
    txt_h = "　{}　　　　　{}　　　　　{}\n".format(
        "".join([ltext.get("四課").get(i)[0][0] for i in ['四課', '三課', '二課', '一課']]),
        "".join([ltext1.get("四課").get(i)[0][0] for i in ['四課', '三課', '二課', '一課']]),
        "".join([ltext2.get("四課").get(i)[0][0] for i in ['四課', '三課', '二課', '一課']])
    )
    txt_i = "　{}　　　　　{}　　　　　{}\n\n".format(
        "".join([ltext.get("四課").get(i)[0][1] for i in ['四課', '三課', '二課', '一課']]),
        "".join([ltext1.get("四課").get(i)[0][1] for i in ['四課', '三課', '二課', '一課']]),
        "".join([ltext2.get("四課").get(i)[0][1] for i in ['四課', '三課', '二課', '一課']])
    )
    txt_j = "　{}　　　　　{}　　　　　{}\n".format(
        "".join([ltext.get("地轉天將").get(i) for i in list("巳午未申")]),
        "".join([ltext1.get("地轉天將").get(i) for i in list("巳午未申")]),
        "".join([ltext2.get("地轉天將").get(i) for i in list("巳午未申")])
    )
    txt_k = "　{}　　　　　{}　　　　　{}\n".format(
        "".join([ltext.get("地轉天盤").get(i) for i in list("巳午未申")]),
        "".join([ltext1.get("地轉天盤").get(i) for i in list("巳午未申")]),
        "".join([ltext2.get("地轉天盤").get(i) for i in list("巳午未申")])
    )
    txt_l = "{}{}　　{}{}　　　{}{}　　{}{}　　　{}{}　　{}{}\n".format(
        ltext.get("地轉天將").get("辰"), ltext.get("地轉天盤").get("辰"),
        ltext.get("地轉天盤").get("酉"), ltext.get("地轉天將").get("酉"),
        ltext1.get("地轉天將").get("辰"), ltext1.get("地轉天盤").get("辰"),
        ltext1.get("地轉天盤").get("酉"), ltext1.get("地轉天將").get("酉"),
        ltext2.get("地轉天將").get("辰"), ltext2.get("地轉天盤").get("辰"),
        ltext2.get("地轉天盤").get("酉"), ltext2.get("地轉天將").get("酉")
    )
    txt_m = "{}{}　　{}{}　　　{}{}　　{}{}　　　{}{}　　{}{}\n".format(
        ltext.get("地轉天將").get("卯"), ltext.get("地轉天盤").get("卯"),
        ltext.get("地轉天盤").get("戌"), ltext.get("地轉天將").get("戌"),
        ltext1.get("地轉天將").get("卯"), ltext1.get("地轉天盤").get("卯"),
        ltext1.get("地轉天盤").get("戌"), ltext1.get("地轉天將").get("戌"),
        ltext2.get("地轉天將").get("卯"), ltext2.get("地轉天盤").get("卯"),
        ltext2.get("地轉天盤").get("戌"), ltext2.get("地轉天將").get("戌")
    )
    txt_n = "　{}　　　　　{}　　　　　{}\n".format(
        "".join([ltext.get("地轉天盤").get(i) for i in list("寅丑子亥")]),
        "".join([ltext1.get("地轉天盤").get(i) for i in list("寅丑子亥")]),
        "".join([ltext2.get("地轉天盤").get(i) for i in list("寅丑子亥")])
    )
    txt_o = "　{}　　　　　{}　　　　　{}\n\n\n".format(
        "".join([ltext.get("地轉天將").get(i) for i in list("寅丑子亥")]),
        "".join([ltext1.get("地轉天將").get(i) for i in list("寅丑子亥")]),
        "".join([ltext2.get("地轉天將").get(i) for i in list("寅丑子亥")])
    )

    chart_text = txt_a + txt_b + txt_c + txt_d + txt_d2 + txt_d1 + txt_e + txt_f + txt_g + txt_h + txt_i + txt_j + txt_k + txt_l + txt_m + txt_n + txt_o

    # 儲存排盤至 session state
    st.session_state.chart_text = chart_text
    st.session_state.chart_ltext = ltext
    st.session_state.chart_ltext1 = ltext1
    st.session_state.chart_ltext2 = ltext2

    # 保存歷史記錄
    hist_key = f"{sel_y}-{sel_m}-{sel_d}-{sel_h}-{sel_mi}"
    if "history" not in st.session_state:
        st.session_state.history = []
    existing_keys = [r.get('key') for r in st.session_state.history]
    if hist_key not in existing_keys:
        st.session_state.history.append({
            'key': hist_key,
            'time': f"{sel_y}/{sel_m}/{sel_d} {sel_h:02d}:{sel_mi:02d}",
            'y': sel_y, 'm': sel_m, 'd': sel_d, 'h': sel_h, 'mi': sel_mi,
            'purpose': divination_purpose
        })
        # 最多保留 20 條
        if len(st.session_state.history) > 20:
            st.session_state.history = st.session_state.history[-20:]

    # ===== 資訊條 =====
    st.markdown(f"""
    <div class="info-bar">
        <span class="info-item"><span class="info-label">日期</span>{sel_y}年{sel_m}月{sel_d}日 {sel_h:02d}:{sel_mi:02d}</span>
        <span class="info-item"><span class="info-label">節氣</span>{current_jq}</span>
        <span class="info-item"><span class="info-label">農曆</span>{cm}</span>
        <span class="info-item"><span class="info-label">干支</span>{colored_gz(qgz[0])}年 {colored_gz(qgz[1])}月 {colored_gz(qgz[2])}日 {colored_gz(qgz[3])}時 {colored_gz(qgz[4])}分</span>
        <span class="info-item"><span class="info-label">格局</span>{ltext.get("格局")[0]}</span>
        <span class="info-item"><span class="info-label">日馬</span>{dhorse1}(月) {dhorse2}(日) {dhorse3}(時)</span>
    </div>
    """, unsafe_allow_html=True)

    # 占卜事由顯示
    if divination_purpose:
        st.markdown(f"""
        <div class="gufeng-card" style="border-color:rgba(200,16,46,0.4)">
            <span style="color:#c8102e;font-weight:700;font-family:'Ma Shan Zheng',serif">📝 占卜事由：</span>
            <span style="color:#f5f0e8">{divination_purpose}</span>
        </div>
        """, unsafe_allow_html=True)

    # ===== 分享連結 =====
    share_params = f"?y={sel_y}&m={sel_m}&d={sel_d}&h={sel_h}&mi={sel_mi}"
    if divination_purpose:
        import urllib.parse
        share_params += f"&purpose={urllib.parse.quote(divination_purpose)}"
    share_url = f"https://kinliuren.streamlit.app/{share_params}"

    col_share, col_dl = st.columns([1, 1])
    with col_share:
        st.code(share_url, language=None)
    with col_dl:
        # PNG 下載：使用純文字版排盤作為可下載檔案
        st.download_button(
            "📥 下載排盤文字",
            data=chart_text,
            file_name=f"liuren_{sel_y}{sel_m:02d}{sel_d:02d}_{sel_h:02d}{sel_mi:02d}.txt",
            mime="text/plain",
            use_container_width=True
        )

    # ========== 三課排盤視覺化 ==========
    def render_sanchuan(data, label):
        """渲染三傳垂直卡片"""
        html_parts = [f'<div class="sanchuan-wrapper">']
        for idx, key in enumerate(["初傳", "中傳", "末傳"]):
            vals = data.get("三傳", {}).get(key, [])
            zhi_char = vals[0] if len(vals) > 0 else "?"
            general = vals[1] if len(vals) > 1 else ""
            relation = vals[2] if len(vals) > 2 else ""
            kong = vals[3] if len(vals) > 3 else ""
            kong_display = f' <span style="color:#ef4444;font-size:0.75rem">空</span>' if kong else ''
            html_parts.append(f'''
            <div class="sanchuan-card">
                <div class="sc-label">{key}</div>
                <div class="sc-zhi">{colored_gz(zhi_char)}{kong_display}</div>
                <div class="sc-info">{fortune_badge(general)} {relation}</div>
            </div>
            ''')
            if idx < 2:
                html_parts.append('<div class="sanchuan-connector"></div>')
        html_parts.append('</div>')
        return ''.join(html_parts)

    def render_sike(data, label):
        """渲染四課橫排卡片"""
        html_parts = ['<div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap">']
        for key in ['一課', '二課', '三課', '四課']:
            vals = data.get("四課", {}).get(key, [])
            top = vals[0][0] if len(vals) > 0 and len(vals[0]) > 0 else "?"
            bottom = vals[0][1] if len(vals) > 0 and len(vals[0]) > 1 else "?"
            general = vals[1] if len(vals) > 1 else ""
            html_parts.append(f'''
            <div class="sike-card">
                <div class="sk-label">{key}</div>
                <div class="sk-top">{colored_gz(top)}</div>
                <div class="sk-divider"></div>
                <div class="sk-bottom">{colored_gz(bottom)}</div>
                <div class="sk-general">{fortune_badge(general)}</div>
            </div>
            ''')
        html_parts.append('</div>')
        return ''.join(html_parts)

    def render_tianpan(data):
        """渲染天地盤九宮格"""
        sky_earth = data.get("地轉天盤", {})
        generals = data.get("地轉天將", {})
        positions = list("巳午未申") + ["辰", "酉"] + list("卯寅丑子亥戌")
        # 九宮格佈局：巳午未申 / 辰__酉 / 卯__戌 / 寅丑子亥
        top_row = list("巳午未申")
        mid1_l, mid1_r = "辰", "酉"
        mid2_l, mid2_r = "卯", "戌"
        bot_row = list("寅丑子亥")

        html = '<div class="tianpan-grid">'
        # 上排
        for z in top_row:
            s = sky_earth.get(z, '?')
            g = generals.get(z, '?')
            html += f'<div class="tianpan-cell"><div class="tp-label">{z}</div><div>{colored_gz(s)}</div><div style="font-size:0.75rem">{fortune_badge(g)}</div></div>'
        # 中排1
        z = mid1_l
        s = sky_earth.get(z, '?'); g = generals.get(z, '?')
        html += f'<div class="tianpan-cell"><div class="tp-label">{z}</div><div>{colored_gz(s)}</div><div style="font-size:0.75rem">{fortune_badge(g)}</div></div>'
        html += '<div class="tianpan-cell" style="grid-column:span 2;background:rgba(212,160,23,0.05);display:flex;align-items:center;justify-content:center;font-family:Ma Shan Zheng,serif;color:#d4a017;font-size:1.1rem">天地盤</div>'
        z = mid1_r
        s = sky_earth.get(z, '?'); g = generals.get(z, '?')
        html += f'<div class="tianpan-cell"><div class="tp-label">{z}</div><div>{colored_gz(s)}</div><div style="font-size:0.75rem">{fortune_badge(g)}</div></div>'
        # 中排2
        z = mid2_l
        s = sky_earth.get(z, '?'); g = generals.get(z, '?')
        html += f'<div class="tianpan-cell"><div class="tp-label">{z}</div><div>{colored_gz(s)}</div><div style="font-size:0.75rem">{fortune_badge(g)}</div></div>'
        html += '<div class="tianpan-cell" style="grid-column:span 2;background:transparent"></div>'
        z = mid2_r
        s = sky_earth.get(z, '?'); g = generals.get(z, '?')
        html += f'<div class="tianpan-cell"><div class="tp-label">{z}</div><div>{colored_gz(s)}</div><div style="font-size:0.75rem">{fortune_badge(g)}</div></div>'
        # 下排
        for z in bot_row:
            s = sky_earth.get(z, '?')
            g = generals.get(z, '?')
            html += f'<div class="tianpan-cell"><div class="tp-label">{z}</div><div>{colored_gz(s)}</div><div style="font-size:0.75rem">{fortune_badge(g)}</div></div>'
        html += '</div>'
        return html

    # --- 三課並排顯示 ---
    st.markdown("### 三傳")
    col_mc, col_dc, col_hc = st.columns(3)
    with col_mc:
        st.markdown('<p style="text-align:center;color:#d4a017;font-family:Ma Shan Zheng,serif;font-size:1.2rem">月課</p>', unsafe_allow_html=True)
        st.markdown(render_sanchuan(ltext, "月課"), unsafe_allow_html=True)
    with col_dc:
        st.markdown('<p style="text-align:center;color:#d4a017;font-family:Ma Shan Zheng,serif;font-size:1.2rem">日課</p>', unsafe_allow_html=True)
        st.markdown(render_sanchuan(ltext1, "日課"), unsafe_allow_html=True)
    with col_hc:
        st.markdown('<p style="text-align:center;color:#d4a017;font-family:Ma Shan Zheng,serif;font-size:1.2rem">時課</p>', unsafe_allow_html=True)
        st.markdown(render_sanchuan(ltext2, "時課"), unsafe_allow_html=True)

    # --- 四課 ---
    st.markdown("### 四課")
    col_mc2, col_dc2, col_hc2 = st.columns(3)
    with col_mc2:
        st.markdown('<p style="text-align:center;color:#d4a017;font-family:Ma Shan Zheng,serif;font-size:1.1rem">月課</p>', unsafe_allow_html=True)
        st.markdown(render_sike(ltext, "月課"), unsafe_allow_html=True)
    with col_dc2:
        st.markdown('<p style="text-align:center;color:#d4a017;font-family:Ma Shan Zheng,serif;font-size:1.1rem">日課</p>', unsafe_allow_html=True)
        st.markdown(render_sike(ltext1, "日課"), unsafe_allow_html=True)
    with col_hc2:
        st.markdown('<p style="text-align:center;color:#d4a017;font-family:Ma Shan Zheng,serif;font-size:1.1rem">時課</p>', unsafe_allow_html=True)
        st.markdown(render_sike(ltext2, "時課"), unsafe_allow_html=True)

    # --- 天地盤 ---
    st.markdown("### 天地盤")
    col_tp1, col_tp2, col_tp3 = st.columns(3)
    with col_tp1:
        st.markdown('<p style="text-align:center;color:#d4a017;font-family:Ma Shan Zheng,serif;font-size:1.1rem">月課</p>', unsafe_allow_html=True)
        st.markdown(render_tianpan(ltext), unsafe_allow_html=True)
    with col_tp2:
        st.markdown('<p style="text-align:center;color:#d4a017;font-family:Ma Shan Zheng,serif;font-size:1.1rem">日課</p>', unsafe_allow_html=True)
        st.markdown(render_tianpan(ltext1), unsafe_allow_html=True)
    with col_tp3:
        st.markdown('<p style="text-align:center;color:#d4a017;font-family:Ma Shan Zheng,serif;font-size:1.1rem">時課</p>', unsafe_allow_html=True)
        st.markdown(render_tianpan(ltext2), unsafe_allow_html=True)

    # --- 天將吉凶一覽 ---
    st.markdown("### 天將吉凶")
    all_generals = set()
    for data in [ltext, ltext1, ltext2]:
        for v in data.get("地轉天將", {}).values():
            all_generals.add(v)
    badges = ' '.join(fortune_badge(g) for g in sorted(all_generals, key=lambda x: list("貴蛇雀合勾龍空虎常玄陰后").index(x) if x in "貴蛇雀合勾龍空虎常玄陰后" else 99))
    st.markdown(f'<div class="gufeng-card">{badges}</div>', unsafe_allow_html=True)

    # --- 原始文字排盤（可收合） ---
    with st.expander("📜 文字排盤（原始格式）"):
        st.code(chart_text)

    with st.expander("🔧 原始數據"):
        st.write(str(ltext))

    # ===== AI 分析 =====
    if st.button("🔍 使用AI分析排盤結果", key="analyze_with_ai", type="primary", use_container_width=True):
        if not divination_purpose:
            st.warning("⚠️ 請先在側邊欄填寫「占卜事由」，以便 AI 提供更精準的分析。")
        else:
            with st.spinner("AI正在分析六壬排盤結果…"):
                cerebras_api_key = st.secrets.get("CEREBRAS_API_KEY") or os.getenv("CEREBRAS_API_KEY")
                if not cerebras_api_key:
                    st.error("CEREBRAS_API_KEY 未設置，請先在 .streamlit/secrets.toml 設置，或設置環境變量 CEREBRAS_API_KEY。")
                else:
                    try:
                        client = CerebrasClient(api_key=cerebras_api_key)
                        liuren_prompt = format_liuren_results_for_prompt(
                            chart_text, ltext, ltext1, ltext2, divination_purpose
                        )
                        messages = [
                            {"role": "system", "content": st.session_state.system_prompt},
                            {"role": "user", "content": liuren_prompt}
                        ]
                        api_params = {
                            "messages": messages,
                            "model": selected_model,
                            "max_tokens": st.session_state.get("ai_max_tokens", AI_MAX_MAX_TOKENS),
                            "temperature": st.session_state.get("ai_temperature", 0.7)
                        }
                        response = client.get_chat_completion(**api_params)
                        raw_response = response.choices[0].message.content
                        with st.expander("AI分析結果", expanded=True):
                            st.markdown(raw_response)
                    except Exception as e:
                        st.error(f"調用AI時發生錯誤：{e}")

# ========== 底部 AI 聊天區（固定） ==========

st.markdown("---")
st.markdown(
    '<h2 style="text-align:center">💬 AI 六壬問答</h2>',
    unsafe_allow_html=True
)

# 初始化聊天歷史
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# 顯示聊天歷史
chat_container = st.container(height=400)
with chat_container:
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# 聊天輸入
if user_input := st.chat_input("輸入您的六壬問題…", key="chat_input"):
    st.session_state.chat_messages.append({"role": "user", "content": user_input})
    with chat_container:
        with st.chat_message("user"):
            st.markdown(user_input)

    cerebras_api_key = st.secrets.get("CEREBRAS_API_KEY") or os.getenv("CEREBRAS_API_KEY")
    if not cerebras_api_key:
        err_msg = "CEREBRAS_API_KEY 未設置，請先在 .streamlit/secrets.toml 設置，或設置環境變量 CEREBRAS_API_KEY。"
        st.session_state.chat_messages.append({"role": "assistant", "content": err_msg})
        with chat_container:
            with st.chat_message("assistant"):
                st.markdown(err_msg)
    else:
        # 建構帶有排盤上下文的系統提示
        chart_context = ""
        if "chart_text" in st.session_state:
            purpose = st.session_state.get("divination_purpose", "")
            liuren_prompt = format_liuren_results_for_prompt(
                st.session_state.chart_text,
                st.session_state.chart_ltext,
                st.session_state.chart_ltext1,
                st.session_state.chart_ltext2,
                purpose
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
                "temperature": st.session_state.get("ai_temperature", 0.7)
            }
            response = client.get_chat_completion(**api_params)
            assistant_reply = response.choices[0].message.content
            st.session_state.chat_messages.append({"role": "assistant", "content": assistant_reply})
            with chat_container:
                with st.chat_message("assistant"):
                    st.markdown(assistant_reply)
        except Exception as e:
            err_msg = f"調用AI時發生錯誤：{e}"
            st.session_state.chat_messages.append({"role": "assistant", "content": err_msg})
            with chat_container:
                with st.chat_message("assistant"):
                    st.markdown(err_msg)

# 清除聊天
if st.session_state.chat_messages:
    if st.button("🗑️ 清除對話記錄", key="clear_chat"):
        st.session_state.chat_messages = []
        st.rerun()
