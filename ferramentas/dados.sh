#!/usr/bin/env bash
# Os dados gerados (posts, fotos, videos, historico, token criptografado) ficam no
# branch "dados", reescrito a cada execucao com um unico commit: o repositorio nao cresce.
set -euo pipefail
REMOTO="https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"

case "${1:-}" in
  baixar)
    rm -rf dados
    if git ls-remote --exit-code --heads "$REMOTO" dados >/dev/null 2>&1; then
      git clone --quiet --depth 1 --branch dados "$REMOTO" dados
      rm -rf dados/.git
    else
      mkdir -p dados
    fi
    ;;
  salvar)
    [ -d dados ] || exit 0
    cd dados
    rm -rf .git
    git init --quiet -b dados
    git -c user.name="achadinhos-bot" -c user.email="actions@users.noreply.github.com" add -A
    git -c user.name="achadinhos-bot" -c user.email="actions@users.noreply.github.com" \
      commit --quiet -m "dados $(date -u +%Y-%m-%dT%H:%MZ)" || exit 0
    git push --quiet --force "$REMOTO" dados
    ;;
  *) echo "uso: dados.sh baixar|salvar"; exit 1 ;;
esac
