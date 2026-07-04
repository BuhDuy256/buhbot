#!/usr/bin/env bash
# =============================================================================
# setup_vm.sh — Run ONCE on a fresh Azure VM (Ubuntu 24.04 LTS, azureuser)
#
# Usage:
#   chmod +x setup_vm.sh
#   sudo -E ./setup_vm.sh
#
# What this script does:
#   1. Installs Docker CE
#   2. Creates persistent directory structure at /opt/optibot/
#   3. Clones the repo
#   4. Scaffolds .env (you fill in the keys)
#   5. Installs run_job.sh and registers the daily cron job
# =============================================================================

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
REPO_URL="${REPO_URL:-https://github.com/YOUR_USERNAME/YOUR_REPO.git}"
INSTALL_DIR="/opt/optibot"
REPO_DIR="$INSTALL_DIR/repo"
DATA_DIR="$INSTALL_DIR/data"
LOGS_DIR="$INSTALL_DIR/logs"
CRON_SCRIPT="$INSTALL_DIR/run_job.sh"
CRON_USER="${SUDO_USER:-azureuser}"
# Cron schedule: 2:30 AM UTC daily (= 9:30 AM Vietnam time UTC+7)
CRON_SCHEDULE="30 2 * * *"
# ─────────────────────────────────────────────────────────────────────────────

echo "============================================================"
echo " OptiBot Pipeline — Azure VM Setup (Ubuntu 24.04 LTS)"
echo "============================================================"

# ── 1. Install Docker CE ──────────────────────────────────────────────────────
echo ""
echo "[1/5] Installing Docker CE..."

apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg lsb-release

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin

systemctl enable --now docker
usermod -aG docker "$CRON_USER"

echo "  ✔ Docker installed: $(docker --version)"

# ── 2. Create directory structure ─────────────────────────────────────────────
echo ""
echo "[2/5] Creating directory structure at $INSTALL_DIR ..."

# data/ mirrors buhbot/data/ layout (hash_store.json, chunks/, raw/)
mkdir -p "$DATA_DIR/chunks" "$DATA_DIR/raw" "$LOGS_DIR"
chown -R "$CRON_USER:$CRON_USER" "$INSTALL_DIR"

echo "  ✔ Directories created"

# ── 3. Clone repo ─────────────────────────────────────────────────────────────
echo ""
echo "[3/5] Cloning repository..."

if [ -d "$REPO_DIR/.git" ]; then
  echo "  ⚠  Repo already exists — skipping clone (run 'git pull' in $REPO_DIR if needed)"
else
  sudo -u "$CRON_USER" git clone "$REPO_URL" "$REPO_DIR"
  echo "  ✔ Repo cloned to $REPO_DIR"
fi

# ── 4. Create .env file ───────────────────────────────────────────────────────
echo ""
echo "[4/5] Setting up environment secrets..."

ENV_FILE="$INSTALL_DIR/.env"

if [ -f "$ENV_FILE" ]; then
  echo "  ⚠  .env already exists — skipping (edit manually: $ENV_FILE)"
else
  cat > "$ENV_FILE" <<'EOF'
# ── Fill in your actual values ─────────────────────────────────────────────
OPENAI_API_KEY=sk-proj-REPLACE_ME
APP_ENV=production
EOF
  chown "$CRON_USER:$CRON_USER" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "  ✔ Created $ENV_FILE"
  echo "  ⚠  ACTION REQUIRED: Edit the .env file with your actual API key:"
  echo "       nano $ENV_FILE"
fi

# ── 5. Install run_job.sh & register cron ────────────────────────────────────
echo ""
echo "[5/5] Installing cron job..."

cp "$REPO_DIR/deploy/run_job.sh" "$CRON_SCRIPT"
chmod +x "$CRON_SCRIPT"
chown "$CRON_USER:$CRON_USER" "$CRON_SCRIPT"

CRON_LINE="$CRON_SCHEDULE $CRON_SCRIPT >> $LOGS_DIR/cron.log 2>&1"
(crontab -u "$CRON_USER" -l 2>/dev/null | grep -v "run_job.sh" || true; echo "$CRON_LINE") \
  | crontab -u "$CRON_USER" -

echo "  ✔ Cron registered for user '$CRON_USER':"
echo "       $CRON_LINE"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo " Setup complete!"
echo "============================================================"
echo ""
echo " Next steps:"
echo "  1. Edit secrets:  nano $ENV_FILE"
echo "  2. Test manually: sudo -u $CRON_USER $CRON_SCRIPT"
echo "  3. Check logs:    tail -f $LOGS_DIR/cron.log"
echo "  4. Verify cron:   crontab -u $CRON_USER -l"
echo ""
echo " Cron will run daily at 2:30 AM UTC (9:30 AM Vietnam time)."
