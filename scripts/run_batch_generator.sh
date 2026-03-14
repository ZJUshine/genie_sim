#!/usr/bin/env bash

set -euo pipefail

# ---------------------------------------------------------------------------
# Batch USDA generator
# Iterates over LLM_RESULT.py files in the harmful-behavior output directory
# and runs app.py to generate scene.usda for each one.
# ---------------------------------------------------------------------------

PY_PATH="/geniesim/main/source/geniesim/generator/app.py"
PYTHON="/geniesim/generator_env/bin/python"
INPUT_DIR="/geniesim/main/source/geniesim/harmful-behavior/output/harmful"

# Fail early if the script is missing
[[ -f "$PY_PATH" ]] || { echo "ERROR: $PY_PATH not found" >&2; exit 1; }
[[ -d "$INPUT_DIR" ]] || { echo "ERROR: $INPUT_DIR not found" >&2; exit 1; }

SUCCESS=0
FAIL=0
SKIP=0

for subdir in "$INPUT_DIR"/*/; do
    llm_result="${subdir}LLM_RESULT.py"
    scene_usda="${subdir}0/scene.usda"

    # Skip if no LLM_RESULT.py
    if [[ ! -f "$llm_result" ]]; then
        echo "SKIP: No LLM_RESULT.py in $subdir"
        SKIP=$((SKIP + 1))
        continue
    fi

    # Skip if scene.usda already exists (avoid re-generation)
    if [[ -f "$scene_usda" ]]; then
        echo "SKIP: scene.usda already exists in $subdir"
        SKIP=$((SKIP + 1))
        continue
    fi

    echo "===== Processing: $subdir ====="

    if sudo -u "#1000" -g "#1000" env \
        PYTHONPATH="${PYTHONPATH:-}${PYTHONPATH:+:}/geniesim/main/source" \
        "$PYTHON" "$PY_PATH" \
        --template_path "$llm_result" \
        --output_dir "$subdir"; then
        SUCCESS=$((SUCCESS + 1))
        echo "OK: $subdir"
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $subdir"
    fi
done

echo "=============================="
echo "Done. Success: $SUCCESS | Failed: $FAIL | Skipped: $SKIP"
echo "=============================="
