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
FIXED_DATE_STR = "2026年7月7日"    # 第三轮统一填表日期（无需专家选择）
ADMIN_PASSCODE = "admin123"       # 管理员导出数据口令，建议部署前修改

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
# AHP 计算函数
# ============================================================
def get_ahp_cr(matrix: np.ndarray) -> float:
    """计算一致性比率 CR。n<=2 时判断矩阵在数学上必然完全一致，CR 恒为 0。"""
    n = matrix.shape[0]
    if n <= 2:
        return 0.0

    eigenvalues = np.linalg.eigvals(matrix)
    lambda_max = np.max(eigenvalues.real)
    CI = (lambda_max - n) / (n - 1)

    # 平均随机一致性指标 R.I.（Saaty 标准表，n=1~10）
    RI_TABLE = [0, 0, 0.58, 0.90, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49]
    RI = RI_TABLE[n - 1] if n <= len(RI_TABLE) else 1.49
    if RI == 0:
        return 0.0

    cr = CI / RI
    return max(cr, 0.0)  # 避免浮点误差导致的极小负值


# ============================================================
# 三级指标含义说明（点击展开查看，不常驻显示）
# ============================================================
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
        "单位时间或空间内感染者聚集的程度，感染者高度集中可能显著增加环境污染负荷和医护人员的整体暴露风险。",
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
        "医护人员机体对病原体感染的免疫防御水平，通过结合疫苗接种史、既往感染史等可获取信息，综合评估个体的自然免疫与获得性免疫状态，是决定感染发生及疾病严重程度的重要个体因素。",
    ],
    "L3_C3": [
        "个体防护装备在规格和尺寸上与医护人员身体特征的适配程度，匹配不良可能降低防护效果并增加暴露风险。",
        "佩戴个体防护装备后执行临床操作的便利性与精确性，灵活性不足影响操作安全与防护依从性。",
        "医护人员长时间使用个体防护装备引发的生理与心理不适感，该因素可能影响防护依从性。",
        "个体防护装备对医护人员个体生理特征、行为习惯及特殊需求的适配程度，其不足可能削弱实际防护效果。",
        "医护人员自身的健康状况（如心肺功能、过敏史等）对安全佩戴特定防护装备的允许程度，旨在评估个体是否存在因基础疾病导致无法持续、安全使用高等级防护用品的身体限制。",
    ],
}

# 一级 / 二级指标的简要说明（较短，常驻显示，无需折叠）
LEVEL1_DESC = {
    "A.病原体与相应疾病风险特征": "病原体自身生物学特性及所致疾病严重程度、可防治性等内在风险要素。",
    "B.暴露环境风险": "工作环境布局通风条件、感染者相关状况及物品环境污染水平所形成的外部暴露风险。",
    "C.个体风险与健康基础": "医护人员个体工作场景暴露特征、生理易感性及防护装备适配情况等个体层面因素。",
}

LEVEL2_DESC = {
    "A1.病原体基础属性": "生物危害分级、病原体谱构成及载量水平。",
    "A2.病原体变异与进化潜力": "分子水平持续变异及不同株系间遗传距离。",
    "A3.传播特性与潜力": "传播途径与多途径风险、传染数及无症状潜伏期传播能力。",
    "A4.环境存活能力": "消杀敏感性及环境稳定性。",
    "A5.疾病临床严重性": "住院率、重症率及病死率。",
    "A6.临床防治有效性": "早期诊疗、疫苗与治疗药物可及性有效性及病原体耐药性。",
    "B1.布局与通风": "功能分区、流线设置、空气质量与气流组织及通风保障。",
    "B2.感染者风险": "感染者行为可控性、体液暴露风险、集中度及移动转运风险。",
    "B3.物品与环境污染风险": "物资环境表面、空气颗粒、医疗废物及医疗器械设备污染风险。",
    "C1.工作场景暴露风险": "操作暴露风险、岗位暴露强度及暴露时间。",
    "C2.个体生理易感性": "基础健康状况及免疫能力。",
    "C3.个体防护装备的身体适配性": "尺寸匹配、操作灵活、舒适耐受、个体特征及基础健康适宜性。",
}


# ============================================================
# 矩阵 UI 生成器
# ============================================================
def matrix_input(matrix_key: str, title: str, items: list, level3_defs: list = None, brief_desc: str = None):
    st.markdown(f"### {title}")

    if brief_desc:
        st.caption(brief_desc)

    if level3_defs:
        with st.expander("📖 点击查看三级指标含义说明"):
            for item_label, definition in zip(items, level3_defs):
                st.markdown(f"**{item_label}**：{definition}")

    n = len(items)
    matrix = np.ones((n, n))
    pairwise_values = {}

    for i in range(n):
        for j in range(i + 1, n):
            val = st.slider(f"{items[i]} vs {items[j]}", 1, 9, 1, key=f"{matrix_key}_{i}_{j}")
            matrix[i, j] = val
            matrix[j, i] = 1 / val
            pairwise_values[f"{i}_{j}"] = val

    cr = get_ahp_cr(matrix)

    # 记录到 session_state，供最终提交与后续统计使用
    st.session_state.setdefault("matrices_data", {})
    st.session_state.setdefault("cr_results", {})
    st.session_state["matrices_data"][matrix_key] = {
        "title": title,
        "items": items,
        "pairwise": pairwise_values,
    }
    st.session_state["cr_results"][matrix_key] = cr

    if cr < 0.1:
        st.success(f"✅ 一致性校验通过 (CR: {cr:.3f})")
    else:
        st.error(f"❌ 逻辑冲突过大 (CR: {cr:.3f})，请调整打分，使其小于 0.1")
    st.divider()


# ============================================================
# 页面主体
# ============================================================
st.set_page_config(page_title="医护人员感染性职业暴露风险评估——专家AHP问卷", layout="centered")

st.title("专家德尔菲-AHP调查问卷（第三轮）")
st.write("请专家根据重要性进行两两比较（1=同等重要，9=极端重要）")

# --- 专家基本信息（第三轮：仅需姓名，日期固定） ---
st.subheader("专家基本信息")
expert_name = st.text_input("专家姓名 *", key="expert_name", placeholder="请输入您的姓名")
st.caption(f"填表日期：{FIXED_DATE_STR}（第 {ROUND_NO} 轮专家咨询）")
st.divider()

# --- 1. 一级指标 ---
l1_items = ["A.病原体与相应疾病风险特征", "B.暴露环境风险", "C.个体风险与健康基础"]
st.markdown("#### 一级指标含义")
for it in l1_items:
    st.caption(f"**{it}**：{LEVEL1_DESC.get(it, '')}")
matrix_input("L1", "一级指标对比", l1_items)

# --- 2. 二级指标 ---
l2_a = ["A1.病原体基础属性", "A2.病原体变异与进化潜力", "A3.传播特性与潜力", "A4.环境存活能力", "A5.疾病临床严重性", "A6.临床防治有效性"]
l2_b = ["B1.布局与通风", "B2.感染者风险", "B3.物品与环境污染风险"]
l2_c = ["C1.工作场景暴露风险", "C2.个体生理易感性", "C3.个体防护装备的身体适配性"]

matrix_input("L2_A", "针对【A.病原体与相应疾病风险特征】的二级指标对比", l2_a,
             brief_desc=" ／ ".join(f"{it}：{LEVEL2_DESC.get(it, '')}" for it in l2_a))
matrix_input("L2_B", "针对【B.暴露环境风险】的二级指标对比", l2_b,
             brief_desc=" ／ ".join(f"{it}：{LEVEL2_DESC.get(it, '')}" for it in l2_b))
matrix_input("L2_C", "针对【C.个体风险与健康基础】的二级指标对比", l2_c,
             brief_desc=" ／ ".join(f"{it}：{LEVEL2_DESC.get(it, '')}" for it in l2_c))

# --- 3. 三级指标 (A系列) ---
matrix_input("L3_A1", "A1 下属指标对比",
             ["A1.1 病原体生物危害分级", "A1.2 病原体谱构成", "A1.3 病原体载量"],
             level3_defs=LEVEL3_DEFS["L3_A1"])
matrix_input("L3_A2", "A2 下属指标对比",
             ["A2.1 分子进化情况", "A2.2 遗传距离"],
             level3_defs=LEVEL3_DEFS["L3_A2"])
matrix_input("L3_A3", "A3 下属指标对比",
             ["A3.1 传播途径与多途径风险", "A3.2 基本传染数R0/有效传染数Re", "A3.3 无症状/潜伏期传播能力"],
             level3_defs=LEVEL3_DEFS["L3_A3"])
matrix_input("L3_A4", "A4 下属指标对比",
             ["A4.1 消杀敏感性", "A4.2 环境稳定性"],
             level3_defs=LEVEL3_DEFS["L3_A4"])
matrix_input("L3_A5", "A5 下属指标对比",
             ["A5.1 病例住院率", "A5.2 重症率", "A5.3 病死率"],
             level3_defs=LEVEL3_DEFS["L3_A5"])
matrix_input("L3_A6", "A6 下属指标对比",
             ["A6.1 早期诊疗可行性", "A6.2 预防接种可及性与有效性", "A6.3 特异性治疗药物可及性与有效性", "A6.4 病原体耐药性"],
             level3_defs=LEVEL3_DEFS["L3_A6"])

# --- 4. 三级指标 (B与C系列) ---
matrix_input("L3_B1", "B1 下属指标对比",
             ["B1.1 功能分区合理性", "B1.2 流线设置合理性", "B1.3 空气质量与气流组织", "B1.4 通风保障充分性"],
             level3_defs=LEVEL3_DEFS["L3_B1"])
matrix_input("L3_B2", "B2 下属指标对比",
             ["B2.1 感染者行为可控性", "B2.2 感染者体液暴露风险", "B2.3 感染者集中度", "B2.4 感染者移动/转运"],
             level3_defs=LEVEL3_DEFS["L3_B2"])
matrix_input("L3_B3", "B3 下属指标对比",
             ["B3.1 物资与环境表面污染风险", "B3.2 空气颗粒暴露风险", "B3.3 医疗废物传染风险", "B3.4 医疗器械与设备污染风险"],
             level3_defs=LEVEL3_DEFS["L3_B3"])

matrix_input("L3_C1", "C1 下属指标对比",
             ["C1.1 操作暴露风险", "C1.2 岗位暴露强度", "C1.3 工作场景暴露时间"],
             level3_defs=LEVEL3_DEFS["L3_C1"])
matrix_input("L3_C2", "C2 下属指标对比",
             ["C2.1 基础健康状况", "C2.2 免疫能力"],
             level3_defs=LEVEL3_DEFS["L3_C2"])
matrix_input("L3_C3", "C3 下属指标对比",
             ["C3.1 尺寸匹配性", "C3.2 操作灵活性", "C3.3 舒适耐受性", "C3.4 个体特征适配性", "C3.5 基础健康适宜性"],
             level3_defs=LEVEL3_DEFS["L3_C3"])

# ============================================================
# 提交区：一致性未通过或姓名未填时禁止提交
# ============================================================
st.markdown("---")
st.subheader("提交问卷")

cr_results = st.session_state.get("cr_results", {})
matrices_data = st.session_state.get("matrices_data", {})

failed_titles = [matrices_data[k]["title"] for k, v in cr_results.items() if v >= 0.1]
name_filled = bool(expert_name and expert_name.strip())

if failed_titles:
    st.error(
        "以下判断矩阵尚未通过一致性检验（CR ≥ 0.1），请返回上方调整打分后再提交：\n\n"
        + "\n".join(f"- {t}" for t in failed_titles)
    )

if not name_filled:
    st.info("请填写专家姓名后再提交问卷。")

can_submit = name_filled and len(failed_titles) == 0

if st.button("✅ 完成问卷提交", disabled=not can_submit, type="primary"):
    save_submission(expert_name.strip(), ROUND_NO, matrices_data, cr_results)
    st.balloons()
    st.success("感谢您的专业参与，数据已成功记录！")

if not can_submit:
    st.caption("（提交按钮在所有条件满足前保持禁用状态：姓名已填写 且 全部判断矩阵一致性检验通过）")


# ============================================================
# 管理员数据导出（供课题组统计分析使用，非专家填写内容）
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
    elif passcode:
        st.error("口令错误")
