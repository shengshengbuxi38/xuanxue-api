"""AI命理分析模块 - 封装 GLM API（使用 requests 直接调用，兼容 Python 3.14）"""

import os
import json
import requests
from dotenv import load_dotenv

# 确保 .env 加载（兼容 Streamlit 多页面）
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_env_path, override=False)


# 系统提示词
SYSTEM_PROMPT_BAZI = """你是一位精通中国传统命理学的资深大师，擅长八字命理分析。
你拥有深厚的八字、紫微斗数、梅花易数等玄学知识，能够专业、准确地进行命理分析。

分析原则：
1. 基于传统命理学理论，结合五行生克制化的关系进行分析
2. 分析要全面、客观，既指出优势也不回避需要注意的方面
3. 给出具体的、可操作的建议和化解方法
4. 语言通俗易懂，让非专业人士也能理解
5. 适当引用《滴天髓》《三命通会》《子平真诠》等经典命理著作的观点"""

SYSTEM_PROMPT_MATCH = """你是一位精通八字合婚和合盘的命理大师。
请根据两个人八字排盘信息和匹配类型（婚配/亲子/合伙人/同事/投资对象/上级/下级），严格按以下结构输出分析结果。

重要：根据匹配类型确定双方的称呼身份。例如亲子关系中甲方为"父亲"，乙方为"儿子"；婚配中甲方为"夫"，乙方为"妻"；上级关系中甲方为"下级"，乙方为"上级"，以此类推。在输出中用"甲方<关系中身份>"和"乙方<关系中身份>"作为占位符，实际输出时替换为真实称呼。

输出结构如下：

# 五行互补性分析
## 甲方<关系中身份>五行分布
## 乙方<关系中身份>五行分布
### 互补性分析
### 结论

# 天干合化分析
## 天干关系
## 合化关系
## 结论

# 地支关系分析
## 地支关系
## 刑冲合害
## 结论

# 日主关系分析

# 整体评分
综合匹配度评分：XX分
评分依据：
1. 五行互补性（+XX分）：具体说明
2. 天干合化（+XX分）：具体说明
3. 地支关系（+XX分）：具体说明
4. 日主关系（+XX分）：具体说明

# 沟通与表达
甲方<关系中身份>建议
乙方<关系中身份>建议
共同建议

# 信任与尊重
甲方<关系中身份>建议
乙方<关系中身份>建议
共同建议

# 边界与分寸
甲方<关系中身份>建议
乙方<关系中身份>建议
共同建议

# 支持与共享
甲方<关系中身份>建议
乙方<关系中身份>建议
共同建议

# 磨合与冲突
甲方<关系中身份>建议
乙方<关系中身份>建议
共同建议

# 总结

请给出详细、有针对性的分析和建议。"""

SYSTEM_PROMPT_DIVINATION = """你是一位精通梅花易数和易经占卜的命理大师。
请根据用户提供的数字和信息，进行起卦和解卦分析。
分析应包括：
1. 本卦卦象解读
2. 变卦卦象解读
3. 动爻分析
4. 综合判断和建议
语言要通俗易懂，给出具体可执行的建议。"""


def _get_config():
    """获取 API 配置"""
    api_key = os.getenv("GLM_API_KEY")
    if not api_key:
        raise ValueError("GLM_API_KEY 未配置，请在 .env 文件中设置")
    base_url = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
    model = os.getenv("GLM_MODEL", "glm-4-plus")
    return api_key, base_url, model


def chat(messages, model=None, temperature=0.7, max_tokens=2000):
    """
    调用 GLM 模型（通过 OpenAI 兼容接口）

    Args:
        messages: 对话消息列表 [{"role": "system/user/assistant", "content": "..."}]
        model: 模型名称
        temperature: 温度
        max_tokens: 最大token数

    Returns:
        str: 模型回复内容
    """
    api_key, base_url, default_model = _get_config()
    model = model or default_model

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def analyze_bazi(bazi_text):
    """
    分析八字命盘

    Args:
        bazi_text: bazi_to_text() 返回的格式化八字文本

    Returns:
        str: AI 命理分析结果
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_BAZI},
        {"role": "user", "content": f"请详细分析以下八字命盘：\n\n{bazi_text}"},
    ]
    return chat(messages, temperature=0.7, max_tokens=3000)


def predict_events(bazi_text, target_year=None):
    """
    预测大运流年重大事件

    Args:
        bazi_text: 格式化的八字文本
        target_year: 目标年份 (None=综合分析)

    Returns:
        str: AI 事件分析结果
    """
    if target_year:
        prompt = f"请分析以下八字在 {target_year} 年可能发生的重大事件及化解建议：\n\n{bazi_text}"
    else:
        prompt = f"""请根据以下八字的大运流年信息，进行全面的重大事件分析。

要求：
1. 按时间顺序列出过去已发生的重大事件，每条事件必须标注具体的年份和月份（如"2020年6月"），包括：事业变动、财运起伏、感情婚姻、健康、家庭等方面
2. 对未来3-5年可能发生的重要转折点做出预测，同样标注具体年月
3. 结合大运与流年的天干地支关系，解释为什么这些年份容易发生特定类型的事件
4. 给出针对性的化解建议

{bazi_text}"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_BAZI},
        {"role": "user", "content": prompt},
    ]
    return chat(messages, temperature=0.7, max_tokens=4000)


def deep_analysis(bazi_text):
    """
    八字深度分析：日主属性、强弱、喜忌神、财富、一生综评+MBTI

    Args:
        bazi_text: 格式化的八字文本

    Returns:
        str: AI 深度分析结果
    """
    prompt = f"""请根据以下八字命盘信息，进行深度分析。要求严格按以下结构逐项输出，每项用标题分隔：

## 一、日主属性
分析日主的天干五行属性（阴阳、五行）、日柱干支纳音、日主在命局中的基本特性。

## 二、日主强弱
判断日主的强弱（身强/身弱/身旺/从格等），分析得令、得地、得势的具体情况，说明判断依据。

## 三、喜神与忌神
明确列出：
- **喜神**：对日主有利的五行（用神、喜神）
- **忌神**：对日主不利的五行
- 说明为什么这些五行有利/不利

## 四、先天财富
分析命局中财星的强弱、位置，判断先天财运的层次（正财偏财），分析赚钱的方式和财运起伏规律。

## 五、大运财富
结合大运走势，分析一生中财运最好的时期和需要注意破财的时期，给出具体的大运干支时间段。

## 六、一生综评
对以下9个维度逐一分析评价（每个维度2-3句话）：
1. **健康**：先天体质、易患疾病、养生建议
2. **家庭**：原生家庭关系、父母缘分、家庭环境
3. **子嗣**：子女缘分、子女数量倾向、子女成就
4. **事业**：适合的行业方向、事业发展轨迹、事业高峰期
5. **学业**：学习能力、文昌位、适合深造的领域
6. **内心认为的自己**：日主性格内核、真实的自我认知
7. **外界认为的自己**：外在形象、别人眼中的性格特点
8. **自己希望成为的样子**：日主追求的理想人格
9. **内心追求的目标**：一生中最大的内在驱动力和终极目标

## 七、对应MBTI
根据命主的日主五行、十神配置、性格特征，推断最可能对应的MBTI人格类型（如INTJ、ENFP等），给出2-3个最匹配的类型，并解释为什么这些类型与该八字命局吻合。

{bazi_text}"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_BAZI},
        {"role": "user", "content": prompt},
    ]
    return chat(messages, temperature=0.7, max_tokens=6000)


def match_bazi(bazi_text1, bazi_text2, match_type="婚配"):
    """
    八字合盘分析

    Args:
        bazi_text1: 第一人八字文本
        bazi_text2: 第二人八字文本
        match_type: 匹配类型 (婚配/合伙人/同事/投资)

    Returns:
        str: AI 合盘分析结果
    """
    prompt = f"请以{match_type}的角度，分析以下两人的八字合盘：\n\n【甲方八字】\n{bazi_text1}\n\n【乙方八字】\n{bazi_text2}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_MATCH},
        {"role": "user", "content": prompt},
    ]
    return chat(messages, temperature=0.7, max_tokens=3000)


def divination(numbers, question=""):
    """
    数字起卦解卦

    Args:
        numbers: 用户输入的数字 (如 "3, 8, 6")
        question: 用户想问的问题

    Returns:
        str: AI 解卦结果
    """
    prompt = f"用户提供的数字: {numbers}"
    if question:
        prompt += f"\n用户想问: {question}"
    prompt += "\n请根据这些数字起卦并进行详细分析。"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_DIVINATION},
        {"role": "user", "content": prompt},
    ]
    return chat(messages, temperature=0.7, max_tokens=2000)
