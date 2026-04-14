import os, urllib, calendar, json
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

@contextmanager


def st_capture(output_func):
    with StringIO() as stdout, redirect_stdout(stdout):
        old_write = stdout.write
        def new_write(string):
            ret = old_write(string)
            output_func(stdout.getvalue())
            return ret
        stdout.write = new_write
        yield

def get_file_content_as_string(path):
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
        res1.append( olist[zhihead_code % len(olist)])
        zhihead_code = zhihead_code + 1
    return res1

def weekday(y, m, d):
    cweekdays = ["星期"+i for i in list("日一二三四五六")]
    dayNumber = calendar.weekday(y, m, d)
    return dict(zip([int(i) for i in list("6012345")], cweekdays)).get(dayNumber)

def day_chin(zhi, weekday):
    three_zhi = "申子辰,巳酉丑,寅午戌,亥卯未".split(",")
    head = ["虛畢翼箕奎鬼氐", "房危觜軫斗婁柳", "星心室參角牛胃", "昴張尾壁井亢女"]
    cweekdays = ["星期"+i for i in list("日一二三四五六")]
    ydict = {}
    for i in range(4):
        b = {tuple(list(three_zhi[i])): dict(zip(cweekdays , list(head[i])))}
        ydict.update(b)
    return multi_key_dict_get(ydict, zhi).get(weekday)

# Cerebras Model Options
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

# System Prompt Management Functions
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

def format_liuren_results_for_prompt(chart_text, ltext, ltext1, ltext2):
    """Format Liuren calculation results into a prompt for the AI model."""
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
    return "\n".join(prompt_lines)

st.set_page_config(
    layout="wide",
    page_title="堅六壬 - 六壬排盘",
    page_icon="icon.jpg"
)
pan,example,guji,links,update = st.tabs([' 🧮排盤 ', ' 📜案例 ', ' 📚古籍 ',' 🔗連結 ',' 🆕更新 ' ])

with st.sidebar:
    st.header("日期與時間選擇")
    
    # Set default datetime to current time in Asia/Hong_Kong (HKT)
    default_datetime = pdlm.now(tz='Asia/Hong_Kong')  # June 1, 2025, 12:49 PM HKT
    
    # Separate input fields for year, month, day, hour, minute
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        y = st.number_input(
            "年",
            min_value=1900,
            max_value=2100,
            value=default_datetime.year,
            step=1,
            help="輸入年份 (1900-2100)"
        )
    with col2:
        m = st.number_input(
            "月",
            min_value=1,
            max_value=12,
            value=default_datetime.month,
            step=1,
            help="輸入月份 (1-12)"
        )
    with col3:
        d = st.number_input(
            "日",
            min_value=1,
            max_value=31,
            value=default_datetime.day,
            step=1,
            help="輸入日期 (1-31)"
        )
    
    col4, col5 = st.columns(2)
    with col4:
        h = st.number_input(
            "時",
            min_value=0,
            max_value=23,
            value=default_datetime.hour,
            step=1,
            help="輸入小時 (0-23)"
        )
    with col5:
        min = st.number_input(
            "分",
            min_value=0,
            max_value=59,
            value=default_datetime.minute,
            step=1,
            help="輸入分鐘 (0-59)"
        )
    
    # Quick-select buttons for common times
    st.subheader("快速選擇")
    if st.button("現在"):
        now = pdlm.now(tz='Asia/Hong_Kong')
        y = now.year
        m = now.month
        d = now.day
        h = now.hour
        min = now.minute

    
    # Display selected datetime
    try:
        selected_datetime = pdlm.datetime(y, m, d, h, min, tz='Asia/Hong_Kong')
        st.write(f"已選擇: {y}年{m}月{d}日 {h:02d}:{min:02d}")
    except ValueError:
        st.error("請輸入有效的日期和時間！")
    
    # Timezone info
    st.caption("時區: Asia/Hong_Kong")

    st.markdown("---")
    st.header("AI設置")

    selected_model = st.selectbox(
        "AI 模型",
        options=CEREBRAS_MODEL_OPTIONS,
        index=0,
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
            "選擇系統提示",
            options=prompt_names,
            index=selected_index,
            key="system_prompt_selector",
            help="選擇用於AI模型的系統提示，指導其分析六壬排盤結果"
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
            "編輯系統提示",
            value=st.session_state.system_prompt,
            height=150,
            placeholder="範例：你是一位大六壬專家，根據排盤數據提供詳細分析...",
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
            "新提示內容",
            height=100,
            placeholder="輸入AI分析指令...",
            key=content_key
        )
        if st.button("➕ 新增提示", key="add_prompt_button",
                    disabled=not new_prompt_name or not new_prompt_content):
            if new_prompt_name in prompt_names:
                st.error(f"提示名稱 '{new_prompt_name}' 已存在。")
            else:
                prompts_list.append({
                    "name": new_prompt_name,
                    "content": new_prompt_content
                })
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
            key="ai_max_tokens_slider",
            help="控制AI回應的最大長度"
        )
        st.session_state.ai_temperature = st.slider(
            "溫度 (專注 vs. 創意)",
            0.0, 1.5,
            st.session_state.get("ai_temperature", 0.7),
            step=0.05,
            key="ai_temperature_slider",
            help="較低值 (如 0.2) 更確定性；較高值 (如 0.8) 更隨機"
        )

with guji:
    st.header('古籍')
    st.markdown(get_file_content_as_string("guji.md"))

with links:
    st.header('連結')
    st.markdown(get_file_content_as_string("update.md"), unsafe_allow_html=True)

with update:
    st.header('更新')
    st.markdown(get_file_content_as_string("log.md"))
  
with pan:
    st.header('堅六壬')
    cm =  jieqi.lunar_date_d(y, m, d).get("農曆月")
    #dict(zip(list(range(1,13)), list("正二三四五六七八九十")+["十一","十二"])).get(int(lunar_date_d(y, m, d).get("月").replace("月", "")))
    qgz = gangzhi(y, m, d, h, min)
    jq = jq(y, m, d, h, min)
    liuren_month = kinliuren.Liuren(jq, cm, qgz[1], qgz[2]).result_d(0)
    liuren_day =  kinliuren.Liuren(jq, cm, qgz[2], qgz[3]).result(0)
    liuren_hour =  kinliuren.Liuren(jq, cm, qgz[3], qgz[4]).result_m(0)
    dhorse1 = liuren_month.get("日馬")
    dhorse2 = liuren_day.get("日馬")
    dhorse3 = liuren_hour.get("日馬")
    ltext = liuren_month
    ltext1 = liuren_day
    ltext2 = liuren_hour
    dchin = day_chin(qgz[2][1], weekday(y, m, d))
    zhi = list("子丑寅卯辰巳午未申酉戌亥")
    zdict = dict(zip(zhi, range(1, 13)))
    chin_list = list('角亢氐房心尾箕斗牛女虛危室壁奎婁胃昴畢觜參井鬼柳星張翼軫')
    d_n_h = zdict[qgz[3][1]] + zdict[qgz[4][1]]
    a = "日期︰{}年{}月{}日{}時{}分\n".format(y,m,d,h,min)
    b = "格局︰{}\n".format(ltext.get("格局")[0])
    c = "節氣︰{}\n".format(jq)      
    d = "干支︰{}年 {}月 {}日 {}時 {}分\n".format(qgz[0], qgz[1], qgz[2], qgz[3], qgz[4])
    d2 = "日馬︰{}(月) {}(日) {}(時)\n\n".format(dhorse1, dhorse2, dhorse3)
    d1="　　月課　　　　　　　日課　　　　　　　時課\n\n"
    e ="　{}　　　　　{}　　　　　{}\n".format("".join(ltext.get("三傳").get("初傳")),"".join(ltext1.get("三傳").get("初傳")),"".join(ltext2.get("三傳").get("初傳")))
    f ="　{}　　　　　{}　　　　　{}\n".format("".join(ltext.get("三傳").get("中傳")),"".join(ltext1.get("三傳").get("中傳")),"".join(ltext2.get("三傳").get("中傳")))
    g ="　{}　　　　　{}　　　　　{}\n\n".format("".join(ltext.get("三傳").get("末傳")),"".join(ltext1.get("三傳").get("末傳")),"".join(ltext2.get("三傳").get("末傳")))
    h ="　{}　　　　　{}　　　　　{}\n".format("".join([ltext.get("四課").get(i)[0][0] for i in ['四課','三課','二課','一課']]),"".join([ltext1.get("四課").get(i)[0][0] for i in ['四課','三課','二課','一課']]), "".join([ltext2.get("四課").get(i)[0][0] for i in ['四課','三課','二課','一課']]))
    i ="　{}　　　　　{}　　　　　{}\n\n".format("".join([ltext.get("四課").get(i)[0][1] for i in ['四課','三課','二課','一課']]),"".join([ltext1.get("四課").get(i)[0][1] for i in ['四課','三課','二課','一課']]), "".join([ltext2.get("四課").get(i)[0][1] for i in ['四課','三課','二課','一課']]))
    j ="　{}　　　　　{}　　　　　{}\n".format("".join([ltext.get("地轉天將").get(i) for i in list("巳午未申")]),"".join([ltext1.get("地轉天將").get(i) for i in list("巳午未申")]), "".join([ltext2.get("地轉天將").get(i) for i in list("巳午未申")]))
    k ="　{}　　　　　{}　　　　　{}\n".format("".join([ltext.get("地轉天盤").get(i) for i in list("巳午未申")]),"".join([ltext1.get("地轉天盤").get(i) for i in list("巳午未申")]), "".join([ltext2.get("地轉天盤").get(i) for i in list("巳午未申")]))
    l ="{}{}　　{}{}　　　{}{}　　{}{}　　　{}{}　　{}{}\n".format(ltext.get("地轉天將").get("辰"), ltext.get("地轉天盤").get("辰"), ltext.get("地轉天盤").get("酉"), ltext.get("地轉天將").get("酉"),ltext1.get("地轉天將").get("辰"), ltext1.get("地轉天盤").get("辰"), ltext1.get("地轉天盤").get("酉"), ltext1.get("地轉天將").get("酉"), ltext2.get("地轉天將").get("辰"), ltext2.get("地轉天盤").get("辰"), ltext2.get("地轉天盤").get("酉"), ltext2.get("地轉天將").get("酉"))
    m ="{}{}　　{}{}　　　{}{}　　{}{}　　　{}{}　　{}{}\n".format(ltext.get("地轉天將").get("卯"), ltext.get("地轉天盤").get("卯"), ltext.get("地轉天盤").get("戌"), ltext.get("地轉天將").get("戌"),ltext1.get("地轉天將").get("卯"), ltext1.get("地轉天盤").get("卯"), ltext1.get("地轉天盤").get("戌"), ltext1.get("地轉天將").get("戌"), ltext2.get("地轉天將").get("卯"), ltext2.get("地轉天盤").get("卯"), ltext2.get("地轉天盤").get("戌"), ltext2.get("地轉天將").get("戌"))
    n ="　{}　　　　　{}　　　　　{}\n".format("".join([ltext.get("地轉天盤").get(i) for i in list("寅丑子亥")]), "".join([ltext1.get("地轉天盤").get(i) for i in list("寅丑子亥")]), "".join([ltext2.get("地轉天盤").get(i) for i in list("寅丑子亥")]))
    o ="　{}　　　　　{}　　　　　{}\n\n\n".format("".join([ltext.get("地轉天將").get(i) for i in list("寅丑子亥")]), "".join([ltext1.get("地轉天將").get(i) for i in list("寅丑子亥")]), "".join([ltext2.get("地轉天將").get(i) for i in list("寅丑子亥")]))
    richp1 = zdict[bidict(ltext2.get("地轉天將")).inverse["貴"]]
    richp2 = zdict[ltext1.get("地轉天盤").get(bidict(ltext2.get("地轉天將")).inverse["貴"])]
    home = dict(zip(range(1,29),new_list(chin_list, dchin))).get(zdict[qgz[4][1]]+zdict[qgz[3][1]])
    away = dict(zip(range(1,29),new_list(chin_list, dchin))).get(zdict[qgz[3][1]]) 
    skychin = dict(zip(range(1,29),new_list(chin_list, dchin))).get( richp1+richp2  ) 
    #p = "\n《堅六壬用禽法》\n地禽︰{}(主分禽) VS {}(客時禽) | 天禽︰{}".format(home, away, skychin) 

    output2 = st.empty()
    with st_capture(output2.code):
        print(a+b+c+d+d2+d1+e+f+g+h+i+j+k+l+m+n+o)
    expander = st.expander("原始碼")
    expander.write(str(ltext))

    chart_text = a+b+c+d+d2+d1+e+f+g+h+i+j+k+l+m+n+o

    if st.button("🔍 使用AI分析排盤結果", key="analyze_with_ai"):
        with st.spinner("AI正在分析六壬排盤結果..."):
            cerebras_api_key = st.secrets.get("CEREBRAS_API_KEY") or os.getenv("CEREBRAS_API_KEY")
            if not cerebras_api_key:
                st.error("CEREBRAS_API_KEY 未設置，請先在 .streamlit/secrets.toml 設置，或設置環境變量 CEREBRAS_API_KEY。")
            else:
                try:
                    client = CerebrasClient(api_key=cerebras_api_key)
                    liuren_prompt = format_liuren_results_for_prompt(chart_text, ltext, ltext1, ltext2)
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
