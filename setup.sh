#!/usr/bin/env bash
# Crusoe PM Workshop: one-command setup.
# Installs everything, asks for your API key, checks it works.
set -euo pipefail
cd "$(dirname "$0")"

BLACK='\033[0;30m'; YELLOW='\033[38;2;206;235;19m'; GOLD='\033[38;2;205;136;26m'
BLUE='\033[38;2;119;153;182m'; GREY='\033[38;2;163;163;163m'; RED='\033[38;2;134;77;24m'
BOLD='\033[1m'; OFF='\033[0m'

step()  { printf "\n${YELLOW}${BOLD}==>${OFF} ${BOLD}%s${OFF}\n" "$1"; }
info()  { printf "    ${GREY}%s${OFF}\n" "$1"; }
good()  { printf "    ${BLUE}OK${OFF}  %s\n" "$1"; }
fail()  { printf "\n    ${RED}${BOLD}Problem:${OFF} %s\n" "$1"; }

printf "${YELLOW}"
cat <<'BANNER'
   ______                             
  / ____/______  ______________  ___  
 / /   / ___/ / / / ___/ __ \  \/  /  
/ /___/ /  / /_/ (__  ) /_/ / /\/ /   
\____/_/   \__,_/____/\____/_/  /_/   
BANNER
printf "${OFF}${BOLD}  Crusoe Chat${OFF}\n"
printf "${GREY}  A chatbot on open models, running on your machine.${OFF}\n"
printf "${GREY}  This takes about two minutes. You can leave it running.${OFF}\n"

# ---------------------------------------------------------------- 1. uv
step "Step 1 of 4: checking the Python toolchain"
if ! command -v uv >/dev/null 2>&1; then
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
if ! command -v uv >/dev/null 2>&1; then
  info "Installing uv, the Python installer. Nothing else on your Mac changes."
  if ! curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1; then
    fail "Could not download uv. Check your internet connection, then run ./setup.sh again."
    exit 1
  fi
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || { fail "uv installed but is not on PATH. Close this window, open a new one, and run ./setup.sh again."; exit 1; }
good "uv $(uv --version | awk '{print $2}')"

# ---------------------------------------------------------------- 2. deps
step "Step 2 of 4: installing Python and the packages"
info "Python 3.12 and every package are pinned, so you get the same versions as everyone else."
info "The first run downloads them. Later runs are instant."
# --frozen installs exactly what uv.lock says and never re-resolves, so a
# fresh machine gets byte-identical versions. Older uv may not know the flag.
if ! uv sync --frozen --quiet 2>/dev/null; then
  if ! uv sync --quiet; then
    fail "Install failed. Scroll up for the reason, or send that output to whoever shared this with you."
    exit 1
  fi
  info "Note: your uv is older, so versions were resolved rather than taken from the lock file."
fi
good "Environment ready in .venv ($(uv run python --version 2>/dev/null || echo 'python'))"

# ---------------------------------------------------------------- 3. key
step "Step 3 of 4: your Crusoe API key"

EXISTING_KEY=""
[ -f .env ] && EXISTING_KEY="$(grep -E '^CRUSOE_API_KEY=' .env | cut -d= -f2- | tr -d '"'"'"' ' || true)"
[ -z "$EXISTING_KEY" ] && EXISTING_KEY="${CRUSOE_API_KEY:-}"

if [ -n "$EXISTING_KEY" ]; then
  good "Found a key already saved (ending ...${EXISTING_KEY: -4})"
  API_KEY="$EXISTING_KEY"
else
  info "Get one at https://console.crusoecloud.com  ->  Intelligence Foundry  ->  API Keys"
  info "Paste it below and press Return. It stays on this machine, in a file called .env."
  printf "\n    ${BOLD}Crusoe API key:${OFF} "
  read -rs API_KEY || true
  printf "\n"
  API_KEY="$(printf '%s' "$API_KEY" | tr -d '[:space:]')"
  if [ -z "$API_KEY" ]; then
    fail "No key entered. Run ./setup.sh again when you have one."
    exit 1
  fi
  good "Key received (ending ...${API_KEY: -4})"
fi

TEAM_NAME="${WORKSHOP_TEAM:-}"
if [ -z "$TEAM_NAME" ]; then
  printf "    ${BOLD}Your team name${OFF} ${GREY}(optional, just a label in the app, press Return to skip):${OFF} "
  read -r TEAM_NAME || true
fi
[ -z "$TEAM_NAME" ] && TEAM_NAME="Crusoe Product"

umask 077
cat > .env <<ENVEOF
# Written by setup.sh. Keep this file private, it is your API key.
CRUSOE_API_KEY=$API_KEY
WORKSHOP_TEAM=$TEAM_NAME

# Filled in later, after you deploy your own fine-tuned model.
CRUSOE_FINE_TUNED_MODEL=
ENVEOF
good "Saved to .env"

# ---------------------------------------------------------------- 4. verify
step "Step 4 of 4: checking the key against Crusoe"
if VERIFY_OUT="$(uv run --quiet python scripts/check_setup.py 2>&1)"; then
  printf '%s\n' "$VERIFY_OUT" | sed 's/^/    /'
else
  printf '%s\n' "$VERIFY_OUT" | sed 's/^/    /'
  fail "The key did not work. Open .env and check it, or generate a new key in the Console."
  exit 1
fi

printf "\n${YELLOW}${BOLD}  Setup complete.${OFF}\n\n"
printf "  ${BOLD}Open the chatbot:${OFF}   ${GOLD}./chat.sh${OFF}\n"
printf "  ${BOLD}Open the notebook:${OFF}  ${GOLD}./notebook.sh${OFF}\n"
printf "  ${GREY}Nothing else to install. Run either one any time.${OFF}\n\n"

if [ -t 0 ]; then
  printf "  Open the chatbot now? [Y/n] "
  read -r LAUNCH || true
  case "${LAUNCH:-y}" in
    [nN]*) printf "  ${GREY}Run ./chat.sh whenever you are ready.${OFF}\n\n" ;;
    *)     exec ./chat.sh ;;
  esac
fi
