
<h1 align="center" style="font-size: 52px; font-weight: 600; font-family: 'Palatino Linotype', 'Book Antiqua', serif;">
💌 TheraMind：面向纵向心理咨询的策略自适应智能体（WWW 2026）
</h1>

<p align="center">
  <a href="README.md">English</a> | <a href="README.zh-CN.md">简体中文</a>
</p>

## 🌸 项目简介

本仓库包含论文《**TheraMind: A Strategic and Adaptive Agent for Longitudinal Psychological Counseling**》的官方评估代码与数据。更多细节请见[论文](https://arxiv.org/abs/2510.25758)。如果这个项目对你有帮助，欢迎点一个 ⭐。

> TheraMind 代表了 AI 心理健康领域的一次根本性转变：它不再是一个静态模型，而是一个模拟人类认知过程的、动态的纵向智能体。它采用新颖的**双循环**框架，同时管理逐轮的即时交互与跨多次会谈的长期策略目标。与传统单一疗法工具不同，TheraMind 通过自适应选择机制，依据实时疗效调整其临床取向。通过整合患者状态感知与阶段感知的对话管理，它把标准的回复生成转化为一种深思熟虑的临床干预。

## 📰 动态

- **[2026-01-14]** 论文 [**TheraMind**](https://arxiv.org/abs/2510.25758) 已被 WWW 2026 接收！
- **[2025-11-02]** 论文提交至 arXiv：https://arxiv.org/abs/2510.25758

## 📦 数据集

Patient-Medical-Record 数据集为 Patient Agent 提供完整的医疗档案，使其塑造的患者更接近真实。它包含患者化名、年龄、心理健康史、生理健康史、当前问题与症状，以及对应的心理疾病类型。我们使用大语言模型从原始数据集中自动抽取并整合关键信息，得到该数据集。[TheraMind-Patient-Guidance](https://huggingface.co/datasets/GMLHUHE/TheraMind_Patient_Guidance) 数据集则为 Patient Agent 提供会谈级别的引导，以在多会谈对话中取得更好的表现。我们用大语言模型从原始数据集中自动总结治疗过程，并合理划分出各会谈的摘要。通过遵循标准化结构，我们合成的数据集保证了高度的真实性、隐私性与临床可靠性，从而为在真实情境中评估智能体的长期、细致能力提供了坚实基础。

我们所合成数据集的原始心理数据来自公开研究数据集 [CPsyCounR](https://huggingface.co/datasets/CAS-SIAT-XinHai/CPsyCounR)，其中包含 3,134 份匿名化并经专业改写的心理咨询报告。所有数据均严格依照其原始许可与使用规范，仅用于研究目的。

## 🧠 TheraMind 是什么？

**TheraMind** 是一个专注于**纵向心理咨询**与**自适应心理健康对话生成**的智能体。针对标准 LLM 的关键局限，它通过新颖的**双循环**架构统一了**战术级对话管理**与**长期策略规划**。

<p align="center">
  <img src="figues/pipeline-agent.jpg" alt="Agent Pipeline Overview" width="75%">
  <br>
  <em></em>
</p>

### 🧩 核心特性

- 新颖的双循环智能体框架（TheraMind），同时建模逐轮对话动态与心理咨询中跨会谈的策略结构。
- 自适应治疗选择机制，评估治疗效果并在会谈之间调整治疗策略，弥补静态单一疗法取向的不足。
- 有临床依据的对话管理系统，整合患者状态感知、动态策略选择与治疗阶段意识，支撑深思熟虑的治疗性干预。

### 📈 性能表现

在单次会谈（左）与多次会谈（右）两种情境下，TheraMind 在全部十个心理问题类别上均取得了更好的表现。

<p align="center">
  <img src="figues/combined_radar_chart.jpg" alt="radar overview" width="60%">
  <br>
  <em></em>
</p>

## 🔥 快速开始

> **数据文件不随仓库提供。** 整条流水线由需要你自行下载或生成的 JSON 文件驱动 —— 具体清单与放置位置见[数据准备](#3-数据准备)。

### 1. 环境

需要 Python >= 3.10 与 [uv](https://docs.astral.sh/uv/)：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # 已安装 uv 可跳过
uv sync                                           # 创建 .venv 并安装 openai / requests
```

下文的每条命令都必须在**仓库根目录**下执行，并且通过 `uv run` 运行 —— uv 管理的解释器并非你的系统 Python。

### 2. API 配置

```bash
cp api_config.example.json api_config.json
```

然后填写 `base_url`、`api_key` 与 `model`：

| 字段 | 说明 |
|---|---|
| `base_url` | 兼容 OpenAI 协议的接口地址，**必须包含 `/v1`**（例如 `http://host:port/vllm/v1`）。缺少 `/v1` 会返回 `404`。 |
| `api_key` | 只填裸 Key —— 不要带 `Bearer ` 前缀，SDK 会自动添加。 |
| `model` | 与网关对外暴露的名称完全一致。 |
| `extra_body` | 承载 `enable_thinking=false`。对 Qwen3 这类把全部 token 花在推理上、导致 `content` 为空的网关是必需的；若所用模型不支持该参数，删除这一项即可。 |

### 3. 数据准备

有两个文件必须手动下载，其余均为生成产物。

| 文件 | 获取方式 | 放置位置 |
|---|---|---|
| `new_data_translate.json` | HuggingFace [`GMLHUHE/TheraMind_Patient_Guidance`](https://huggingface.co/datasets/GMLHUHE/TheraMind_Patient_Guidance) → 下载 `TheraMind_Patient_Guidance.json` 并重命名为 `new_data_translate.json` | 仓库根目录 |
| `CPsyCounR.json` | HuggingFace [`CAS-SIAT-XinHai/CPsyCounR`](https://huggingface.co/datasets/CAS-SIAT-XinHai/CPsyCounR)（gated 数据集，研究用途许可，需提交申请） | 仓库根目录 |

随后生成患者病历：

```bash
export PYTHONPATH="$PWD/agent"

uv run python data_process/build_raw_data.py   # CPsyCounR.json          -> raw_data_translate.json
uv run python data_process/case_produce.py     # raw_data_translate.json -> client_records_translate.json
cp client_records_translate.json agent/client_records_translate.json
```

`build_raw_data.py` 会把 3134 份中文 CPsyCounR 报告映射到引导文件中的 100 个患者 key 上（10 个类别 × 每类 10 个患者）。

如果你希望自行生成会谈引导、而不使用已发布的数据，可以额外运行：

```bash
uv run python data_process/data_produce.py     # raw_data_translate.json -> new_data_translate.json
```

> **工作目录说明：** `save_data/`、`eval_data/`、`label_data/` 与 `new_data_translate.json` 按当前工作目录解析，而 `client_records_translate.json` 从 `agent/` 目录读取。请始终从仓库根目录启动。

### 4. 模拟一次咨询轨迹

```bash
uv run python agent/main.py
```

该命令会对 `client_records_translate.json` 中的每一位患者各跑 6 个会谈 × 8 轮对话。若只想快速冒烟验证，请修改 `agent/main.py` 末尾：

```python
simulator.run(num_sessions=1, max_rounds_per_session=3)
```

输出产物：

| 输出 | 内容 |
|---|---|
| `save_data/<patient_id>.json` | 患者档案、每次会谈所用疗法与完整对话 |
| `eval_data/decision basis_<patient_id>.json` | 每一轮的记忆调用、情绪、策略与疗法决策依据 |
| `label_data/label_<patient_id>.json` | 每一轮的患者态度标签 |

### 5. 直接调用各 Agent

```python
from main import AutoDialogueRunner, TherapistAgent, PatientAgent

runner = AutoDialogueRunner()
runner.run(num_sessions=6, max_rounds_per_session=8)

therapist = TherapistAgent()
patient_agent = PatientAgent(medical_record, patient_id)
```

### 6. 常见问题排查

| 现象 | 可能原因 |
|---|---|
| `404 Not Found` | `base_url` 缺少 `/v1` |
| `401 Unauthorized` | Key 无效，或 Key 值本身已带 `Bearer ` 前缀 |
| `content` 为 `None`，或病历返回 `{}` | 推理模型开启了思考模式 —— 设置 `extra_body.chat_template_kwargs.enable_thinking=false` |
| `ModuleNotFoundError: No module named 'memory'` | 运行 `data_process/` 下脚本时未设置 `PYTHONPATH=<repo>/agent` |
| `FileNotFoundError: new_data_translate.json` | 未在仓库根目录下启动脚本 |

## 📜 引用

```bibtex
@inproceedings{hu2026theramind,
  title={Theramind: A strategic and adaptive agent for longitudinal psychological counseling},
  author={Hu, He and Ma, Chiyuan and Wang, Qianning and Lin, Liu and Zhou, Yucheng and Cui, Laizhong and Ma, Fei and Tian, Qi},
  booktitle={Proceedings of the ACM Web Conference 2026},
  pages={9136--9147},
  year={2026}
}
```

## 🧩 许可

**仅供研究与教育用途。** 请确保在心理健康 AI 研究中遵守**伦理与法律规范**。

## 🌱 致谢

我们衷心感谢 **CPsyCounR** 数据集提供的咨询报告，它们支撑了本数据集中真实患者画像的模拟。我们也诚挚感谢在 TheraMind 研发过程中提供宝贵心理治疗过程与咨询动力学指导的**心理学专家**，他们帮助确保了所模拟咨询场景的临床合理性与真实性。

🔥如遇任何问题，请联系 huhe@gml.ac.cn 或 chiyuanma@link.cuhk.edu.cn
