#!/usr/bin/env bash
# =============================================================================
# run_job.sh — Daily cron wrapper for the OptiBot pipeline
#
# Installed at: /opt/optibot/run_job.sh  (by setup_vm.sh)
# Called by cron as user: azureuser
#
# Flow:
#   1. Load .env secrets
#   2. Pull latest code from git
#   3. Build Docker image from buhbot/Dockerfile
#   4. Run container with persistent data/ volume mount
#   5. Log output with timestamp
#   6. Rotate logs older than 30 days
# =============================================================================

set -euo pipefail

# ── Paths ─────────────────────────────────────────────────────────────────────
INSTALL_DIR="/opt/optibot"
REPO_DIR="$INSTALL_DIR/repo"
DATA_DIR="$INSTALL_DIR/data"
LOGS_DIR="$INSTALL_DIR/logs"
ENV_FILE="$INSTALL_DIR/.env"
IMAGE_NAME="optibot-pipeline"
LOG_FILE="$LOGS_DIR/$(date +%Y-%m-%d).log"
# ─────────────────────────────────────────────────────────────────────────────

mkdir -p "$LOGS_DIR"

# Tee: write to today's log AND to stdout (which cron captures into cron.log)
exec > >(tee -a "$LOG_FILE") 2>&1

echo ""
echo "============================================================"
echo " OptiBot Daily Sync — $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "============================================================"

# ── 1. Load secrets ───────────────────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
  echo "[ERROR] .env file not found at $ENV_FILE"
  echo "        Run setup_vm.sh first, then fill in your API key."
  exit 1
fi

set -o allexport
# shellcheck disable=SC1090
source "$ENV_FILE"
set +o allexport

echo "[INFO] Loaded secrets from $ENV_FILE"
echo "[INFO] APP_ENV=${APP_ENV:-production}"

# ── 2. Pull latest code ───────────────────────────────────────────────────────
echo ""
echo "[STEP 1] Pulling latest code..."
git -C "$REPO_DIR" pull --ff-only
echo "[INFO] Repo is up to date."

# ── 3. Build Docker image ─────────────────────────────────────────────────────
echo ""
echo "[STEP 2] Building Docker image: $IMAGE_NAME ..."
# Dockerfile lives at the root of the buhbot repo
docker build \
  --file "$REPO_DIR/Dockerfile" \
  --tag "$IMAGE_NAME:latest" \
  "$REPO_DIR"
echo "[INFO] Image built successfully."

# ── 4. Run container ──────────────────────────────────────────────────────────
echo ""
echo "[STEP 3] Running pipeline..."
echo "[INFO] Mounting $DATA_DIR → /app/data (persistent state)"

# docker run -e OPENAI_API_KEY=... runs main.py once and exits 0
docker run --rm \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e APP_ENV="${APP_ENV:-production}" \
  -v "$DATA_DIR:/app/data" \
  "$IMAGE_NAME:latest"

EXIT_CODE=$?

# ── 5. Report result ──────────────────────────────────────────────────────────
echo ""
if [ "$EXIT_CODE" -eq 0 ]; then
  echo "[SUCCESS] Pipeline completed. Exit code: 0"
else
  echo "[FAILURE] Pipeline exited with code: $EXIT_CODE"
fi

echo " Finished at: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "============================================================"

# ── 6. Rotate logs older than 30 days ────────────────────────────────────────
find "$LOGS_DIR" -name "*.log" -mtime +30 -delete 2>/dev/null || true

exit "$EXIT_CODE"
