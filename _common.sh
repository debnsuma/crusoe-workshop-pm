# Shared by chat.sh and notebook.sh. Not meant to be run on its own.
YELLOW='\033[38;2;206;235;19m'; GREY='\033[38;2;163;163;163m'
RED='\033[38;2;134;77;24m'; BOLD='\033[1m'; OFF='\033[0m'

prepare() {
  cd "$(dirname "$0")"
  command -v uv >/dev/null 2>&1 || export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  if ! command -v uv >/dev/null 2>&1; then
    printf "\n  ${RED}${BOLD}Run ./setup.sh first.${OFF}\n\n"; exit 1
  fi
  if [ ! -d .venv ]; then
    printf "  ${GREY}First run, installing packages. This takes a minute...${OFF}\n"
    uv sync --frozen --quiet 2>/dev/null || uv sync --quiet || {
      printf "\n  ${RED}${BOLD}Install failed. Run ./setup.sh${OFF}\n\n"; exit 1; }
  fi
}
