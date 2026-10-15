#!/bin/sh
# Run only from the complete offline delivery directory. No download commands.
set -eu
umask 077
LC_ALL=C
export LC_ALL
fail() { printf '%s\n' "$1" >&2; exit 1; }
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
hash() {
  if command -v sha256sum >/dev/null 2>&1; then value=$(sha256sum "$1")
  elif command -v shasum >/dev/null 2>&1; then value=$(shasum -a 256 "$1")
  else fail 'A SHA256 checksum tool is required.'; fi
  printf '%s\n' "${value%% *}"
}
for name in SHA256SUMS images.tsv deployment.tar.gz versions.tsv manifest.json install-version.sh install-offline.sh README.txt backend.tar app.tar postgres.tar objects.tar; do
  [ ! -L "$base/$name" ] && [ -f "$base/$name" ] || fail 'The offline package is incomplete or contains a symbolic link.'
done
[ "$(wc -c < "$base/SHA256SUMS")" -le 4096 ] || fail 'The checksum list is invalid.'
awk '
  NF!=2 || length($1)!=64 || $1~/[^0-9a-f]/ { exit 1 }
  $2!~/^(images.tsv|deployment.tar.gz|versions.tsv|manifest.json|install-version.sh|install-offline.sh|README.txt|backend.tar|app.tar|postgres.tar|objects.tar)$/ { exit 1 }
  seen[$2]++ { exit 1 }
  END { if (NR!=11) exit 1 }
' "$base/SHA256SUMS" || fail 'The checksum list is invalid.'
while read -r expected name; do
  [ "$(hash "$base/$name")" = "$expected" ] || fail 'Offline package checksum failed. Existing services and data were preserved.'
done < "$base/SHA256SUMS"
[ "$(wc -c < "$base/images.tsv")" -le 1024 ] || fail 'The image list is invalid.'
awk -F '\t' '
  BEGIN { split("backend app postgres objects",names," ") }
  NF!=4 || $1!=names[NR] || $2!~/^sha256:/ || length($2)!=71 || substr($2,8)~/[^0-9a-f]/ || $3!="linux/amd64" || $4!=$1 ".tar" { exit 1 }
  END { if (NR!=4) exit 1 }
' "$base/images.tsv" || fail 'The image list is invalid.'
command -v docker >/dev/null 2>&1 || fail 'Install Docker with Compose v2 first.'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose v2 is required.'
while IFS="$(printf '\t')" read -r kind identity platform archive; do
  printf 'Loading offline image: %s\n' "$kind"
  docker image load --input "$base/$archive"
  actual=$(docker image inspect --format '{{.Id}}' "$identity") || fail 'An imported image is missing.'
  [ "$actual" = "$identity" ] || fail 'An imported image ID differs.'
  actual=$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$identity") || fail 'Cannot check an imported image platform.'
  [ "$actual" = "$platform" ] || fail 'An imported image platform differs. Existing services and data were preserved.'
done < "$base/images.tsv"
CAPSTONE_OFFLINE_DIRECTORY=$base CAPSTONE_INSTALL_CATALOG=$base/versions.tsv sh "$base/install-version.sh"
