# 对话生成流程说明

本文档描述 `agent/main.py` 执行时的完整对话生成逻辑，对应当前代码的三层循环、每轮模型调用链、上下文注入来源与落盘产物。

- 适用文件：`agent/main.py`、`agent/memory.py`、`agent/initialization.py`、`agent/evaluation.py`
- 运行方式：在仓库根目录执行 `uv run python agent/main.py`
- 语言与目录：由 `api_config.json` 的 `response_language`（`zh` / `en`）决定，下文的 `<lang>` 即该值

---

## 1. 总体结构

对话生成是一个单进程、纯顺序执行的离线模拟器，没有并发、没有服务端，全部状态通过 JSON 文件读写。

```
患者（100 位）  →  会谈（默认 6 次）  →  轮次（默认上限 8 轮）  →  每轮 1 次患者发言 + 1 次医生发言
```

每完成一次"患者发言 + 医生回复"，系统会写入对话、决策依据、情绪标签三类产物，并判断是否结束本会谈。

---

## 2. 启动阶段

模块加载时完成配置与客户端初始化：

```python
# agent/main.py
config = StrictMemoryManager().get_config()   # 读取根目录 api_config.json
client = OpenAI(base_url=..., api_key=...)
```

`StrictMemoryManager.__init__` 在此时创建产物目录：

```
save_data/<lang>/
eval_data/<lang>/
```

`if __name__ == "__main__"` 分支创建 `AutoDialogueRunner`：

| 步骤 | 行为 | 说明 |
|---|---|---|
| 1 | `TherapistAgent()` | 持有 memory_manager、initializer、evaluator |
| 2 | `initializer._load_client_record()` | 读取 `client_records_translate_<lang>.json`，回退旧名 `client_records_translate.json` |
| 3 | `initializer._get_initial_record(pid)` | 从 `medical information` 中抽出五个字段，构成内存病历视图 |
| 4 | 结果存入 `self.patient_records` | 仅内存，不写盘；患者档案在首次进入会谈时落盘 |

病历查找顺序：`agent/<stem>_<lang>.json` → `agent/<stem>.json` → 仓库根目录 `<stem>_<lang>.json` → 仓库根目录 `<stem>.json`。

---

## 3. 主循环

```
run(num_sessions=6, max_rounds_per_session=8)
  for patient_id in patient_records:                      # 第一层：患者
      patient_agent = PatientAgent(medical_record, pid)
          ├─ memory_manager = StrictMemoryManager()
          └─ _load_session_guides()                       # 读取该患者 6 条会谈引导
      for session_num in 1..num_sessions:                 # 第二层：会谈
          patient_agent.update_session(session_num)
          TherapistAgent.auto_conversation(...)           # 第三层：轮次
```

### 会话引导的加载

`PatientAgent._load_session_guides` 从 `new_data_translate_<lang>.json`（回退 `new_data_translate.json`）读取：

```
{ "<patient_id>": { "Conversation guidance": { "session_1": "...", ... } } }
```

处理规则：只保留 `session_` 前缀的键；若值中含冒号，则取第一个冒号后的内容（`v.split(":", 1)[1]`），因此引导文本本身不应包含冒号。

---

## 4. 会谈初始化（start_new_session）

每次进入新会谈时执行：

| 步骤 | 行为 | 模型调用 |
|---|---|---|
| 1 | 读 `save_data/<lang>/<pid>.json` | 无 |
| 2 | 档案缺失或 `patient_record` 为空 → 重新取病历并 `create_patient_record` 写盘 | 无 |
| 3 | `cross_session_evaluate(pid)` | 1 次 |
| 4 | `_determine_therapy_for_new_session(pid)` → 再次 `cross_session_evaluate` | 1 次（重复） |
| 5 | `add_session(pid, therapy)`，写入 `sessions.session_N = {therapy, dialogs: []}` | 无 |
| 6 | 生成开场白（按语言中英双语） | 无 |
| 7 | `_save_therapy_reason` 写入 `eval_data/<lang>/decision basis_<pid>.json` | 无 |

疗法决策规则：

- 首次会谈（无历史会话）：`select_initial_therapy(patient_record)`，直接依据病历推荐疗法。
- 后续会谈：`evaluate_therapy_progress(上一个 session)`，判断上一疗程是否有效，有效则维持、无效则更换。

注意：步骤 3 与步骤 4 会各计算一次同样的疗法评估，且第二步的 `reason for therapy` 会覆盖第一步写入的同名字段。这是当前代码行为，不是设计意图。

---

## 5. 单轮对话调用链

一次"患者发言 → 医生回复"共触发 12 次模型调用。

| # | 组件 | 方法 | 输出 | max_tokens | 用途 |
|---|---|---|---|---|---|
| ① | 患者 | `PatientAgent.generate_response` | `{"patient_response": "..."}` | 300 | 生成患者话术；同时写 `label_data` |
| ② | 医生 | `should_end_session` | `True` / `False` | 5 | 控制流：是否结束会谈 |
| ③ | 医生 | `evaluate_client_reaction` | `True` / `False` | 5 | 是否抗拒或偏题 |
| ④ | 医生 | `assess_emotion` | `{primary_emotion, emotional_intensity}` | 50 | 情绪与强度 |
| ⑤ | 医生 | `should_use_memory` | 摘要或固定句 | 110 | 历史记忆是否需要被引用 |
| ⑥ | 医生 | `get_current_stage` → `determine_treatment_stage` | 阶段分析段落 | 120 | 当前治疗阶段 |
| ⑦ | 医生 | `update_response_strategy` | `{strategy, strategy_text}` | 100 | 回复策略 |
| ⑧ | 医生 | `get_current_stage`（重复 ⑥） | 同上 | 120 | 仅供医生 prompt |
| ⑨ | 医生 | `should_use_memory`（重复 ⑤） | 同上 | 110 | 仅供医生 prompt |
| ⑩ | 医生 | `evaluate_client_reaction`（重复 ③） | 同上 | 5 | 仅供医生 prompt |
| ⑪ | 医生 | `update_response_strategy`（重复 ⑦） | 同上 | 100 | 仅供医生 prompt |
| ⑫ | 医生 | 回复生成 | 医生话术文本 | 150 | 最终对话内容 |

其中 ⑧⑨⑩⑪ 与 ③⑤⑥⑦ 参数完全相同，是 `process_patient_input` 与 `_generate_response` 各自独立计算的产物：前者用于写 `decision basis`，后者用于拼装医生 prompt。

### 执行顺序

```
patient.generate_response                     ①
  └─ _save_label_data                        写 label_data/<lang>/label_<pid>.json

therapist.process_patient_input
  ├─ add_dialog(patient)                     写 save_data
  ├─ should_end_session                      ②
  ├─ evaluate_client_reaction                ③
  ├─ assess_emotion                          ④
  ├─ should_use_memory                       ⑤
  ├─ get_current_stage                       ⑥
  ├─ update_response_strategy                ⑦
  ├─ _generate_response
  │    ├─ get_current_stage                  ⑧
  │    ├─ should_use_memory                  ⑨
  │    ├─ evaluate_client_reaction           ⑩
  │    ├─ update_response_strategy           ⑪
  │    └─ 医生话术                           ⑫
  ├─ add_dialog(doctor)                      写 save_data
  ├─ save_decision_data                      写 eval_data/decision basis
  └─ should_end → _end_current_session()
```

---

## 6. 上下文注入矩阵

| 上下文 | 来源 | 注入位置 | 长度特征 |
|---|---|---|---|
| 病历 `medical_record` | `client_records_translate*.json` | 患者 prompt | 固定 |
| 本次会谈引导 `session_guide` | `new_data_translate*.json` | 患者 prompt | 固定 |
| 全部历史对话 | `save_data/<lang>/<pid>.json` 的所有 `dialogs` | 患者 prompt | 随会话线性增长 |
| 本会谈对话 `session_memory` | 同上，仅当前 `session_N` | 医生 prompt | 随轮次线性增长 |
| 记忆摘要 `memory_result` | ⑤ / ⑨ | 医生 prompt、决策依据 | 约 50 字 |
| 情绪与强度 | ④ | 策略 prompt、医生 prompt、决策依据 | 固定 |
| 治疗阶段 | ⑥ / ⑧ | 医生 prompt、决策依据 | 约 80 字 |
| 策略与策略描述 | ⑦ / ⑪ | 医生 prompt、决策依据 | 固定 |
| 本会谈已用策略列表 | `eval_data/<lang>/decision basis_<pid>.json` | 策略 prompt | 随轮次增长 |
| 疗法 | `add_session` 时确定 | 医生 prompt、阶段 prompt、决策依据 | 固定 |

所有上下文均以原文拼接，没有摘要压缩或滑窗截断。

---

## 7. 产物结构

| 路径 | 内容 | 写入时机 |
|---|---|---|
| `save_data/<lang>/<pid>.json` | `patient_record`（五项病历字段）与 `sessions`（每会疗法 + 对话数组） | 首次开会谈、每次发言 |
| `eval_data/<lang>/decision basis_<pid>.json` | `reason for therapy` 与每轮 9 项决策依据 | 每次会谈开始、每轮医生决策后 |
| `label_data/<lang>/label_<pid>.json` | 每轮患者态度 `attitude` | 每次患者发言后 |

`decision basis` 单轮字段：`Memory Invoke`、`Whether to Reject or Deviate`、`Current Therapy`、`Current Stage`、`Primary Emotion`、`Emotional Intensity`、`Response Strategy`、`Strategy Description`、`Attitude`。

会话内对话以 `PATIENT: ...` / `DOCTOR: ...` 字符串形式顺序追加到 `sessions.session_N.dialogs`。

---

## 8. 语言与内部术语边界

`response_language` 影响：

| 环节 | `zh` 模式 | `en` 模式 |
|---|---|---|
| 患者、医生话术 | 中文 | 英文 |
| 开场问候、异常兜底句 | 中文 | 英文 |
| 记忆摘要 | 中文 | 英文 |
| 产物目录 | `save_data/zh` 等 | `save_data/en` 等 |
| 数据文件 | `*_<lang>.json` | `*_<lang>.json` |
| 策略名、治疗名、情绪枚举、阶段分析、疗法理由 | 英文 | 英文 |

内部术语保持英文，以便与论文口径及跨语言统计保持一致。

---

## 9. 会话结束条件

两个出口，先命中者生效：

1. `should_end_session` 返回 `True`：患者明确表达结束（prompt 中同时给出中英文示例）。
2. `dialog_count >= max_rounds_per_session`：达到轮次上限，强制结束并打印系统提示。

患者 prompt 要求"在第 4 至 5 轮主动表达结束"，因此正常情况下由第 1 个出口结束；`max_rounds` 是兜底。

---

## 10. 调用规模

默认参数下：

```
100 位患者 × 6 次会谈 × 约 4.5 轮 × 12 次调用 ≈ 3.2 万次模型调用
```

每次会谈另有 2 次疗法评估（首会为初始疗法选择）。全量运行耗时以小时计，建议先用小参数验证：

```python
simulator.run(num_sessions=1, max_rounds_per_session=3)
```

---

## 11. 已知设计问题

| 问题 | 位置 | 影响 |
|---|---|---|
| 每轮重复计算阶段、记忆、抗拒判断、策略 | `main.py` `process_patient_input` 与 `_generate_response` | 每轮多 4 次调用，约 33% 成本 |
| 每次会谈重复计算疗法评估 | `start_new_session` 与 `_determine_therapy_for_new_session` | 每会多 1 次调用，并覆盖 `reason for therapy` |
| 上下文全量拼接 | `_get_all_historical_dialogs`、`should_use_memory`、`determine_treatment_stage`、`session_memory` | 长会话 token 线性增长，可能超出上下文窗口 |
| 策略选项编号重复 | `evaluation.update_response_strategy` 的选项表（G/H/I 出现两次） | 可能影响策略分布统计 |
| 患者态度为随机值 | `random.choices([positive, negative], weights=[70, 30])` | `label_data` 记录的是随机值而非模型推导 |

---

## 12. 修改指引

| 需求 | 修改位置 |
|---|---|
| 调整轮次或会谈数 | `run()` 参数；患者 prompt 中"4 至 5 轮"的表述 |
| 增加或调整回复策略 | `evaluation.update_response_strategy` 的选项表 |
| 更换疗法决策依据 | `evaluation.select_initial_therapy`、`evaluate_therapy_progress` |
| 控制上下文长度 | `PatientAgent._get_all_historical_dialogs`、`session_memory` 的截断逻辑 |
| 新增落盘产物 | `memory.py` 的 `save_*` 方法，或在 `main.py` 的对应阶段追加写盘 |
| 切换中英文 | `api_config.json` 的 `response_language` |
| 消除重复调用 | 让 `_generate_response` 接收 `process_patient_input` 已算好的阶段、记忆、抗拒、策略结果 |

---

## 附录 A：各模型输入输出与判断示例

附录中的输出示例取自 `zh` 模式的冒烟运行，括号内为对应调用编号。

### A.1 总览

| # | 调用 | 输出形态 | 取值域 | 输出语言 |
|---|---|---|---|---|
| ① | 患者发言 | JSON | `patient_response` 文本 | 跟随 `response_language` |
| ② | 结束判断 | 布尔字面量 | `True` / `False` | 英文 |
| ③ | 抗拒判断 | 布尔字面量 | `True` / `False` | 英文 |
| ④ | 情绪识别 | JSON | 8 种情绪 + 强度 0~1 | 英文 |
| ⑤ | 记忆调用 | 文本 | 50 字摘要或固定句 | 跟随 `response_language` |
| ⑥ | 治疗阶段 | 文本 | 一段分析 | 英文 |
| ⑦ | 回复策略 | JSON | 策略名 + 策略描述 | 英文 |
| ⑫ | 医生回复 | 纯文本 | 无格式要求 | 跟随 `response_language` |
| S1 | 初始疗法 | 纯文本 | 标准疗法名 | 英文 |
| S2 | 疗程评估 | JSON | `new_therapy` + `reason` | 英文 |

### A.2 患者发言（①）

输入要点：

```text
You are a patient participating in psychological counseling.
  - This is your personal information: {病历}
  - This is round_{n} in your session_{m} with the counselor.
  - The conselor just said: {医生上一句}
  - Previous consultation conversation history record: {全部历史对话}
##Requirements:
1.Your speech should revolve around the guidance for this session: {session_guide}.
2.You must finish this session within 4 to 5 rounds strictly.
3.Your response should clearly reflect your attitude: positive / negative.
##Constraints:
Generate your response in Chinese. Your response should be no more than 60 characters.
```

输出示例：

```json
{"patient_response": "谢谢医生。我最近情绪很乱，产后抑郁让我很痛苦，希望能通过咨询找到内心的平静和方向。"}
```

判断逻辑：`attitude` 不由模型决定，而是代码按 70% positive / 30% negative 随机采样后写入 prompt，再写入 `label_data`。模型只负责把该态度演出来。

### A.3 结束判断（②）

输入要点：`Your task is to strictly judge whether the current session should be ended based on the patient's current words: {patient_input}.`

| 患者输入 | 输出 | 说明 |
|---|---|---|
| 今天先聊到这里吧，谢谢医生。 | `True` | 明确表达结束 |
| 我们下次再聊。 | `True` | 明确表达结束 |
| 我最近总是睡不好，脑子里很乱。 | `False` | 只是继续叙述 |
| 好，我回去试试看。 | `False` | 未表达结束意图 |

输出示例：

```text
True
```

### A.4 抗拒 / 偏题判断（③）

输入要点：判断患者是否拒绝当前话题、表现出不耐烦，或明显偏离咨询主题。

| 患者输入 | 输出 | 判定依据 |
|---|---|---|
| 我不想谈这个，换个话题吧。 | `True` | 直接拒绝 |
| 这些都没用，说了也白说。 | `True` | 明显不耐烦 |
| 对了，你玩股票吗？ | `True` | 突然引入无关话题 |
| 是的，我最近确实很焦虑。 | `False` | 正常回应 |

输出示例：

```text
False
```

结果用途：作为 ⑦ 的输入（Yes/No），并写入 `decision basis` 的 `Whether to Reject or Deviate`。

### A.5 情绪识别（④）

#### 完整提示词

以下为 Python 模板原文，发送给模型时 `{{` / `}}` 会渲染为单个花括号：

```python
prompt = f"""
##Role:
You are a professional and empathetic psychological counselor. 
Identify the primary emotion and assess its intensity in the patient's words.
##Criteria:
The patient words: {patient_input}.
1.	primary_emotion:
The primary emotion is the most intense one in the patient words. 
You can only choose one from the list: ["joy", "sadness", "anger", "fear", "disgust", "surprise", "trust","anticipation"].
2.	emotional_intensity:
The intensity of the emotion you identified above(a float number from 0 to 1, where 0 indicates no emotion and 1 indicates very intense emotion). Please retain one decimal place.
##Constraints:
Return your answer strictly in JSON format, like this:
{{
   "primary_emotion": "str",          
   "emotional_intensity": "float"     
}}
"""
```

调用参数：system message 为 `You are a professional psychological counselor.`，`temperature=0.3`，`max_tokens=50`。提示词全英文，输出语言与 `response_language` 无关。

#### 提示词约束

| 段落 | 约束 | 实际效果 |
|---|---|---|
| `##Role` | 设定为专业心理咨询师 | 判断贴近临床语境，而非通用文本分类 |
| `The patient words` | 唯一输入是当前一句患者话语 | 不注入病历与历史对话，只看这一句 |
| `primary_emotion` | 取话语中最强烈的一种，只能从 8 项中选一项 | 单选、固定枚举，便于后续统计 |
| `emotional_intensity` | 0~1 浮点，0 无情绪、1 极强，保留一位小数 | 与情绪标签组成二元组，供策略选择量化使用 |
| `##Constraints` | 严格返回 JSON，字段名固定 | 代码直接解析，不做自然语言抽取 |

#### 判断机制

提示词只给出判定原则，没有情绪定义，也没有 few-shot 示例，模型单轮直接给出结论，推理路径为：

```text
读取患者这句话
  → 识别情绪表达（词语、语气、事件性质）
  → 多种情绪并存时比较强度，取最强的一种
  → 映射到 8 个英文标签之一
  → 按表达强度折算 0~1 数值，保留一位小数
  → 输出 JSON
```

因为要求“直接出 JSON”且 `max_tokens=50`，模型不会输出中间推理过程。

#### 情绪取值

情绪只能从以下 8 种中选择一种（对应 Plutchik 基本情绪模型）：

| 取值 | 含义 | 典型表达 |
|---|---|---|
| `joy` | 喜悦 | 终于好起来了，我很开心 |
| `sadness` | 悲伤 | 晚上总是哭，觉得没希望 |
| `anger` | 愤怒 | 他骗了我，我很生气 |
| `fear` | 恐惧 | 一进超市就心慌 |
| `disgust` | 厌恶 | 那种事让我觉得恶心 |
| `surprise` | 惊讶 | 没想到会变成这样 |
| `trust` | 信任 | 我信任你，愿意说下去 |
| `anticipation` | 期待 | 希望下次能有进展 |

强度 `emotional_intensity` 为 0~1 的小数，保留一位小数，0 表示无情绪、1 表示非常强烈。

#### 输出与解析

输出示例（输入：「产后抑郁让我很痛苦，晚上总是哭」）：

```json
{"primary_emotion": "sadness", "emotional_intensity": 0.8}
```

解析与归一：

````python
# evaluation.py：解析
response = self._call_openai_api(prompt, max_tokens=50, temperature=0.3)
if isinstance(response, dict):
    return response
cleaned = re.sub(r'^\s*```(json)?|```\s*$', '', response, flags=re.IGNORECASE).strip()
return json.loads(cleaned)

# main.py：归一
emotion_result = self.evaluator.assess_emotion(patient_text)
if not isinstance(emotion_result, dict):
    emotion_result = {}
emotion_data = {
    "primary_emotion": emotion_result.get("primary_emotion", ""),
    "emotional_intensity": float(emotion_result.get("emotional_intensity", 0.0)),
}
````

`float(...)` 仅在键缺失时取 0.0；若模型返回 `"moderate"` 这类非数值字符串，会抛 `ValueError`，此处没有 try/except。

#### 结果去向

| 消费方 | 用法 |
|---|---|
| `update_response_strategy` | 注入主要情绪与强度，并决定候选策略组（positive → A~D，negative → E~I） |
| 医生回复 prompt | `The patient current primary emotion is {primary_emotion}, with an intensity of {emotional_intensity}` |
| `decision basis_{pid}.json` | 写入 `Primary Emotion` 与 `Emotional Intensity` |

#### 注意点

1. 枚举不校验：提示词限定 8 项，代码不校验；越界标签（如 `anxiety`）会原样落盘并注入后续 prompt。
2. 强度不钳制：没有 min/max 限制，`1.5` 或 `-0.2` 会直接进入决策依据。
3. `float()` 无保护：非数值会中断该轮对话。
4. 输出语言固定英文：中文模式下标签仍为英文，用于与论文口径对齐。
5. 不看上下文：只读当前一句，情绪曲线受单句表达影响，不被整体会话状态平滑。

### A.6 记忆调用（⑤）

判断规则：只有当历史对话中存在与当前话语明显相关、且距离当前不远的内容时才需要引用。

需要引用时输出不超过 50 字的摘要：

```text
患者在 session_1 提到童年被母亲忽视，与当前与母亲冲突的话题直接相关。
```

不需要时输出固定句：

```text
No need to consider historical conversation memory
```

结果会原样拼进医生 prompt 的 `Historical memories you may need to be referred to`，并写入 `Memory Invoke`。

### A.7 治疗阶段（⑥）

输入：当前疗法 + 全部历史对话。输出一段连贯分析（约 80 词），包含“已完成内容总结”与“下一步方向”。

输出示例：

```text
We have established a therapeutic alliance, acknowledging your postpartum distress. Moving forward, we will integrate Cognitive Behavioral Therapy to challenge negative thought patterns and Interpersonal Therapy to address relational stressors.
```

空返回时回退为 `Cannot determine the current treatment stage`。

### A.8 回复策略（⑦）

输入：患者当前话语、主要情绪、情绪强度、是否抗拒、本会谈已用策略列表。选择规则：

- 模型先判断患者态度，只能是 positive 或 negative；
- positive 只能选 A~D；
- negative 只能选 E~I。

策略清单（代码原样，注意 G/H/I 编号出现了两次，实际共 12 项）：

| 编号 | 策略名 | 含义 | 适用态度 |
|---|---|---|---|
| A | Interpretation | 解释：深入分析、换视角 | positive |
| B | Confrontation | 面质：指出不合理与矛盾 | positive |
| C | Invite to Take New Perspectives | 邀请新视角 | positive |
| D | Invite to Explore New Actions | 邀请尝试新行动 | positive |
| E | Restatement | 复述 | negative |
| F | Reflection of Feelings | 情感反映 | negative |
| G | Self-disclosure | 自我暴露 | negative |
| H | Inquiring Subjective Information | 询问主观信息 | negative |
| I | Inquiring Objective Information | 询问客观信息 | negative |
| G | Affirmation and Reassurance | 肯定与安抚 | negative |
| H | Minimal Encouragement | 最小鼓励 | negative |
| I | Answer | 直接回答 | negative |

输出示例：

```json
{"strategy": "Reflection of Feelings", "strategy_text": "I hear how much pain and confusion you are in. It takes courage to seek help for postpartum depression."}
```

`strategy` 只返回策略名，不带编号；`strategy_text` 不超过 30 词，用于指导医生回复。代码不校验策略名是否在清单内，原样落盘并注入医生 prompt。

### A.9 医生回复（⑫）

输入要素：患者当前话语、记忆摘要、主要情绪与强度、当前疗法与阶段分析、策略与策略描述、本会谈历史对话。

输入要点：

```text
1.Patient current words: {patient_input}.
2.Historical memories you may need to be referred to: {memory_result}.
3.The patient current primary emotion is {primary_emotion}, with an intensity of {intensity}.
4.The therapy you should adopt is {current_therapy}.
5.The response strategy you should adopt is {strategy} and the detailed guidance is {strategy_text}.
8.Please refer to your previous replies from the conversation records for this session: {session_memory}.
##Constraints:
Directly generate your response in Chinese. Your response should be no more than 60 characters.
```

输出示例（纯文本，无 JSON）：

```text
这份痛苦与迷茫我都懂。别急，我会陪你一起梳理，慢慢找回内心的安宁。
```

异常时回退为 `抱歉，我暂时无法处理你的请求，请再说一次。`（`en` 模式为英文提示）。

### A.10 初始疗法选择（S1）

输入：完整病历 JSON。输出：标准疗法名称，可为不超过两种的组合，用 ` + ` 连接。

输出示例：

```text
Cognitive Behavioral Therapy + Interpersonal Therapy
```

代码会去除末尾的中英文句号；空返回时回退为 `cognitive-behavioral therapy`。

### A.11 疗程评估（S2）

输入：上一会谈使用的疗法与该会谈完整对话。判断上一疗程是否有效：有效则维持、无效则更换。

输出示例：

```json
{"new_therapy": "Cognitive Behavioral Therapy + Interpersonal Therapy", "reason": "The last session improved emotional awareness and trust; the current combination is effective and stays unchanged."}
```

`reason` 不超过 50 词，写入 `decision basis` 的 `reason for therapy`。缺失时回退为 `cognitive-behavioral therapy` 与 `maintain the original therapy`。

### A.12 解析与兜底规则

| 调用 | 期望输出 | 解析方式 | 空值 / 异常兜底 |
|---|---|---|---|
| ① | JSON | 剥离代码围栏后 `json.loads` | 直接抛异常，本轮中断 |
| ② | 布尔 | `strip().lower() == "true"` | `False` |
| ③ | 布尔 | 非字符串视为 `False`，否则 `lower() == "true"` | `False` |
| ④ | JSON | 已是 dict 直接返回，否则剥离围栏后 `json.loads` | 调用方置 `{}`，强度按 0.0 |
| ⑤ | 文本 | 原样使用 | `No need to consider historical conversation memory` |
| ⑥ | 文本 | 原样使用 | `Cannot determine the current treatment stage` |
| ⑦ | JSON | 同 ④ | 空 dict，策略与描述为空串 |
| ⑫ | 文本 | 去除转义引号与首尾引号 | 中文或英文的固定道歉句 |
| S1 | 文本 | `rstrip('。.')` | `cognitive-behavioral therapy` |
| S2 | JSON | 同 ④ | `cognitive-behavioral therapy` / `maintain the original therapy` |

统一约定：布尔与 JSON 类 prompt 都要求“只输出结果”，但模型仍可能附带代码围栏或说明文字，因此所有 JSON 调用都有剥围栏处理；布尔调用只认字面量 `true`，其余一律按 `False` 处理。
