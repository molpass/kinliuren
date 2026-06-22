import os, sys, urllib, calendar, json, datetime

# Add src/ to the module search path so that library modules can be imported by name.
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
        "당신은 《대육임대전(大六壬大全)》, 《육임수언(六壬粹言)》, 《임학쇄기(壬學瑣記)》 등 고전 고서와 역사 사례에 정통한 대육임 대가입니다. 제공된 육임 포국 데이터를 바탕으로 다음을 수행하세요:\n"
        "1. 반국(盤局)의 핵심 요소(사과·삼전·천장·천반지반 등)를 설명합니다.\n"
        "2. 육임 고전 이론에 결합하여 반국의 길흉과 잠재적 영향을 분석합니다.\n"
        "3. 일과·월과·시과의 격국과 삼전·사과를 바탕으로 현재 운세 흐름을 상세히 평가합니다.\n"
        "4. 실용적인 조언이나 대응 전략을 제시합니다.\n"
        "명확한 구조(단락·제목)로 제시하고, 전문적이면서도 이해하기 쉬운 한국어로 작성하며, 역사 사례나 고전 이론을 적절히 인용하세요."
    )
    try:
        with open(SYSTEM_PROMPTS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        default_data = {
            "prompts": [{"name": "육임 대가", "content": DEFAULT_SYSTEM_PROMPT}],
            "selected": "육임 대가"
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
        st.error(f"프롬프트 저장 중 오류: {e}")
        return False

def format_liuren_results_for_prompt(chart_text, ltext, ltext1, ltext2):
    """Format Liuren calculation results into a prompt for the AI model."""
    prompt_lines = [
        "다음은 대육임 포국 계산 결과입니다. 이 데이터를 바탕으로 상세한 분석과 해석을 한국어로 제공해 주세요:",
        "",
        chart_text,
        "",
        "【월과(月課) 상세 데이터】",
        f"격국(格局): {ltext.get('格局', '')}",
        f"삼전(三傳): 초전{''.join(ltext.get('三傳', {}).get('初傳', []))} | 중전{''.join(ltext.get('三傳', {}).get('中傳', []))} | 말전{''.join(ltext.get('三傳', {}).get('末傳', []))}",
        f"사과(四課): {ltext.get('四課', '')}",
        f"천장(天將): {ltext.get('地轉天將', '')}",
        f"천반(天盤): {ltext.get('地轉天盤', '')}",
        f"일마(日馬): {ltext.get('日馬', '')}",
        "",
        "【일과(日課) 상세 데이터】",
        f"격국(格局): {ltext1.get('格局', '')}",
        f"삼전(三傳): 초전{''.join(ltext1.get('三傳', {}).get('初傳', []))} | 중전{''.join(ltext1.get('三傳', {}).get('中傳', []))} | 말전{''.join(ltext1.get('三傳', {}).get('末傳', []))}",
        f"사과(四課): {ltext1.get('四課', '')}",
        f"천장(天將): {ltext1.get('地轉天將', '')}",
        f"천반(天盤): {ltext1.get('地轉天盤', '')}",
        f"일마(日馬): {ltext1.get('日馬', '')}",
        "",
        "【시과(時課) 상세 데이터】",
        f"격국(格局): {ltext2.get('格局', '')}",
        f"삼전(三傳): 초전{''.join(ltext2.get('三傳', {}).get('初傳', []))} | 중전{''.join(ltext2.get('三傳', {}).get('中傳', []))} | 말전{''.join(ltext2.get('三傳', {}).get('末傳', []))}",
        f"사과(四課): {ltext2.get('四課', '')}",
        f"천장(天將): {ltext2.get('地轉天將', '')}",
        f"천반(天盤): {ltext2.get('地轉天盤', '')}",
        f"일마(日馬): {ltext2.get('日馬', '')}",
    ]
    return "\n".join(prompt_lines)

st.set_page_config(
    layout="wide",
    page_title="堅六壬 - 육임 포국",
    page_icon="icon.jpg"
)
pan,example,guji,links,update = st.tabs([' 🧮 포국 ', ' 📜 사례 ', ' 📚 고서 ',' 🔗 링크 ',' 🆕 업데이트 ' ])

with st.sidebar:
    st.header("날짜와 시간 선택")

    # Set default datetime to current time in Asia/Hong_Kong (HKT)
    default_datetime = pdlm.now(tz='Asia/Hong_Kong')

    # Quick-select button for current time
    if st.button("📍 현재"):
        now = pdlm.now(tz='Asia/Hong_Kong')
        st.session_state['dt_date'] = now.date()
        st.session_state['dt_time'] = now.time()
        st.rerun()

    # Native date picker with calendar popup
    selected_date = st.date_input(
        "날짜",
        value=default_datetime.date(),
        min_value=datetime.date(1900, 1, 1),
        max_value=datetime.date(2100, 12, 31),
        key='dt_date',
        help="클릭하여 날짜 선택"
    )

    # Native time picker with hour/minute selection
    selected_time = st.time_input(
        "시간",
        value=default_datetime.time(),
        step=datetime.timedelta(minutes=1),
        key='dt_time',
        help="클릭하여 시간 선택"
    )

    y = selected_date.year
    m = selected_date.month
    d = selected_date.day
    h = selected_time.hour
    mi = selected_time.minute

    # Display selected datetime
    st.write(f"선택됨: {y}년 {m}월 {d}일 {h:02d}:{mi:02d}")

    # Timezone info
    st.caption("시간대: Asia/Hong_Kong")

    st.markdown("---")
    st.header("AI 설정")

    selected_model = st.selectbox(
        "AI 모델",
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
            "시스템 프롬프트 선택",
            options=prompt_names,
            index=selected_index,
            key="system_prompt_selector",
            help="AI 모델에 사용할 시스템 프롬프트를 선택합니다. 육임 포국 결과 분석을 지도합니다"
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
            "시스템 프롬프트 편집",
            value=st.session_state.system_prompt,
            height=150,
            placeholder="예: 당신은 대육임 전문가입니다. 포국 데이터를 바탕으로 상세한 분석을 한국어로 제공하세요...",
            key="system_prompt_editor"
        )

        st.session_state.system_prompt = new_content

        col_u, col_d = st.columns(2)
        with col_u:
            if st.button("💾 프롬프트 업데이트", key="update_prompt_button"):
                for prompt in prompts_list:
                    if prompt["name"] == selected_name:
                        prompt["content"] = new_content
                        break
                if save_system_prompts(system_prompts_data):
                    st.toast(f"✅ 시스템 프롬프트 '{selected_name}'을(를) 업데이트했습니다!")

        with col_d:
            if st.button("❌ 프롬프트 삭제", key="delete_prompt_button",
                        disabled=len(prompts_list) <= 1):
                prompts_list = [p for p in prompts_list if p["name"] != selected_name]
                system_prompts_data["prompts"] = prompts_list
                if selected_name == selected_prompt and prompts_list:
                    system_prompts_data["selected"] = prompts_list[0]["name"]
                if save_system_prompts(system_prompts_data):
                    st.toast(f"✅ 시스템 프롬프트 '{selected_name}'을(를) 삭제했습니다!")
                    st.rerun()

    if "form_key_suffix" not in st.session_state:
        st.session_state.form_key_suffix = 0

    name_key = f"new_prompt_name_{st.session_state.form_key_suffix}"
    content_key = f"new_prompt_content_{st.session_state.form_key_suffix}"

    with st.expander("➕ 프롬프트 추가", expanded=False):
        new_prompt_name = st.text_input("새 프롬프트 이름", key=name_key)
        new_prompt_content = st.text_area(
            "새 프롬프트 내용",
            height=100,
            placeholder="AI 분석 지시문을 입력하세요...",
            key=content_key
        )
        if st.button("➕ 프롬프트 추가", key="add_prompt_button",
                    disabled=not new_prompt_name or not new_prompt_content):
            if new_prompt_name in prompt_names:
                st.error(f"프롬프트 이름 '{new_prompt_name}'이(가) 이미 존재합니다.")
            else:
                prompts_list.append({
                    "name": new_prompt_name,
                    "content": new_prompt_content
                })
                system_prompts_data["prompts"] = prompts_list
                if save_system_prompts(system_prompts_data):
                    st.session_state.form_key_suffix += 1
                    st.toast(f"✅ 시스템 프롬프트 '{new_prompt_name}'을(를) 추가했습니다!")
                    st.rerun()

    if st.toggle("🔧 고급 설정", key="advanced_settings_toggle"):
        st.session_state.ai_max_tokens = st.slider(
            "최대 생성 Tokens",
            AI_MIN_MAX_TOKENS, AI_MAX_MAX_TOKENS,
            st.session_state.get("ai_max_tokens", AI_MAX_MAX_TOKENS),
            key="ai_max_tokens_slider",
            help="AI 응답의 최대 길이를 조절합니다"
        )
        st.session_state.ai_temperature = st.slider(
            "온도 (정확 vs. 창의)",
            0.0, 1.5,
            st.session_state.get("ai_temperature", 0.7),
            step=0.05,
            key="ai_temperature_slider",
            help="낮은 값(예: 0.2)은 더 확정적이고, 높은 값(예: 0.8)은 더 무작위적입니다"
        )

with guji:
    st.header('고서')
    st.markdown(get_file_content_as_string("docs/guji.md"))

with links:
    st.header('링크')
    st.markdown(get_file_content_as_string("docs/contact.md"), unsafe_allow_html=True)

with update:
    st.header('업데이트')
    st.markdown(get_file_content_as_string("docs/changelog.md"))

with pan:
    st.header('堅六壬 · 육임 포국')
    cm =  jieqi.lunar_date_d(y, m, d).get("農曆月")
    #dict(zip(list(range(1,13)), list("正二三四五六七八九十")+["十一","十二"])).get(int(lunar_date_d(y, m, d).get("月").replace("月", "")))
    qgz = gangzhi(y, m, d, h, mi)
    jq = jq(y, m, d, h, mi)
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
    a = "日期︰{}年{}月{}日{}時{}分\n".format(y,m,d,h,mi)
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
    expander = st.expander("원본 데이터")
    expander.write(str(ltext))

    chart_text = a+b+c+d+d2+d1+e+f+g+h+i+j+k+l+m+n+o

    # Store chart context in session state for use in chat
    st.session_state.chart_text = chart_text
    st.session_state.chart_ltext = ltext
    st.session_state.chart_ltext1 = ltext1
    st.session_state.chart_ltext2 = ltext2

    if st.button("🔍 AI로 포국 결과 분석", key="analyze_with_ai"):
        with st.spinner("AI가 육임 포국 결과를 분석하는 중..."):
            cerebras_api_key = st.secrets.get("CEREBRAS_API_KEY") or os.getenv("CEREBRAS_API_KEY")
            if not cerebras_api_key:
                st.error("CEREBRAS_API_KEY가 설정되지 않았습니다. .streamlit/secrets.toml에 설정하거나 환경 변수 CEREBRAS_API_KEY를 설정해 주세요.")
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
                    with st.expander("AI 분석 결과", expanded=True):
                        st.markdown(raw_response)
                except Exception as e:
                    st.error(f"AI 호출 중 오류가 발생했습니다: {e}")

# --- Fixed LLM Chat Section at Bottom ---
st.markdown("---")
st.subheader("💬 AI 육임 문답")

# Initialize chat history
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# Display chat history
chat_container = st.container(height=400)
with chat_container:
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# Chat input (fixed at bottom by Streamlit)
if user_input := st.chat_input("육임 질문을 입력하세요...", key="chat_input"):
    # Append user message to history
    st.session_state.chat_messages.append({"role": "user", "content": user_input})

    # Display user message immediately
    with chat_container:
        with st.chat_message("user"):
            st.markdown(user_input)

    # Build context-aware messages for the AI
    cerebras_api_key = st.secrets.get("CEREBRAS_API_KEY") or os.getenv("CEREBRAS_API_KEY")
    if not cerebras_api_key:
        err_msg = "CEREBRAS_API_KEY가 설정되지 않았습니다. .streamlit/secrets.toml에 설정하거나 환경 변수 CEREBRAS_API_KEY를 설정해 주세요."
        st.session_state.chat_messages.append({"role": "assistant", "content": err_msg})
        with chat_container:
            with st.chat_message("assistant"):
                st.markdown(err_msg)
    else:
        # Build system prompt with chart context
        chart_context = ""
        if "chart_text" in st.session_state:
            liuren_prompt = format_liuren_results_for_prompt(
                st.session_state.chart_text,
                st.session_state.chart_ltext,
                st.session_state.chart_ltext1,
                st.session_state.chart_ltext2
            )
            chart_context = f"\n\n다음은 현재 육임 포국 데이터입니다(참고용):\n{liuren_prompt}"

        system_content = st.session_state.get("system_prompt", "") + chart_context

        # Build conversation messages (system + full chat history)
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

            # Append assistant reply to history
            st.session_state.chat_messages.append({"role": "assistant", "content": assistant_reply})

            with chat_container:
                with st.chat_message("assistant"):
                    st.markdown(assistant_reply)
        except Exception as e:
            err_msg = f"AI 호출 중 오류가 발생했습니다: {e}"
            st.session_state.chat_messages.append({"role": "assistant", "content": err_msg})
            with chat_container:
                with st.chat_message("assistant"):
                    st.markdown(err_msg)

# Clear chat button
if st.session_state.chat_messages:
    if st.button("🗑️ 대화 기록 지우기", key="clear_chat"):
        st.session_state.chat_messages = []
        st.rerun()
