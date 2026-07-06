import streamlit as st
import numpy as np

# AHP 计算函数
def get_ahp_cr(matrix):
    n = matrix.shape[0]
    # 使用 numpy 计算特征值
    eigenvalues, _ = np.linalg.eig(matrix)
    lambda_max = np.max(eigenvalues).real
    if n > 1:
        CI = (lambda_max - n) / (n - 1)
        # RI 值参考: n=1 to 10
        RI = [0, 0, 0.58, 0.90, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49]
        CR = CI / RI[n-1] if n <= 10 else 0
        return CR
    return 0

# 矩阵 UI 生成器
def matrix_input(matrix_key, title, items):
    st.markdown(f"### {title}")
    n = len(items)
    # 创建对角矩阵
    matrix = np.ones((n, n))
    
    # 使用两两对比的滑块
    for i in range(n):
        for j in range(i + 1, n):
            val = st.slider(f"{items[i]} vs {items[j]}", 1, 9, 1, key=f"{matrix_key}_{i}_{j}")
            matrix[i, j] = val
            matrix[j, i] = 1 / val
    
    cr = get_ahp_cr(matrix)
    if cr < 0.1:
        st.success(f"✅ 一致性校验通过 (CR: {cr:.3f})")
    else:
        st.error(f"❌ 逻辑冲突过大 (CR: {cr:.3f})，请调整打分，使其小于 0.1")
    st.divider()

st.title("专家德尔菲-AHP调查问卷")
st.write("请专家根据重要性进行两两比较（1=同等重要，9=极端重要）")

# --- 1. 一级指标 ---
matrix_input("L1", "一级指标对比", 
             ["A.病原体与相应疾病风险特征", "B.暴露环境风险", "C.个体风险与健康基础"])

# --- 2. 二级指标 ---
matrix_input("L2_A", "针对【A.病原体与相应疾病风险特征】的二级指标对比", 
             ["A1.病原体基础属性", "A2.病原体变异与进化潜力", "A3.传播特性与潜力", "A4.环境存活能力", "A5.疾病临床严重性", "A6.临床防治有效性"])
matrix_input("L2_B", "针对【B.暴露环境风险】的二级指标对比", 
             ["B1.布局与通风", "B2.感染者风险", "B3.物品与环境污染风险"])
matrix_input("L2_C", "针对【C.个体风险与健康基础】的二级指标对比", 
             ["C1.工作场景暴露风险", "C2.个体生理易感性", "C3.个体防护装备的身体适配性"])

# --- 3. 三级指标 (A系列) ---
matrix_input("L3_A1", "A1 下属指标对比", ["A1.1 病原体生物危害分级", "A1.2 病原谱构成", "A1.3 病原体载量"])
matrix_input("L3_A2", "A2 下属指标对比", ["A2.1 分子进化情况", "A2.2 遗传距离"])
matrix_input("L3_A3", "A3 下属指标对比", ["A3.1 传播途径与多途径风险", "A3.2 基本传染数Ra/有效传染数Re", "A3.3 无症状/潜伏期传播能力"])
matrix_input("L3_A4", "A4 下属指标对比", ["A4.1 消杀敏感性", "A4.2 环境稳定性"])
matrix_input("L3_A5", "A5 下属指标对比", ["A5.1 病例住院率", "A5.2 重症率", "A5.3 病死率"])
matrix_input("L3_A6", "A6 下属指标对比", ["A6.1 早期诊疗可行性", "A6.2 预防接种可及性与有效性", "A6.3 特异性治疗药物可及性与有效性", "A6.4 病原体耐药性"])

# --- 4. 三级指标 (B与C系列) ---
matrix_input("L3_B1", "B1 下属指标对比", ["B1.1 功能分区合理性", "B1.2 流线设置合理性", "B1.3 空气质量与气流组织", "B1.4 通风保障充分性"])
matrix_input("L3_B2", "B2 下属指标对比", ["B2.1 感染者行为可控性", "B2.2 感染者体液暴露风险", "B2.3 感染者集中度", "B2.4 感染者移动/转运"])
matrix_input("L3_B3", "B3 下属指标对比", ["B3.1 物资与环境表面污染风险", "B3.2 空气颗粒暴露风险", "B3.3 医疗废物传染风险", "B3.4 医疗器械与设备污染风险"])

matrix_input("L3_C1", "C1 下属指标对比", ["C1.1 操作暴露风险", "C1.2 岗位暴露强度", "C1.3 工作场景暴露时间"])
matrix_input("L3_C2", "C2 下属指标对比", ["C2.1 基础健康状况", "C2.2 免疫能力"])
matrix_input("L3_C3", "C3 下属指标对比", ["C3.1 尺寸匹配性", "C3.2 操作灵活性", "C3.3 舒适耐受性", "C3.4 个体特征适配性", "C3.5 基础健康适宜性"])

if st.button("完成问卷提交"):
    st.balloons()
    st.success("感谢您的专业参与，数据已成功记录！")