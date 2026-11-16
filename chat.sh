#!/usr/bin/env bash
# Open the chatbot in your browser.
set -euo pipefail
. "$(dirname "$0")/_common.sh"
prepare

printf "\n${YELLOW}${BOLD}  Crusoe Chat${OFF}\n"
printf "${GREY}  Your browser will open in a moment.${OFF}\n"
printf "${GREY}  Press Control-C in this window when you are done.${OFF}\n"
exec uv run python app.py
