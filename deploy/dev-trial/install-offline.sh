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
markdown=0
if [ -e "$base/README.md" ] || [ -L "$base/README.md" ]; then
  [ ! -L "$base/README.md" ] && [ -f "$base/README.md" ] || fail 'The offline guide must be a regular file.'
  markdown=1
fi
[ "$(wc -c < "$base/SHA256SUMS")" -le 4096 ] || fail 'The checksum list is invalid.'
awk -v markdown="$markdown" '
  NF!=2 || length($1)!=64 || $1~/[^0-9a-f]/ { exit 1 }
  $2!~/^(images\.tsv|deployment\.tar\.gz|versions\.tsv|manifest\.json|install-version\.sh|install-offline\.sh|README\.txt|README\.md|backend\.tar|app\.tar|postgres\.tar|objects\.tar)$/ { exit 1 }
  seen[$2]++ { exit 1 }
  END { if (NR!=11+markdown || (markdown && !seen["README.md"])) exit 1 }
' "$base/SHA256SUMS" || fail 'The checksum list is invalid.'
while read -r expected name; do
  [ "$(hash "$base/$name")" = "$expected" ] || fail 'Offline package checksum failed. Existing services and data were preserved.'
done < "$base/SHA256SUMS"
[ "$(wc -c < "$base/images.tsv")" -le 4096 ] || fail 'The image list is invalid.'
source_revision=$(awk -F '"' '$2=="source_revision" { print $4 }' "$base/manifest.json")
[ "${#source_revision}" -eq 40 ] || fail 'The offline source is invalid.'
case "$source_revision" in *[!0-9a-f]*) fail 'The offline source is invalid.';; esac
awk -F '\t' -v revision="$source_revision" '
  function digest(s) { return substr(s,1,7)=="sha256:" && length(s)==71 && substr(s,8)!~/[^0-9a-f]/ }
  BEGIN { split("backend app postgres objects",names," ") }
  NF!=6 || $1!=names[NR] || $2!="capstone-offline/" $1 ":" revision || !digest($3) || !digest($4) || $5!="linux/amd64" || $6!=$1 ".tar" { exit 1 }
  END { if (NR!=4) exit 1 }
' "$base/images.tsv" || fail 'The image list is invalid.'
command -v docker >/dev/null 2>&1 || fail 'Install Docker with Compose v2 first.'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose v2 is required.'
while IFS="$(printf '\t')" read -r kind tag config_digest manifest_digest platform archive; do
  printf 'Loading offline image: %s\n' "$kind"
  docker image load --input "$base/$archive"
  actual=$(docker image inspect --format '{{.Id}}' "$tag") || fail 'An imported image tag is missing.'
  [ "$actual" = "$config_digest" ] || [ "$actual" = "$manifest_digest" ] || fail 'An imported image ID differs.'
  actual_platform=$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$actual") || fail 'Cannot check an imported image platform.'
  [ "$actual_platform" = "$platform" ] || fail 'An imported image platform differs. Existing services and data were preserved.'
  case "$kind" in
    backend|app)
      label=$(docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$actual") || fail 'Cannot check an imported image source.'
      [ "$label" = "$source_revision" ] || fail 'An imported image source differs.';;
  esac
  case "$kind" in
    backend) backend_actual=$actual;; app) app_actual=$actual;;
    postgres) postgres_actual=$actual;; objects) objects_actual=$actual;;
  esac
done < "$base/images.tsv"
# Nothing reaches the installer until every archive, imported identity,
# platform and application source label has passed its checks.
selection_directory=$(mktemp -d)
trap 'rm -f "$selection_directory/selection.tsv"; rmdir "$selection_directory"' 0
trap 'exit 1' HUP INT TERM
selection=$selection_directory/selection.tsv
printf 'backend\t%s\napp\t%s\npostgres\t%s\nobjects\t%s\n' \
  "$backend_actual" "$app_actual" "$postgres_actual" "$objects_actual" > "$selection"
CAPSTONE_OFFLINE_DIRECTORY=$base CAPSTONE_INSTALL_CATALOG=$base/versions.tsv \
  CAPSTONE_OFFLINE_IMAGE_SELECTION=$selection sh "$base/install-version.sh"
