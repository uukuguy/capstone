#!/bin/sh
# Release publisher replaces these four literals before publishing this installer.
set -eu
umask 077
version='@VERSION@'
url='@ARCHIVE_URL@'
expected='@ARCHIVE_SHA256@'
source='@SOURCE_REVISION@'
destination=${CAPSTONE_TRIAL_DIRECTORY:-"$HOME/capstone"}
fail() { printf '%s\n' "$1" >&2; exit 1; }
safe() { [ ! -L "$1" ] || fail 'An installation path is a symbolic link.'; }
command -v docker >/dev/null 2>&1 || fail 'Install Docker with Compose v2 first.'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose v2 is required.'
if [ -z "${CAPSTONE_OFFLINE_DIRECTORY:-}" ]; then
  command -v curl >/dev/null 2>&1 || fail 'curl is required.'
fi
safe "$destination"
[ ! -e "$destination" ] || [ -d "$destination" ] || fail 'The installation directory is invalid.'
temporary=$(mktemp -d)
locked=''
cleanup() {
  rm -f "$temporary/package.tar.gz" "$temporary/list" "$temporary/catalog" "$temporary/catalog.new" "$temporary/catalog.old" "$temporary/catalog.merged"
  if [ -d "$temporary/package" ]; then
    for file in compose.yaml start.sh .env .env.example release.env manifest.json README.txt data-contract.env capstone.sh install.sh legacy-data-contract.env; do
      rm -f "$temporary/package/$file"
    done
    rmdir "$temporary/package"
  fi
  rmdir "$temporary"
  if [ -n "$locked" ]; then rmdir "$locked"; fi
}
trap cleanup 0
trap 'exit 1' HUP INT TERM
if [ -n "${CAPSTONE_OFFLINE_DIRECTORY:-}" ]; then
  safe "$CAPSTONE_OFFLINE_DIRECTORY/deployment.tar.gz"
  [ "$url" = offline ] || fail 'The installer does not support offline input.'
  [ -n "${CAPSTONE_INSTALL_CATALOG:-}" ] || fail 'The offline catalog is required.'
  cp "$CAPSTONE_OFFLINE_DIRECTORY/deployment.tar.gz" "$temporary/package.tar.gz"
else
  printf 'Downloading user-local %s deployment package...\n' "$version"
  curl --fail --location --progress-bar --connect-timeout 15 --max-time 180 "$url" -o "$temporary/package.tar.gz"
fi
if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "$temporary/package.tar.gz")
elif command -v shasum >/dev/null 2>&1; then
  actual=$(shasum -a 256 "$temporary/package.tar.gz")
else fail 'A SHA256 checksum tool is required.'; fi
[ "${actual%% *}" = "$expected" ] || fail 'Package checksum failed; installation stopped.'
tar -tzf "$temporary/package.tar.gz" > "$temporary/list"
awk '
  !/^(compose.yaml|start.sh|\.env|\.env.example|release.env|manifest.json|README.txt|data-contract.env|capstone.sh|install.sh|legacy-data-contract.env)$/ { exit 1 }
  seen[$0]++ { exit 1 }
  END { if (!seen["compose.yaml"] || !seen["start.sh"] || !seen[".env"] || !seen[".env.example"] || !seen["release.env"] || !seen["manifest.json"] || !seen["README.txt"] || !seen["data-contract.env"] || !seen["capstone.sh"] || !seen["install.sh"]) exit 1 }
' "$temporary/list" || fail 'Deployment archive contents are invalid.'
# Only flat regular files are allowed, including on BSD tar and GNU tar.
tar -tvzf "$temporary/package.tar.gz" | awk 'substr($0,1,1)!="-" { exit 1 }' || fail 'Deployment archive contains non-regular files.'
mkdir -m 700 "$temporary/package"
tar -xzf "$temporary/package.tar.gz" -C "$temporary/package"
if [ -n "${CAPSTONE_INSTALL_CATALOG:-}" ]; then
  safe "$CAPSTONE_INSTALL_CATALOG"
  cp "$CAPSTONE_INSTALL_CATALOG" "$temporary/catalog"
else
  sh "$temporary/package/install.sh" --catalog > "$temporary/catalog"
fi
mkdir -p "$destination"
destination=$(CDPATH= cd -- "$destination" && pwd -P)
meta=$destination/.capstone-management
packages=$destination/versions
safe "$meta"; safe "$packages"
mkdir -p "$meta" "$packages"
safe "$meta/lock"
mkdir "$meta/lock" 2>/dev/null || fail 'Another installation or management operation is running.'
locked=$meta/lock
if [ -n "${CAPSTONE_OFFLINE_DIRECTORY:-}" ]; then
  # A single offline delivery must not remove the previous active source from
  # the manager catalog, including when the shared-data guard rejects startup.
  validate_catalog() {
    [ -f "$1" ] && [ "$(wc -c < "$1")" -le 1048576 ] || return 1
    awk -F '\t' '
    function hex(s,n) { return length(s)==n && s !~ /[^0-9a-f]/ }
    function date(s,a,y,m,d,days) {
      if (s !~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$/) return 0
      split(s,a,"-"); y=a[1]+0; m=a[2]+0; d=a[3]+0
      if (y<1 || m<1 || m>12) return 0
      days=31
      if (m==4 || m==6 || m==9 || m==11) days=30
      if (m==2) days=28+(y%4==0 && (y%100!=0 || y%400==0))
      return d>=1 && d<=days
    }
    /^#/ || /^$/ { next }
    { p=substr($2,12)
      if (NF!=5 || !hex($1,40) || substr($2,1,11)!="user-local-" || length(p)<7 || length(p)>40 || p ~ /[^0-9a-f]/ || index($1,p)!=1 ||
          $3!="https://github.com/uukuguy/capstone/releases/download/" $2 "/install.sh" || !hex($4,64) ||
          !date($5) || seen[$1]++ || tags[$2]++) { bad=1; exit 1 }
      count++; print
    }
    END { if (bad || !count) exit 1 }
    ' "$1"
  }
  validate_catalog "$temporary/catalog" > "$temporary/catalog.new" || fail 'The offline version catalog is invalid.'
  safe "$meta/versions.tsv"
  : > "$temporary/catalog.old"
  if [ -e "$meta/versions.tsv" ]; then
    validate_catalog "$meta/versions.tsv" > "$temporary/catalog.old" || fail 'The existing version catalog is invalid. Its records were preserved.'
  fi
  awk -F '\t' '
    seen[$1] { if (seen[$1]!=$0) exit 1; next }
    tags[$2] { exit 1 }
    { seen[$1]=$0; tags[$2]=1; print }
  ' "$temporary/catalog.new" "$temporary/catalog.old" > "$temporary/catalog.merged" || fail 'Version catalog records conflict. Existing records were preserved.'
  [ "$(wc -c < "$temporary/catalog.merged")" -le 1048576 ] || fail 'The merged version catalog is too large. Existing records were preserved.'
  mv "$temporary/catalog.merged" "$temporary/catalog"
fi
target=$packages/$source
safe "$target"
if [ -e "$target" ]; then
  [ -d "$target" ] || fail 'The stored version is invalid.'
  for file in compose.yaml start.sh .env.example release.env manifest.json README.txt data-contract.env; do
    safe "$target/$file"
    cmp -s "$target/$file" "$temporary/package/$file" || fail 'An existing frozen version differs. Its files and data were preserved.'
  done
  # Legacy adoption preserves its original runner; these two management files
  # were absent from the original seven-file deployment package.
  for file in capstone.sh install.sh; do
    safe "$target/$file"
    if [ -e "$target/$file" ]; then
      cmp -s "$target/$file" "$temporary/package/$file" || fail 'An existing management file differs.'
    else
      cp "$temporary/package/$file" "$target/$file"
    fi
  done
else
  mv "$temporary/package" "$target"
fi
for file in .env capstone.sh; do safe "$destination/$file"; done
if [ ! -f "$destination/.env" ]; then cp "$target/.env.example" "$destination/.env"; fi
for file in install.sh versions.tsv legacy-data-contract.env; do safe "$meta/$file"; safe "$meta/$file.new"; done
safe "$destination/capstone.sh.new"
cp "$target/capstone.sh" "$destination/capstone.sh.new"
mv "$destination/capstone.sh.new" "$destination/capstone.sh"
chmod 700 "$destination/capstone.sh"
cp "$target/install.sh" "$meta/install.sh.new"
mv "$meta/install.sh.new" "$meta/install.sh"
cp "$temporary/catalog" "$meta/versions.tsv.new"
mv "$meta/versions.tsv.new" "$meta/versions.tsv"
if [ -f "$target/legacy-data-contract.env" ]; then
  if [ -f "$meta/legacy-data-contract.env" ]; then
    cmp -s "$meta/legacy-data-contract.env" "$target/legacy-data-contract.env" || fail 'The legacy data declaration differs.'
  else
    cp "$target/legacy-data-contract.env" "$meta/legacy-data-contract.env.new"
    mv "$meta/legacy-data-contract.env.new" "$meta/legacy-data-contract.env"
  fi
fi
rmdir "$locked"
locked=''
index=0
for kind in BACKEND APP POSTGRES OBJECTS; do
  index=$((index + 1))
  image=$(sed -n "s/^CAPSTONE_${kind}_IMAGE=//p" "$target/release.env")
  if [ -n "${CAPSTONE_OFFLINE_DIRECTORY:-}" ]; then
    case "$image" in sha256:*) ;; *) fail 'Offline image identity is invalid.';; esac
    tail=${image#sha256:}
    case "$tail" in *[!0-9a-f]*|'') fail 'Offline image identity is invalid.';; esac
    [ "${#tail}" -eq 64 ] || fail 'Offline image identity is invalid.'
    actual=$(docker image inspect --format '{{.Id}}' "$image") || fail 'An offline image is missing.'
    [ "$actual" = "$image" ] || fail 'Offline image identity differs.'
    actual=$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$image")
    [ "$actual" = linux/amd64 ] || fail 'Offline image platform differs.'
    continue
  fi
  case "$image" in
    registry.cn-beijing.aliyuncs.com/uukuguy/capstone-*@sha256:*|ghcr.io/uukuguy/capstone-*@sha256:*) ;;
    *) fail 'Release image identity is invalid.';;
  esac
  tail=${image##*@sha256:}
  case "$tail" in *[!0-9a-f]*|'') fail 'Release image digest is invalid.';; esac
  [ "${#tail}" -eq 64 ] || fail 'Release image digest is invalid.'
  printf '\nPulling image %s/4 (%s). Docker layer progress follows.\n' "$index" "$kind"
  docker pull "$image"
done
printf '\nChecking data compatibility and starting user-local...\n'
sh "$destination/capstone.sh" start "$source"
