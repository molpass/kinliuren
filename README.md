# 🔮 堅大六壬 · Kinliuren — Python 大六壬(대육임) 排盤 라이브러리

<p align="center">
  <b>中國三式重中之重 · The Premier Art of China's Three Divination Styles</b><br>
  <i>大六壬 | Da Liu Ren | Six Ren Astrology</i>
</p>

<p align="center">
  <a href="https://pypi.org/project/kinliuren/"><img src="https://img.shields.io/pypi/pyversions/kinliuren" alt="Python Version"></a>
  <a href="https://pypi.org/project/kinliuren/"><img src="https://img.shields.io/pypi/v/kinliuren" alt="PyPI Version"></a>
  <a href="https://pypi.org/project/kinliuren/"><img src="https://img.shields.io/pypi/dm/kinliuren" alt="Monthly Downloads"></a>
  <a href="https://github.com/kentang2017/kinliuren/stargazers"><img src="https://img.shields.io/github/stars/kentang2017/kinliuren?style=flat" alt="GitHub Stars"></a>
  <a href="https://github.com/kentang2017/kinliuren/blob/master/LICENSE"><img src="https://img.shields.io/github/license/kentang2017/kinliuren" alt="License"></a>
</p>

<p align="center">
  <a href="https://kinliuren.streamlit.app/">
    <img src="https://img.shields.io/badge/🌐%20線上排盤-Live%20Demo-brightgreen?style=for-the-badge" alt="Live Demo">
  </a>
</p>

> 🇰🇷 이 저장소는 **molpass가 포크한 사본**입니다. 원문(中文·English)은 [README.en.md](./README.en.md)를 참고하세요.

---

<p align="center">
  <img src="https://github.com/kentang2017/kinliuren/blob/master/pic/Untitled-33.png" alt="堅六壬排盤截圖" width="80%">
</p>

---

## 📖 도입 · Introduction

**대육임**(大六壬, Da Liu Ren)은 육임신과(六壬神課)라고도 하며, 중국 고대 3대 점복술 중 하나로 **기문둔갑**(奇門遁甲), **태을신수**(太乙神數)와 함께 「삼식(三式)」으로 불립니다. 대육임은 한나라, 삼국, 위진남북조 시대에 성행했으며, 문인 명사들이 이를 풍류와 여흥으로 삼아 품속에 물건을 감추고 서로 점쳐 맞히곤 했는데 이를 「사복(射覆)」이라 불렀습니다. 당송 이래 명청을 거쳐 오늘날까지 이어져 왔습니다. 육임술은 일본에 전해진 뒤 헤이안 시대에 음양사 아베노 세이메이(安倍晴明)에 의해 크게 발전하여, 현대 점술·상술의 하나가 되었습니다.

본 라이브러리(**堅六壬**)는 Python으로 대육임의 완전한 포국(排盤)을 구현하여, 삼전(三傳)·사과(四課)·천지반(天地盤)·신살(神煞) 및 각종 격국(格局) 판단을 망라하며, 학습자를 위한 온라인 포국 Web App도 제공합니다.

> 누락이나 오류가 있다면 제게 제보해 주세요. 적시에 수정하겠습니다. 감사합니다!

---

**Da Liu Ren** (大六壬, "Six Ren Astrology") is one of the Three Styles (三式 *sānshì*) of classical Chinese divination, together with **Qi Men Dun Jia** (奇門遁甲) and **Taiyi** (太乙). It originated during the Warring States period and flourished through the Han, Three Kingdoms, and Tang–Qing dynasties. The art later spread to Japan, where it was championed by the legendary *onmyōji* Abe no Seimei during the Heian period.

**Kinliuren** is a fully-featured Python library that computes Da Liu Ren charts — including the Three Transmissions (三傳), Four Courses (四課), Celestial & Earthly Disk (天地盤), Spiritual Auspices (神煞), and pattern recognition (格局) — and ships with a live Streamlit web app.

---

## ✨ 기능 특징 · Features

| 기능 Feature | 설명 Description |
|---|---|
| 📅 삼전 추산 Three Transmissions | 초전·중전·말전 완전 계산 Full calculation of Initial, Middle & Final Transmissions |
| 📐 사과 배열 Four Courses | 1·2·3·4과 정밀 배열 Accurate Four-Course layout |
| 🌀 천지반 Celestial–Earthly Disk | 십이지 천반·지반 및 십이천장 대응 12-branch sky/earth disk with 12 generals |
| 🔮 신살 계산 Spiritual Auspices | 일마·천마·장성 등 30여 종 신살 30+ auspicious/inauspicious indicators |
| 🗂️ 격국 판단 Pattern Recognition | 적극(賊尅)·중심(重審)·원수(元首) 등 과체 격국 Pattern identification (Thief-Clashing, Retrial, etc.) |
| 🗓️ 절기 지원 Solar Term Support | 24절기 자동 대응 Auto-mapping to 24 solar terms |
| 🌐 온라인 포국 Web App | Streamlit 실시간 인터랙티브 포국 Real-time interactive chart via Streamlit |
| 📦 PyPI 패키지 PyPI Package | `pip install kinliuren` 한 줄 설치 One-line install |

---

## 🚀 설치 · Installation

```bash
pip install kinliuren
```

> Python 3.7+ 필요  ·  Requires Python 3.7+

---

## ⚡ 기과(起課) 방법 · Quickstart

```python
from kinliuren import kinliuren

# 格式: Liuren(節氣, 農曆月份, 日干支, 時干支).result(0)
# Format: Liuren(solar_term, lunar_month, day_ganzhi, hour_ganzhi).result(0)

result = kinliuren.Liuren("驚蟄", "二", "己未", "甲午").result(0)
print(result)
```

<details>
<summary>📄 출력 예시 보기 · Sample Output (click to expand)</summary>

```python
{
  '節氣': '驚蟄',
  '日期': '己未日甲午時',
  '格局': ['賊尅', '重審'],
  '日馬': '巳',
  '三傳': {
    '初傳': ['巳', '虎', '父', '丁'],
    '中傳': ['戌', '雀', '兄', '壬'],
    '末傳': ['卯', '玄', '官', '乙']
  },
  '四課': {
    '四課': ['巳子', '虎'],
    '三課': ['子未', '貴'],
    '二課': ['巳子', '虎'],
    '一課': ['子己', '貴']
  },
  '天地盤': {
    '天盤': ['亥', '子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌'],
    '地盤': ['午', '未', '申', '酉', '戌', '亥', '子', '丑', '寅', '卯', '辰', '巳'],
    '天將': ['蛇', '貴', '后', '陰', '玄', '常', '虎', '空', '龍', '勾', '合', '雀']
  },
  '地轉天盤': {'午': '亥', '未': '子', '申': '丑', '酉': '寅', '戌': '卯',
               '亥': '辰', '子': '巳', '丑': '午', '寅': '未', '卯': '申',
               '辰': '酉', '巳': '戌'},
  '地轉天將': {'午': '蛇', '未': '貴', '申': '后', '酉': '陰', '戌': '玄',
               '亥': '常', '子': '虎', '丑': '空', '寅': '龍', '卯': '勾',
               '辰': '合', '巳': '雀'},
  '神煞': {
    '天城': '申', '天吏': '寅', '皇書': '寅', '天喜': '戌',
    '天耳': '申', '戲神': '巳', '遊神': '丑', '天車': '巳',
    '月馬': '辰', '日馬': '巳', '丁馬': '巳', '日德': '寅',
    '日祿': '午', '賢貴': '丑', '進神': '卯', '進神二': '酉',
    '五合': '寅', '支德': '午', '將星': '卯', '六合': '午',
    '天馬': '申', '聖心': '巳', '天恩': '酉', '天財': '午',
    '飛廉': '巳', '會神': '戌', '成神': '申', '生氣': '丑',
    '月合': '戌', '閃電': '丑'
  }
}
```
</details>

---

## 🌐 온라인 포국 · Live Demo

설치 없이 실시간 인터랙티브 포국을 체험하세요.
Try the live interactive chart — no installation required.

👉 **[https://kinliuren.streamlit.app/](https://kinliuren.streamlit.app/)**

---

## 📜 라이선스 · License

[MIT License](LICENSE)
