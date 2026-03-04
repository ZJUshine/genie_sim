# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Genie Sim is AgiBot's simulation platform for embodied intelligence (humanoid robots). It provides environment reconstruction, LLM-driven scene generation, data collection, and automated benchmark evaluation. Built on NVIDIA Isaac Sim 5.1.0 and Python 3.11+.

## Architecture

The codebase has four major subsystems under `source/`:

- **`geniesim/`** — Core simulation platform (MPL 2.0 license)
  - `app/` — Application entry point (`app.py`), workflow launcher, controllers, ROS publisher
  - `benchmark/` — Task benchmark framework: `TaskBenchmark` orchestrates environments (`envs/`), policies (`policy/`), hooks, and task configs (`config/llm_task/`, `config/task_definitions/`)
  - `evaluator/` — LLM/VLM-based evaluation: prompt templates, generators for task instructions and eval configs
  - `generator/` — LLM-driven scene generation pipeline with Open WebUI + MCP server (RAG-based asset retrieval via ChromaDB). Outputs scene graphs to `LLM_RESULT.py`
  - `robot/` — Robot definitions (Genie G1/G2) with Isaac Sim integration and IK/FK utilities
  - `plugins/` — Logging, GUI control, output system, TGS (Task Generation System) with `ObjectSampler` and `TaskGenerator`
  - `utils/` — IK-SDK, data transport (`DataCourier`), USD utilities, transform math, ROS nodes
  - `config/` — YAML task configs (e.g., `select_color.yaml`, `template.yaml`). `template.yaml` is used by `run_tasks.sh` as a base
  - `assets/` — Simulation-ready 3D assets (downloaded separately from ModelScope)

- **`data_collection/`** — Automated and teleoperation data collection with cuRobo motion planning. Has its own Docker image and scripts

- **`scene_reconstruction/`** — 3DGS-based scene reconstruction pipeline (separate Docker image, multi-license)

- **`openpi/`** — Policy inference framework (based on Physical Intelligence's OpenPI). Manages model training and serving

## Key Commands

All commands assume you are in the repo root (`genie_sim/`).

### Docker & Environment Setup

```bash
# Build the main simulation Docker image
docker build -f ./scripts/dockerfile -t registry.agibot.com/genie-sim/open_source:latest .

# Start simulation container (GUI mode)
./scripts/start_gui.sh

# Enter running container
./scripts/into.sh

# Stop simulation container
./scripts/stop_gui.sh
```

### Running Benchmark Tasks (inside container)

```bash
# Run a single benchmark task
omni_python source/geniesim/app/app.py --config source/geniesim/config/select_color.yaml

# Run all benchmark tasks (configure INFER_HOST, INFER_PORT, NUM_EPISODE, ROBOT_TYPE in script)
./scripts/run_tasks.sh

# Collect evaluation scores
./scripts/collect_scores.sh

# Stop all running evaluations
./scripts/clean.sh
```

### Scene Generator

```bash
# Launch LLM scene generator (Open WebUI + MCP server via docker compose)
./scripts/start_generator.sh

# Run scene viewer inside simulation container
omni_python source/geniesim/generator/scene_viewer.py

# Trigger scene generation once
./scripts/run_generator.sh
```

### Data Collection

```bash
# One-click data collection (from source/data_collection/)
./scripts/run_data_collection.sh [--headless] [--task TASK_PATH]

# Teleoperation data collection
./scripts/autoteleop.sh

# Post-process collected data
./scripts/autoteleop_post_process.sh {TASK_NAME}
```

### Model Training (in openpi container)

```bash
uv run python scripts/compute_norm_states.py --config-name={train_config_name}
uv run python scripts/train.py select_color --exp-name=select_color --overwrite
```

### Python Module Install (conda, outside container)

```bash
conda create --name geniesim python=3.11
conda activate geniesim
python -m pip install -e ./source
```

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Code Style & Conventions

- **Formatter**: Black with `--line-length 120`
- **License header**: All `.py` files under `source/geniesim/` and `source/data_collection/` must include the MPL 2.0 license header (enforced by pre-commit)
- **Commit messages**: Commitizen-enforced with prefixes: `add`, `dev`, `chore`, `ci`, `perf`, `update`, `fix`, `feat`, `docs`, `refactor`, `revert`, `test`, `format` (min 10 chars)
- **Pre-commit excludes**: `source/data_collection/`, `source/scene_reconstruction/patch/`, and `source/geniesim/generator/scene_language/` from some hooks

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `BASE_URL` | OpenAI-compatible API endpoint for LLM/VLM |
| `API_KEY` | API key for LLM/VLM services |
| `MODEL` | LLM model name (e.g., `qwen3-max`) for evaluation generation |
| `VL_MODEL` | VLM model name (e.g., `qwen3-vl-plus`) for auto-scoring |
| `SIM_ASSETS` | Path to GenieSimAssets directory (for data_collection) |

## Key Configuration Files

- `source/geniesim/config/template.yaml` — Base config template for batch benchmark runs
- `source/geniesim/benchmark/config/task_config_mapping.py` — Maps sub-task names to background scene configs per robot type
- `source/geniesim/generator/config/openwebui.json` — Open WebUI configuration (requires OPENAI_API_BASE_URL and OPENAI_API_KEY)
- `source/geniesim/generator/server/text_embedding_config.json` — Embedding model config for RAG asset retrieval
- `source/geniesim/generator/compose.yaml` — Docker compose for scene generator (MCP server + Open WebUI)
