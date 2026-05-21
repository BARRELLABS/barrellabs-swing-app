#!/usr/bin/env bash
# Convenience wrapper for launching the labeling tool with sensible defaults:
#   - 4 GB upload limit (screen recordings are big)
#   - No usage stats sent to Streamlit
#   - Honors $LABELING_VIDEO_DIRS if set
#
# Drop videos into validation/videos/ first, then run this from the repo root:
#
#   ./scripts/validation/launch_labeling.sh
#
set -euo pipefail
cd "$(dirname "$0")/../.."

exec python3 -m streamlit run scripts/validation/labeling_app.py \
    --server.maxUploadSize=4096 \
    --browser.gatherUsageStats=false \
    "$@"
