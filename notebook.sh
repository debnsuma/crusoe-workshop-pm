#!/usr/bin/env bash
# Open the notebook: how the API works, with nothing hidden.
set -euo pipefail
. "$(dirname "$0")/_common.sh"
prepare

printf "\n${YELLOW}${BOLD}  Notebook${OFF}\n"
printf "${GREY}  Your browser will open. Click notebook.ipynb, then run the cells in order.${OFF}\n"
printf "${GREY}  Press Control-C in this window when you are done.${OFF}\n"
exec uv run jupyter lab notebook.ipynb
