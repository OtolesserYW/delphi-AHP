import os
import json
import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

# ============================================================
# 基本配置
# ============================================================
ROUND_NO = 3                      # 当前为第三轮专家咨询
FIXED_DATE_STR = "2026年7月7日"    # 第三轮统一填表日期
ADMIN_PASSCODE = "admin123"       # 管理员导出数据口令

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "ahp_responses.db")


# ============================================================
# 数据库：初始化与读写
# ============================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expert_name TEXT NOT NULL,
            round_no INTEGER NOT NULL,
            submit_time TEXT NOT NULL,
            matrices_json TEXT NOT NULL,
            cr_json TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

def save_submission(expert_name: str, round_no: int, matrices_data: dict, cr_data: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO submissions (expert_name, round_no, submit_time, matrices_json, cr_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            expert_name,
            round_no,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            json.dumps(matrices_data, ensure_ascii=False),
            json.dumps(cr_data, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()

def load_all_submissions() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM submissions ORDER BY id", conn)
    conn.close()
    return df

init_db()


# ============================================================
# 页面样式配置 (全局加大字体、1.5倍行距、全面去红美化)
# ============================================================
st.set_page_config(page_title="医护人员感染性职业暴露风险评估——专家AHP问卷", layout="centered")

st.markdown("""
<style>
    /* 调整全局普通文本（如说明、含义等）的字体大小和行距 */
    .stMarkdown p, .stMarkdown li {
        font-size: 18px !important;
        line-height: 1.5 !important;
    }
    /* 调整折叠面板内文字大小 */
    .streamlit-expanderContent p {
        font-size: 17px !important;
        line-height: 1.5 !important;
    }
    
    /* 1. 放大并加粗“我确认这组指标确实同等重要”复选框的文字 */
    div[data-testid="stCheckbox"] label p {
        font-size: 20px !important;
        font-weight: bold !important;
        color: #2c3e50 !important;
    }
    
    /* 2. 彻底改造滑动条：消除刺眼鲜红，放大并优化标度文字 */
    /* 放大滑动条部分的数字/文字提示 */
    div[data-testid="stSelectSlider"] span, 
    div[data-testid="stSelectSlider"] p,
    div[data-testid="stSelectSlider"] div {
        font-size: 18px !important;
    }
    /* 精准抓取滑块下方的激活文本，强行将默认的鲜红色覆写为温馨的医疗蓝 */
    div[data-testid="stSelectSlider"] [style*="color"],
    div[data-testid="stSelectSlider"] span[data-baseweb="typography"] {
        color: #1f77b4 !important;
        font-weight: bold !important;
    }
    /* 将滑动条的圆形滑块颜色也从鲜红替换为统一的蓝色 */
    div[data-testid="stSelectSlider"] div[role="slider"] {
        background-color: #1f77b4 !important;
        border-color: #1f77b4 !important;
    }
    /* 将滑动条左侧轨道的激活颜色从鲜红替换为蓝色 */
    .stSlider [style*="background-color"] {
        background-color: #1f77b4 !important;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# AHP 计算与交互组件配置
# ============================================================
def get_ahp_cr(matrix: np.ndarray) -> float:
    n = matrix.shape[0]
    if n <= 2:
        return 0.0

    eigenvalues = np.linalg.eigvals(matrix)
    lambda_max = np.max(eigenvalues.real)
    CI = (lambda_max - n) / (n - 1)

    RI_TABLE = [0, 0, 0.58, 0.90, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49]
    RI = RI_TABLE[n - 1] if n <= len(RI_TABLE) else 1.49
    if RI == 0:
        return 0.0

    cr = CI / RI
    return max(cr, 0.0)

SLIDER_OPTIONS = [
    "左9(极重要)", "左8", "左7(强重要)", "左6", "左5(明重要)", "左4", "左3(稍重要)", "左2",
    "1 (同等重要)",
    "右2", "右3(稍重要)", "右4", "右5(明重要)", "右6", "右7(强重要)", "右8", "右9(极重要)"
]

def option_to_value(opt: str) -> float:
    if opt == "1 (同等重要)": return 1.0
    if opt.startswith("左"): return float(opt[1:2])
    if opt.startswith("右"): return 1.0 / float(opt[1:2])
    return 1.0


# ============================================================
# 各级指标列表及说明内容
# ============================================================
L1_ITEMS = ["A.病原体与相应疾病风险特征", "B.环境暴露风险", "C.个体风险与健康基础"]
L1_DEFS = [
    "包含下属指标：A1.病原体基础属性，A2.病原体变异与进化潜力，A3.传播特性与潜力，A4.环境存活能力，A5.疾病临床严重性，A6.临床防治有效性。",
    "包含下属指标：B1.布局与通风，B2.感染者风险，B3.物品与环境污染风险。",
    "包含下属指标：C1.工作场景暴露风险，C2.个体生理易感性，C3.个体防护装备的身体适配性。"
]

L2_A_ITEMS = ["A1.病原体基础属性", "A2.病原体变异与进化潜力", "A3.传播特性与潜力", "A4.环境存活能力", "A5.疾病临床严重性", "A6.临床防治有效性"]
L2_A_DEFS = [
    "包含下属指标：A1.1 病原体生物危害分级，A1.2 病原体谱构成，A1.3 病原体载量。",
    "包含下属指标：A2.1 分子进化情况，A2.2 遗传距离。",
    "包含下属指标：A3.1 传播途径与多途径风险，A3.2 基本传染数R0/有效传染数Re，A3.3 无症状/潜伏期传播能力。",
    "包含下属指标：A4.1 消杀敏感性，A4.2 环境稳定性。",
    "包含下属指标：A5.1 病例住院率，A5.2 重症率，A5.3 病死率。",
    "包含下属指标：A6.1 早期诊疗可行性，A6.2 预防接种可及性与有效性，A6.3 特异性治疗药物可及性与有效性，A6.4 病原体耐药性。"
]

L2_B_ITEMS = ["B1.布局与通风", "B2.感染者风险", "B3.物品与环境污染风险"]
L2_B_DEFS = [
    "包含下属指标：B1.1 功能分区合理性，B1.2 流线设置合理性，B1.3 空气质量与气流组织，B1.4 通风保障充分性。",
    "包含下属指标：B2.1 感染者行为可控性，B2.2 感染者体液暴露风险，B2.3 感染者集中度，B2.4 感染者移动/转运。",
    "包含下属指标：B3.1 物资与环境表面污染风险，B3.2 空气颗粒暴露风险，B3.3 医疗废物传染风险，B3.4 医疗器械与设备污染风险。"
]

L2_C_ITEMS = ["C1.工作场景暴露风险", "C2.个体生理易感性", "C3.个体防护装备的身体适配性"]
L2_C_DEFS = [
    "包含下属指标：C1.1 操作暴露风险，C1.2 岗位暴露强度，C1.3 工作场景暴露时间。",
    "包含下属指标：C2.1 基础健康状况，C2.2 免疫能力。",
    "包含下属指标：C3.1 尺寸匹配性，C3.2 操作灵活性，C3.3 舒适耐受性，C3.4 个体特征适配性，C3.5 基础健康适宜性。"
]

LEVEL3_DEFS = {
    "L3_A1": [
        "根据《人间传染的病原微生物名录》等标准，根据病原微生物的传染性、感染后对个体或群体的危害程度，对其进行生物安全等级划分（通常为第一至四类），以反映医护人员在接触该病原体时所面临的基础感染风险水平。",
        "在特定医疗场景或人群中，不同病原体种类及其组合特征，包括主要病原类型及其相互共存情况，用以体现医护人员所处环境中病原体结构的复杂性及潜在职业暴露风险。",
        "指传染源的特定体液、分泌物或组织中，单位体积内所含有的具有活性的病原体数量。该指标通常与患者的临床症状严重程度密切相关，重症患者或疾病急性发作期人群载量更高、传播力最强，直接关系到医护人员发生有效暴露和感染的可能性。",
    ],
    "L3_A2": [
        "病原体在分子水平持续发生变异和演化的特征，用以体现其传播性、致病性及防控不确定性的变化趋势。",
        "不同病原体株系之间的基因差异程度，用以反映其潜在新发风险和防控复杂性。",
    ],
    "L3_A3": [
        "病原体可通过一种或多种传播方式传播，并在医疗活动中形成叠加传播风险的特征，直接影响医护人员的暴露方式和防护要求；当存在未知或不确定传播途径时，其不确定性将直接增加职业暴露风险评估的复杂性与防控难度。",
        "基本传染数R0指在全部易感人群（无免疫或防控措施）中，一个感染者在其传染期内平均产生的二级感染病例数；有效传染数Re（也称Rt）是实际环境下已考虑人口免疫水平、行为干预、疫苗接种、季节因素等抑制作用的传播指数，二者用以反映不同防控条件下病原体持续传播的潜在风险水平。",
        "感染者在未出现明显症状时仍可传播病原体的特征，这种隐匿性传播增加了医护人员识别感染源和防控暴露的难度。",
    ],
    "L3_A4": [
        "病原体固有的理化抵抗特性，即其对各类化学消毒因子及物理灭活因子的生物学敏感程度，反映该病原体从生物结构上抵抗人工干扰、保持感染活性的难易程度。",
        "病原体在空气、物体表面或其他环境介质中存活并保持感染力的能力，用以体现其通过环境介质传播的潜在风险。",
    ],
    "L3_A5": [
        "感染病例中需要住院治疗的比例，用以反映该疾病对医疗系统负担和病情严重程度的总体水平。",
        "感染病例中发展为重症或危重症的比例，用以体现疾病对患者健康造成严重损害的风险程度。",
        "感染病例中因该疾病导致死亡的比例，是衡量疾病致死风险和公共卫生危害程度的重要指标。",
    ],
    "L3_A6": [
        "感染发生后，及时开展早期发现、明确诊断和有效治疗的现实条件，用以体现疾病防控的可控性。",
        "针对特定病原体的疫苗在现实中的可获得程度，以及接种该疫苗后能在医护人员体内产生切实免疫保护的程度。",
        "暴露后针对该病原体的靶向治疗或阻断药物在临床的获取与使用条件，以及该药物在实际干预中的临床疗效。",
        "病原体对抗感染药物产生耐受的能力，该特性可能削弱治疗效果并延长感染风险暴露时间。",
    ],
    "L3_B1": [
        "工作场所三区两通道划分的明确性与分隔有效性，其合理程度直接影响病原体在不同区域间传播和医护人员交叉暴露的风险。",
        "患者、医护人员及各类物品（涵盖洁净物资、一般物品与非洁净污物）在医疗活动中流动路径的科学性与有序性，即各项流线的实际布局与运行状况，符合所在功能区域专项流线设置标准的达标程度。",
        "医疗空间中环境空气参数（温湿度）、换气方式、气流方向及压力梯度的设置情况，以国家医院感染管理相关规范及负压病房建设标准为评价依据，反映环境对空气传播风险的物理屏障水平。",
        "医疗空间实现空气有效交换与净化的环境保障水平，涵盖自然通风、机械通风及净化空调系统等多种形式，旨在反映空间通过稀释或过滤清除空气中病原体的能力。",
    ],
    "L3_B2": [
        "感染者在医疗活动中其行为是否能够被有效管理和限制，行为不可控可能增加体液飞溅、气溶胶产生及环境污染的风险。",
        "医护人员在诊疗和护理过程中接触感染者血液、分泌物或排泄物的可能性，该风险直接关系到经皮或黏膜暴露的发生。",
        "单位时间或空间内感染者聚集的程度，感染者高度集中可能显著增加环境污染负荷 and 医护人员的整体暴露风险。",
        "感染者院内或院际移动过程的风险及管理完备性，该过程可能扩大病原体污染范围并增加医护人员的防控难度。",
    ],
    "L3_B3": [
        "临床物资（含无菌敷料等）及环境表面被病原体污染的程度，其污染水平直接影响医护人员通过间接接触发生感染的风险。",
        "空气中携带病原体的气溶胶或颗粒物对医护人员造成吸入性暴露的可能性，尤其在密闭或通风不足环境中更为突出。",
        "污染医疗废物在处置过程中导致暴露或二次污染的可能性，其直接关系到医护人员的职业安全。",
        "医疗器械（含复用器械）及诊疗设备被病原体污染的程度，其污染水平直接影响医患双方通过诊疗媒介发生交叉感染的风险。",
    ],
    "L3_C1": [
        "医护人员在实施诊疗、护理或侵入性操作过程中直接接触病原体的可能性，操作类型是实现精准分级防护的依据。",
        "不同岗位因职责内容和工作方式不同而承受的病原体暴露水平，用以反映岗位本身的固有职业暴露风险。",
        "医护人员在高感染风险环境中持续或累计工作的时间长度，暴露时间延长可能增加感染发生的概率。",
    ],
    "L3_C2": [
        "可能增加感染易感性或疾病严重性的慢性病或生理状态，该状况可能影响其对感染的易感性和耐受能力。",
        "医护人员机体对病原体感染的免疫防御水平，通过结合疫苗接种史、既往感染史等可获取信息，综合评估个体的自然免疫与获得性免疫状态，是决定感染发生及疾病严重程度的重要个体因素。"
    ],
    "L3_C3": [
        "个体防护装备在规格和尺寸上与医护人员身体特征的适配程度，匹配不良可能降低防护效果并增加暴露风险。",
        "佩戴个体防护装备后执行临床操作的便利性与精确性，灵活性不足影响操作安全与防护依从性。",
        "医护人员长时间使用个体防护装备引发的生理与心理不适感，该因素可能影响防护依从性。",
        "个体防护装备对医护人员个体生理特征、行为习惯及特殊需求的适配程度，其不足可能削弱实际防护效果。",
        "医护人员自身的健康状况（如心肺功能、过敏史等）对安全佩戴特定防护装备的允许程度，旨在评估个体是否存在因基础疾病导致无法持续、安全使用高等级防护用品的身体限制。",
    ],
}


# ============================================================
# 矩阵 UI 生成器
# ============================================================
def matrix_input(matrix_key: str, parent_title: str, items: list, defs: list = None):
    # 蓝色大号字体显示标题 (与整体协调，设为 24px)
    st.markdown(f"<h3 style='color: #1f77b4; font-size: 24px; margin-top: 30px;'>{parent_title} 的下属指标对比</h3>", unsafe_allow_html=True)

    if defs:
        with st.expander("📖 点击查看指标包含内容或含义说明"):
            for item_label, definition in zip(items, defs):
                st.markdown(f"**{item_label}**：{definition}")

    n = len(items)
    matrix = np.ones((n, n))
    pairwise_values = {}
    all_default = True  # 检测是否全是默认值 1

    for i in range(n):
        for j in range(i + 1, n):
            # 对比文字整体调小并统一为 18px 粗体，彻底解决像图片中最后一个字尴尬分行的问题
            st.markdown(f"""
            <div style='display: flex; justify-content: center; align-items: center; margin-top: 20px; margin-bottom: 5px;'>
                <div style='font-size: 18px; font-weight: bold; color: #1f77b4; text-align: right; width: 45%;'>{items[i]}</div>
                <div style='font-size: 15px; font-weight: bold; color: #888; text-align: center; width: 10%;'> VS </div>
                <div style='font-size: 18px; font-weight: bold; color: #1f77b4; text-align: left; width: 45%;'>{items[j]}</div>
            </div>
            """, unsafe_allow_html=True)

            choice = st.select_slider(
                "请滑动选择相对重要程度",
                options=SLIDER_OPTIONS,
                value="1 (同等重要)",
                key=f"{matrix_key}_{i}_{j}",
                label_visibility="collapsed"
            )
            
            if choice != "1 (同等重要)":
                all_default = False
                
            val = option_to_value(choice)
            matrix[i, j] = val
            matrix[j, i] = 1 / val
            pairwise_values[f"{i}_{j}"] = val

    cr = get_ahp_cr(matrix)
    is_valid = True

    # 判断防呆与合法性
    if n > 1 and all_default:
        st.warning("⚠️ 系统检测到该组指标您全部选择了默认的“1(同等重要)”。如果并非漏填，请勾选下方确认框：")
        confirm_all_1 = st.checkbox("☑️ 我确认这组指标确实同等重要", key=f"confirm_all_1_{matrix_key}")
        if confirm_all_1:
            st.success("✅ 已确认同等重要 (CR: 0.000)")
            is_valid = True
        else:
            is_valid = False
    elif cr >= 0.1:
        st.markdown(f"""
        <div style='background-color: #fff4e5; color: #d97706; padding: 12px; border-radius: 8px; border: 1px solid #fde6d8; font-size: 18px; margin-top: 10px;'>
            ⚠️ <strong>一致性提示：</strong> 当前判断矩阵的逻辑冲突偏大 (CR: {cr:.3f})，请微调您的打分使其小于 0.1，以确保结果的科学性。
        </div>
        """, unsafe_allow_html=True)
        is_valid = False
    else:
        st.success(f"✅ 一致性校验通过 (CR: {cr:.3f})")

    st.markdown("<hr style='border: 1px dashed #d3d3d3; margin: 30px 0;'>", unsafe_allow_html=True)

    # 记录到 session_state
    st.session_state.setdefault("matrices_data", {})
    st.session_state.setdefault("cr_results", {})
    st.session_state.setdefault("validity", {})
    
    st.session_state["matrices_data"][matrix_key] = {
        "title": f"{parent_title} 的下属指标对比",
        "items": items,
        "pairwise": pairwise_values,
        "matrix": matrix.tolist()
    }
    st.session_state["cr_results"][matrix_key] = cr
    st.session_state["validity"][matrix_key] = is_valid


# ============================================================
# 页面主体
# ============================================================

# --- 开头语 ---
st.markdown("""
<h1 style='text-align: center; font-size: 32px;'>医护人员感染性职业暴露风险评估体系构建</h1>
<h2 style='text-align: center; font-size: 24px; color: #555;'>——层次分析法（AHP）专家咨询问卷</h2>

**尊敬的专家：**

您好！首先向您在百忙之中抽出时间参与本次调查表示衷心的感谢！

为科学识别和评估医护人员在临床工作中面临的感染性职业暴露风险，构建适用于本院的“医护人员感染性职业暴露风险评估指标体系”，本课题组在前期文献研究与德尔菲专家咨询的基础上，已确立了由“病原体与相应疾病风险特征（A）”“环境暴露风险（B）”“个体风险与健康基础（C）”三个一级指标、13 个二级指标及 45 个三级指标组成的三级评价指标体系。为进一步确定各层级指标在风险评估中的相对重要程度（权重），本课题拟采用层次分析法（Analytic Hierarchy Process, AHP），邀请您根据自身的专业知识与临床实践经验，对同一上级指标下的各指标进行两两比较判断。

您的专业背景与丰富经验对本研究的科学性、实用性至关重要，恳请您结合实际工作情况，独立、审慎地填写本问卷。填写过程中如对指标含义存有疑问，请参见折叠面板中的“指标含义说明”。本问卷所填写内容仅用于本课题的学术研究，数据将进行匿名化处理，不作其他任何用途，请您放心填写。

再次感谢您的大力支持与悉心指导！  
<div style='text-align: right; font-weight: bold; font-size: 18px; line-height: 1.6;'>
    课题组敬上<br>
    2026年7月7日
</div>
""", unsafe_allow_html=True)
st.divider()

# --- 专家基本信息 ---
st.subheader("专家基本信息")
expert_name = st.text_input("专家姓名 *", key="expert_name", placeholder="请输入您的姓名")
st.caption(f"填表日期：{FIXED_DATE_STR}（第 {ROUND_NO} 轮专家咨询）")
st.divider()

# --- 填表说明 ---
st.markdown("""
### 一、填表说明
1. 本问卷需要您对隶属于同一上级指标的各指标，两两比较其相对重要程度。
2. **判断标度说明**：采用国际通用的 1—9 标度法。
   - **1 (同等重要)**：表示两个指标相比，具有同样重要性。
   - **3 (稍微重要)**：表示两个指标相比，前者比后者稍微重要.
   - **5 (明显重要)**：表示两个指标相比，前者比后者明显重要.
   - **7 (强烈重要)**：表示两个指标相比，前者比后者强烈重要.
   - **9 (极端重要)**：表示两个指标相比，前者比后者极端重要.
   - **2、4、6、8**：表示上述相邻判断的中间值。
3. **填写方法（重要⭐）**：我们使用了左右平衡滑块。滑动条停留在中间（1）代表两者**同等重要**。若您认为**左侧**指标比**右侧**重要，请向**左**滑动；若认为**右侧**指标比**左侧**重要，请向**右**滑动。数字越大代表重要程度差异越显著。
   - 例如：“左侧 VS 右侧”的比较中，如果将滑块拖至 **“左3(稍重要)”**，代表：**左侧指标比右侧指标稍微重要**。
4. 请您结合临床实际及个人专业经验独立判断；如某组指标数量较多、判断确有困难，可优先比较差异明显的指标对，再逐一补齐其余。
""")
st.divider()

# --- 二、开始正式问卷 ---
st.markdown("### 二、判断矩阵调查表")

# 1. 一级指标
matrix_input("L1", "总目标（医护人员感染性职业暴露风险）", L1_ITEMS, L1_DEFS)

# 2. 二级指标
matrix_input("L2_A", "A.病原体与相应疾病风险特征", L2_A_ITEMS, L2_A_DEFS)
matrix_input("L2_B", "B.环境暴露风险", L2_B_ITEMS, L2_B_DEFS)
matrix_input("L2_C", "C.个体风险与健康基础", L2_C_ITEMS, L2_C_DEFS)

# 3. 三级指标 (A系列)
matrix_input("L3_A1", "A1.病原体基础属性", ["A1.1 病原体生物危害分级", "A1.2 病原体谱构成", "A1.3 病原体载量"], LEVEL3_DEFS["L3_A1"])
matrix_input("L3_A2", "A2.病原体变异与进化潜力", ["A2.1 分子进化情况", "A2.2 遗传距离"], LEVEL3_DEFS["L3_A2"])
matrix_input("L3_A3", "A3.传播特性与潜力", ["A3.1 传播途径与多途径风险", "A3.2 基本传染数R0/有效传染数Re", "A3.3 无症状/潜伏期传播能力"], LEVEL3_DEFS["L3_A3"])
matrix_input("L3_A4", "A4.环境存活能力", ["A4.1 消杀敏感性", "A4.2 环境稳定性"], LEVEL3_DEFS["L3_A4"])
matrix_input("L3_A5", "A5.疾病临床严重性", ["A5.1 病例住院率", "A5.2 重症率", "A5.3 病死率"], LEVEL3_DEFS["L3_A5"])
matrix_input("L3_A6", "A6.临床防治有效性", ["A6.1 早期诊疗可行性", "A6.2 预防接种可及性与有效性", "A6.3 特异性治疗药物可及性与有效性", "A6.4 病原体耐药性"], LEVEL3_DEFS["L3_A6"])

# 4. 三级指标 (B与C系列)
matrix_input("L3_B1", "B1.布局与通风", ["B1.1 功能分区合理性", "B1.2 流线设置合理性", "B1.3 空气质量与气流组织", "B1.4 通风保障充分性"], LEVEL3_DEFS["L3_B1"])
matrix_input("L3_B2", "B2.感染者风险", ["B2.1 感染者行为可控性", "B2.2 感染者体液暴露风险", "B2.3 感染者集中度", "B2.4 感染者移动/转运"], LEVEL3_DEFS["L3_B2"])
matrix_input("L3_B3", "B3.物品与环境污染风险", ["B3.1 物资与环境表面污染风险", "B3.2 空气颗粒暴露风险", "B3.3 医疗废物传染风险", "B3.4 医疗器械与设备污染风险"], LEVEL3_DEFS["L3_B3"])

matrix_input("L3_C1", "C1.工作场景暴露风险", ["C1.1 操作暴露风险", "C1.2 岗位暴露强度", "C1.3 工作场景暴露时间"], LEVEL3_DEFS["L3_C1"])
matrix_input("L3_C2", "C2.个体生理易感性", ["C2.1 基础健康状况", "C2.2 免疫能力"], LEVEL3_DEFS["L3_C2"])
matrix_input("L3_C3", "C3.个体防护装备的身体适配性", ["C3.1 尺寸匹配性", "C3.2 操作灵活性", "C3.3 舒适耐受性", "C3.4 个体特征适配性", "C3.5 基础健康适宜性"], LEVEL3_DEFS["L3_C3"])


# ============================================================
# 提交区与结束语
# ============================================================
st.markdown("""
### 结束语
至此，本次问卷调查内容全部结束。衷心感谢您在繁忙的临床与科研工作之余，耐心、细致地完成本次两两比较判断！您所提供的专业判断，将通过层次分析法计算得出各级指标的权重系数，并结合一致性检验加以校核，为构建科学、合理的“医护人员感染性职业暴露风险评估指标体系”提供重要依据，对提升本院及同类专科医院医护人员职业防护水平具有切实意义。

若后续需要根据一致性检验结果对个别判断进行复核或修正，我们可能会再次与您联系，恳请您予以理解和支持。您的每一份意见都弥足珍贵，再次向您致以最诚挚的谢意！  
<div style='text-align: right; font-weight: bold; font-size: 18px; line-height: 1.6;'>
    课题组 敬上<br>
    2026年7月7日
</div>
""", unsafe_allow_html=True)

st.markdown("---")

validity = st.session_state.get("validity", {})
matrices_data = st.session_state.get("matrices_data", {})
cr_results = st.session_state.get("cr_results", {})

# 提取未填写完整或者冲突过大的矩阵
failed_titles = [matrices_data[k]["title"] for k, is_valid in validity.items() if not is_valid]
name_filled = bool(expert_name and expert_name.strip())

if failed_titles:
    st.markdown(
        f"""
        <div style='background-color: #fff4e5; color: #d97706; padding: 15px; border-radius: 8px; border: 1px solid #fde6d8; font-size: 18px; line-height: 1.5; margin-bottom: 20px;'>
            <strong>⚠️ 无法提交！以下模块存在未答、需确认“同等重要” 或 逻辑冲突（CR ≥ 0.1），请返回上方修改或确认：</strong><br><br>
            {"<br>".join(f"• {t}" for t in failed_titles)}
        </div>
        """, unsafe_allow_html=True
    )

if not name_filled:
    st.info("请在问卷顶部填写专家姓名后再提交。")

can_submit = name_filled and len(failed_titles) == 0

if st.button("✅ 完成问卷提交", disabled=not can_submit, type="primary", use_container_width=True):
    save_submission(expert_name.strip(), ROUND_NO, matrices_data, cr_results)
    st.balloons()
    st.success("感谢您的专业参与，数据已成功记录！")

if not can_submit:
    st.caption("（提交按钮在所有条件满足前保持禁用状态：姓名已填 且 全部矩阵均已有效打分或确认）")


# ============================================================
# 管理员数据导出（课题组专用）
# ============================================================
with st.sidebar:
    st.subheader("数据管理（课题组专用）")
    passcode = st.text_input("管理员口令", type="password", key="admin_passcode")
    if passcode == ADMIN_PASSCODE:
        df = load_all_submissions()
        st.write(f"已收集 {len(df)} 份有效问卷")
        st.dataframe(df[["id", "expert_name", "round_no", "submit_time"]], use_container_width=True)
        if len(df) > 0:
            csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇️ 下载全部原始数据（CSV）",
                data=csv_bytes,
                file_name=f"ahp_responses_round{ROUND_NO}.csv",
                mime="text/csv",
            )
            st.caption("注：导出的JSON数据内已直接生成 `matrix` 格式，可直接供算法读入做权重计算。")
    elif passcode:
        st.error("口令错误")
