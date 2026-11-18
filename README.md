
<h1 align="center" style="font-size: 52px; font-weight: 600; font-family: 'Palatino Linotype', 'Book Antiqua', serif;">
💌 TheraMind : A Strategic and Adaptive Agent for Longitudinal Psychological Counseling (WWW 2026)
</h1>

<p align="center">
  <a href="README.md">English</a> | <a href="README.zh-CN.md">简体中文</a>
</p>


## 🌸 About
This repository contains the official evaluation code and data for the paper "**TheraMind : A Strategic and Adaptive Agent for Longitudinal Psychological Counseling**". See more details in our [paper](https://arxiv.org/abs/2510.25758). If you find this project helpful, feel free to ⭐ it!

> TheraMind represents a definitive shift in AI mental health, moving beyond static models to a dynamic, longitudinal agent that emulates human cognitive processes. It features a novel dual-loop framework that manages both immediate turn-by-turn interactions and long-term strategic goals across multiple sessions. Unlike traditional single-therapy tools, TheraMind utilizes an adaptive selection mechanism to adjust its clinical approach based on real-time efficacy. By integrating patient state perception with phase-aware dialogue management, it transforms standard response generation into a deliberative clinical intervention.

## 📰 News
- **[2026-01-14]** Our paper [**TheraMind**](https://arxiv.org/abs/2510.25758) has been accepted by WWW2026 !
- **[2025-11-02]** Paper submitted to arXiv:https://arxiv.org/abs/2510.25758.
## 📦 Dataset
Patient-Medical-Record dataset provides a comprehensive medical profile for Patient Agent to create a more realistic patient. It contains key information including patient pseudonym, age, mental health history, physical health history, current problems and symptoms, and its corresponding types of mental illness. We apply large language models to automatically extract and integrate key information from the original dataset to get the Patient-Medical-Record dataset. [TheraMind-Patient-Guidance](https://huggingface.co/datasets/GMLHUHE/TheraMind_Patient_Guidance) dataset provides a session-level guidance for Patient Agent to achieve better performance during the multi-session conversation. We use large language models to automatically summarize the treatment process from the origianl dataset and allocate reasonably to get sessinon-level abstracts. By adhering to a standardized structure, our synthesized datasets ensure a high degree of authenticity, privacy, and clinical reliability. Ultimately, it provides a robust basis for evaluating the long-term, nuanced capabilities of counseling agents within realistic contexts.

The original psychological dataset used in our synthesized datasets are derived from a publicly available research dataset [CPsyCounR](https://huggingface.co/datasets/CAS-SIAT-XinHai/CPsyCounR) which consists of 3,134 anonymized and professionally rewritten Chinese psychological counseling reports. All datasets are used strictly for research purposes in accordance with their original licenses and usage guidelines.

## 🧠 What is TheraMind ？
**TheraMind** is an agent specialized in **longitudinal psychological counseling** and **adaptive mental health dialogue generation**. Addressing the critical limitations of standard LLMs, it unifies **tactical dialogue management** and **long-term strategic planning** through a novel **dual-loop** architecture.

<p align="center">
  <img src="figues/pipeline-agent.jpg" alt="Agent Pipeline Overview" width="75%">
  <br>
  <em></em>
</p>

### 🧩 Key Features
- A novel dual-loop agent framework (TheraMind) that models both turn-level dialogue dynamics and the strategic, multi-session structure of psychological counseling.
- An adaptive therapy selection mechanism that evaluates therapeutic efficacy and adjusts treatment strategies across sessions, addressing the limitations of static   single-therapy approaches.
- A clinically grounded dialogue management system that integrates patient state perception, dynamic strategy selection, and treatment phase awareness to support deliberative therapeutic interventions.

### 📈 Superior Performance
Our TheraMind achieves better performance across all ten distinct categories of psychological issues in both single-session (left) and multi-
session (right) contexts.
<p align="center">
  <img src="figues/combined_radar_chart.jpg" alt="radar overview" width="60%">
  <br>
  <em></em>
</p>

## 🔥 Quick Start

> **Data files are not shipped with this repository.** The pipeline is driven by JSON files that you download or generate yourself — see [Data preparation](#3-data-preparation) for the exact list and where each file must go.

### 1. Environment

Requires Python >= 3.10 and [uv](https://docs.astral.sh/uv/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # skip if uv is already installed
uv sync                                           # creates .venv and installs openai / requests
```

Run every command below **from the repository root** and through `uv run` — the uv-managed interpreter is not your system Python.

### 2. API configuration

```bash
cp api_config.example.json api_config.json
```

Then fill in `base_url`, `api_key` and `model`:

| Field | Notes |
|---|---|
| `base_url` | OpenAI-compatible endpoint **including `/v1`** (e.g. `http://host:port/vllm/v1`). A missing `/v1` returns `404`. |
| `api_key` | Raw key only — no `Bearer ` prefix, the SDK adds it. |
| `model` | Model name exactly as the gateway exposes it. |
| `response_language` | `zh` for Chinese dialogue, `en` for English (default `en`). Also selects the `_{lang}` data-file suffix and the `save_data/<lang>/`, `eval_data/<lang>/`, `label_data/<lang>/` output directories. Internal terms (strategy / therapy / emotion labels) stay English. |
| `extra_body` | Carries `enable_thinking=false`. Required for Qwen3-style gateways that spend every token on reasoning and return an empty `content`; delete the key for models that do not support it. |

### 3. Data preparation

Two files must be downloaded by hand; everything else is generated.

| File | How to obtain | Where to put it |
|---|---|---|
| `new_data_translate.json` | HuggingFace [`GMLHUHE/TheraMind_Patient_Guidance`](https://huggingface.co/datasets/GMLHUHE/TheraMind_Patient_Guidance) → download `TheraMind_Patient_Guidance.json` and rename it to `new_data_translate_<lang>.json` (or the legacy `new_data_translate.json`) | repository root |
| `CPsyCounR.json` | HuggingFace [`CAS-SIAT-XinHai/CPsyCounR`](https://huggingface.co/datasets/CAS-SIAT-XinHai/CPsyCounR) (gated, research-use license, application required) | repository root |

Then generate the patient medical records:

```bash
export PYTHONPATH="$PWD/agent"

uv run python data_process/build_raw_data.py   # CPsyCounR.json                 -> raw_data_translate_<lang>.json
uv run python data_process/case_produce.py     # raw_data_translate_<lang>.json -> client_records_translate_<lang>.json
# optional: copy the records into agent/ if you keep an older layout
cp client_records_translate_<lang>.json agent/client_records_translate_<lang>.json
```

`<lang>` is the value of `response_language` (`zh` / `en`), so Chinese mode writes `raw_data_translate_zh.json` and `client_records_translate_zh.json`. Readers prefer the tagged file and fall back to the legacy untagged name, which keeps the existing English data usable in `zh` mode. `initialization.py` also looks in the repository root, so the `cp ... agent/` step is optional.

`build_raw_data.py` maps the 3134 Chinese CPsyCounR reports onto the 100 patient ids of the guidance file (10 categories × 10 patients).

Optionally regenerate the session guidance instead of using the released one:

```bash
uv run python data_process/data_produce.py     # raw_data_translate_<lang>.json -> new_data_translate_<lang>.json
```

> **Working-directory note:** `save_data/<lang>/`, `eval_data/<lang>/`, `label_data/<lang>/` and the data files are resolved relative to the current working directory, while `client_records_translate*.json` is looked up in `agent/` first and then in the repository root. Always start from the repository root.

### 4. Simulate a counseling trajectory

```bash
uv run python agent/main.py
```

This runs every patient in `client_records_translate.json` for 6 sessions × 8 rounds. For a quick smoke test, edit the bottom of `agent/main.py`:

```python
simulator.run(num_sessions=1, max_rounds_per_session=3)
```

| Output | Content |
|---|---|
| `save_data/<lang>/<patient_id>.json` | patient record, per-session therapy and full dialogue |
| `eval_data/<lang>/decision basis_<patient_id>.json` | per-turn memory usage, emotion, strategy and therapy reasoning |
| `label_data/<lang>/label_<patient_id>.json` | patient attitude label for every turn |

`<lang>` follows `response_language`, so Chinese and English runs never overwrite each other.

> The full per-turn call chain and context sources are documented in [docs/dialogue-flow.zh-CN.md](docs/dialogue-flow.zh-CN.md).

### 5. Use the agents directly

```python
from main import AutoDialogueRunner, TherapistAgent, PatientAgent

runner = AutoDialogueRunner()
runner.run(num_sessions=6, max_rounds_per_session=8)

therapist = TherapistAgent()
patient_agent = PatientAgent(medical_record, patient_id)
```

### 6. Troubleshooting

| Symptom | Likely cause |
|---|---|
| `404 Not Found` | `base_url` is missing `/v1` |
| `401 Unauthorized` | invalid key, or a key that already carries a `Bearer ` prefix |
| `content` is `None`, or the record comes back as `{}` | reasoning model with thinking enabled — set `extra_body.chat_template_kwargs.enable_thinking=false` |
| `ModuleNotFoundError: No module named 'memory'` | a `data_process/` script was run without `PYTHONPATH=<repo>/agent` |
| `FileNotFoundError: new_data_translate_{lang}.json` | the script was started outside the repository root |

## 📜 Citation
```bibtex
@inproceedings{hu2026theramind,
  title={Theramind: A strategic and adaptive agent for longitudinal psychological counseling},
  author={Hu, He and Ma, Chiyuan and Wang, Qianning and Lin, Liu and Zhou, Yucheng and Cui, Laizhong and Ma, Fei and Tian, Qi},
  booktitle={Proceedings of the ACM Web Conference 2026},
  pages={9136--9147},
  year={2026}
}
```

## 🧩 License
For **research and educational use only.** Please ensure compliance with **ethical and legal standards** in mental health AI research.

## 🌱 Acknowledgements

We gratefully acknowledge the **CPsyCounR** dataset for providing counseling reports that support the simulation of realistic patient profiles in our dataset. We also sincerely thank the **psychology experts** who offered valuable guidance on psychotherapy processes and counseling dynamics during the development of TheraMind, helping ensure the clinical plausibility and realism of the simulated counseling scenarios.

🔥Please contact huhe@gml.ac.cn or chiyuanma@link.cuhk.edu.cn
 if you encounter any issues.
