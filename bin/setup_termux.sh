#!/data/data/com.termux/files/usr/bin/bash
set -eu

project_dir="${1:-$HOME/ufmt-agent}"
config_dir="${UFMT_AGENT_HOME:-$HOME/.config/ufmt-agent}"

command -v pkg >/dev/null || {
  echo "Este instalador deve ser executado no Termux."
  exit 1
}

pkg update -y
pkg install -y x11-repo
pkg install -y python chromium termux-api

python -m venv "$project_dir/.venv"
"$project_dir/.venv/bin/pip" install --upgrade pip
"$project_dir/.venv/bin/pip" install "$project_dir"

mkdir -p "$config_dir"
if [ ! -f "$config_dir/.env" ]; then
  cp "$project_dir/.env.example" "$config_dir/.env"
  echo "Edite $config_dir/.env e informe CPF e senha do AVA."
fi

echo "Instalação concluída. Próximos comandos:"
echo "  $project_dir/.venv/bin/ufmt-sync doctor"
echo "  $project_dir/.venv/bin/ufmt-sync authorize --client-secret <arquivo> --output $config_dir/token.json"
echo "  $project_dir/.venv/bin/ufmt-sync inspect"
