#!/bin/sh
# User-local lifecycle manager. Frozen runners retain authority over receipts.
set -eu
umask 077
LC_ALL=C
export LC_ALL
fail() { printf '%s\n' "$1" >&2; exit 1; }
[ ! -L "$0" ] || fail 'The manager must not be a symbolic link.'
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
meta=$root/.capstone-management
packages=$root/versions
safe() { [ ! -L "$1" ] || fail 'A managed path is a symbolic link.'; }
directory() { safe "$1"; [ ! -e "$1" ] || [ -d "$1" ] || fail 'A managed directory is invalid.'; mkdir -p "$1"; chmod 700 "$1"; }
sha_ok() { case "$1" in ''|*[!0-9a-f]*) return 1;; esac; [ "${#1}" -eq 40 ]; }
project_ok() { case "$1" in capstone-user-?*) ;; *) return 1;; esac; case "$1" in *[!a-z0-9_-]*) return 1;; esac; [ "${#1}" -le 100 ]; }
digest() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"; else shasum -a 256 "$1"; fi; }
hash() { h=$(digest "$1") || return 1; printf '%s\n' "${h%% *}"; }
directory "$meta"
for name in versions.tsv install.sh identity active lock project data-contract.env legacy-data-contract.env; do safe "$meta/$name"; done
command=${1:-start}
[ "$#" -eq 0 ] || shift
case "$command" in start|use|switch|install) [ "$#" -le 1 ] || fail 'Use at most one Git revision.';; stop|status|logs|versions) [ "$#" -eq 0 ] || fail 'This command takes no revision.';; *) fail 'Use start, use, switch, stop, status, logs, versions or install.';; esac
requested=${1:-}
# install deliberately runs outside the lifecycle lock. Its fixed installer calls start.
if [ "$command" = install ]; then
    [ -f "$meta/install.sh" ] || fail 'The installation bootstrap is missing.'
    if [ "$#" -eq 1 ]; then
        CAPSTONE_TRIAL_DIRECTORY=$root sh "$meta/install.sh" "$requested"
    else
        CAPSTONE_TRIAL_DIRECTORY=$root sh "$meta/install.sh"
    fi
    exit $?
fi
command -v docker >/dev/null 2>&1 || fail 'Docker is required.'
docker compose version >/dev/null 2>&1 || fail 'Docker Compose is required.'
# All commands lock: readers must not observe partial registration or migration.
mkdir "$meta/lock" 2>/dev/null || fail 'Another manager operation holds the lock. Check it before removing .capstone-management/lock.'
work=$meta/lock
cleanup() {
    if [ -d "$work/legacy" ]; then
        rm -f "$work/legacy"/* "$work/legacy/.env" "$work/legacy/.env.example"
        rmdir "$work/legacy"
    fi
    rm -f "$work"/*
    rmdir "$work"
}
trap cleanup 0
trap 'exit 1' HUP INT TERM
directory "$packages"
directory "$meta/registered"
directory "$meta/logs"
safe "$root/.env"
: > "$work/redact-env"
if [ -f "$root/.env" ]; then cp "$root/.env" "$work/redact-env"; fi
[ -f "$meta/versions.tsv" ] || fail 'The available version registry is missing. Run install.'
[ "$(wc -c < "$meta/versions.tsv")" -le 1048576 ] || fail 'The available version registry is too large.'
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
      !date($5) || seen[$1]++ || tags[$2]++) exit 1
  print
}' "$meta/versions.tsv" > "$work/available" || fail 'The available version registry is invalid.'
[ -s "$work/available" ] || fail 'The available version registry is empty.'
known() { awk -F '\t' -v s="$1" '$1==s { found=1 } END { exit !found }' "$work/available"; }
if [ ! -f "$meta/identity" ]; then
    # mktemp supplies an installation-local random identity without credentials.
    seed=$(mktemp "$work/id.XXXXXXXX") || fail 'Cannot create the installation identity.'
    printf '%s\n' "${seed##*.}" | tr 'A-Z' 'a-z' > "$work/identity"
    mv "$work/identity" "$meta/identity"
fi
identity=$(cat "$meta/identity")
case "$identity" in ''|*[!a-z0-9]*) fail 'The installation identity is invalid.';; esac
[ "${#identity}" -le 40 ] || fail 'The installation identity is invalid.'
# Read bounded scalar JSON fields only. No input is sourced or evaluated.
scalar() {
    [ "$(wc -c < "$1")" -le 1048576 ] || return 1
    awk -v key="$2" '
    { all=all $0 }
    END { pattern="\"" key "\"[[:space:]]*:[[:space:]]*\"[^\"]*\""
      if (!match(all,pattern)) exit 1
      value=substr(all,RSTART,RLENGTH); rest=substr(all,RSTART+RLENGTH)
      if (match(rest,pattern)) exit 1
      sub(/^[^:]*:[[:space:]]*"/,"",value); sub(/"$/,"",value)
      print value
    }' "$1"
}
contract() {
    safe "$1"
    [ -f "$1" ] && [ "$(wc -c < "$1")" -le 512 ] || return 1
    awk -F= -v source="$2" '
      NF!=2 { exit 1 }
      $1=="CAPSTONE_DATA_CONTRACT_VERSION" { if ($2!="1" || v++) exit 1; next }
      $1=="CAPSTONE_DATA_SOURCE_REVISION" { if ($2!=source || s++) exit 1; next }
      $1=="CAPSTONE_DATA_FORMAT_SHA256" { if (length($2)!=64 || $2~/[^0-9a-f]/ || f++) exit 1; fingerprint=$2; next }
      { exit 1 }
      END { if (v!=1 || s!=1 || f!=1) exit 1; print fingerprint }
    ' "$1"
}
package_check() {
    pc=$packages/$1
    safe "$pc"
    [ -d "$pc" ] || return 1
    for f in compose.yaml start.sh .env.example release.env manifest.json README.txt; do
        safe "$pc/$f"; [ -f "$pc/$f" ] || return 1
    done
    safe "$pc/.env"; safe "$pc/.capstone-trial"
    source=$(scalar "$pc/manifest.json" source_revision) || return 1
    [ "$source" = "$1" ] || return 1
    contract "$pc/data-contract.env" "$1" >/dev/null || return 1
    : > "$work/binding"
    printf '%s\n' "$1" >> "$work/binding"
    for key in BACKEND APP POSTGRES OBJECTS; do
        ref=$(sed -n "s/^CAPSTONE_${key}_IMAGE=//p" "$pc/release.env")
        case "$ref" in ghcr.io/uukuguy/*@sha256:*|registry.cn-beijing.aliyuncs.com/uukuguy/*@sha256:*) ;; *) return 1;; esac
        case "$ref" in *[!a-z0-9._:/@-]*) return 1;; esac
        tail=${ref##*@sha256:}
        [ "${#tail}" -eq 64 ] || return 1
        case "$tail" in *[!0-9a-f]*) return 1;; esac
        lower=$(printf '%s' "$key" | tr 'A-Z' 'a-z')
        manifest_ref=$(scalar "$pc/manifest.json" "$lower") || return 1
        [ "$manifest_ref" = "$ref" ] || return 1
        printf '%s=%s\n' "$key" "$ref" >> "$work/binding"
    done
    for f in manifest.json release.env start.sh compose.yaml .env.example README.txt data-contract.env; do
        checksum=$(hash "$pc/$f") || return 1
        printf '%s %s\n' "$checksum" "$f" >> "$work/binding"
    done
}
# Copy legacy files inside this installation only. Never rewrite the original receipt.
safe "$root/.capstone-trial"
if [ -d "$root/.capstone-trial" ]; then
    legacy_count=0
    # Detect all conflicts before copying any legacy package or state.
    for old in "$root/.capstone-trial"/*; do
        [ -e "$old" ] || [ -L "$old" ] || continue
        safe "$old"; safe "$old/installation.json"
        if [ -f "$old/installation.json" ]; then legacy_count=$((legacy_count + 1)); fi
    done
    [ "$legacy_count" -le 1 ] || fail 'Multiple legacy instances exist. Resolve their mapping before migration.'
    legacy_count=0
    for old in "$root/.capstone-trial"/*; do
        [ -e "$old" ] || [ -L "$old" ] || continue
        safe "$old"
        [ -d "$old" ] || fail 'A legacy instance path is invalid.'
        safe "$old/installation.json"; safe "$old/internal.env"
        [ -f "$old/installation.json" ] || continue
        legacy_count=$((legacy_count + 1))
        [ "$legacy_count" -eq 1 ] || fail 'Multiple legacy instances exist. Resolve their mapping before migration.'
        legacy_project=$(scalar "$old/installation.json" instance) || fail 'The legacy instance receipt is invalid.'
        project_ok "$legacy_project" && [ "${old##*/}" = "$legacy_project" ] || fail 'The legacy project is unsafe.'
        legacy_source=$(scalar "$old/installation.json" source_revision) || fail 'The legacy source is missing.'
        sha_ok "$legacy_source" || fail 'The legacy source is invalid.'
        if ! known "$legacy_source"; then
            safe "$meta/registered/$legacy_source"
            safe "$meta/registered/$legacy_source/binding"
            [ -f "$meta/registered/$legacy_source/binding" ] || fail 'The legacy source is not a published or registered version.'
        fi
        [ -f "$old/internal.env" ] || fail 'The legacy private configuration is missing.'
        for f in compose.yaml start.sh .env .env.example release.env manifest.json README.txt; do
            safe "$root/$f"; [ -f "$root/$f" ] || fail 'The legacy package is incomplete.'
        done
        root_source=$(scalar "$root/manifest.json" source_revision) || fail 'The legacy manifest is invalid.'
        [ "$root_source" = "$legacy_source" ] || fail 'The legacy manifest and receipt have different sources.'
        contract "$meta/legacy-data-contract.env" "$legacy_source" >/dev/null || fail 'A trusted legacy data contract is required.'
        # Check original image identity before attaching the trusted declaration.
        for key in backend app postgres objects; do
            original=$(scalar "$old/installation.json" "$key") || fail 'The legacy receipt image identity is missing.'
            expected=$(scalar "$root/manifest.json" "$key") || fail 'The legacy manifest image identity is missing.'
            [ "$original" = "$expected" ] || fail 'The legacy receipt image identity differs.'
        done
        dest=$packages/$legacy_source
        safe "$dest"
        if [ ! -e "$dest" ]; then
            directory "$work/legacy"
            for f in compose.yaml start.sh .env .env.example release.env manifest.json README.txt; do cp "$root/$f" "$work/legacy/$f"; done
            mv "$work/legacy" "$dest"
        else
            for f in compose.yaml start.sh .env.example release.env manifest.json README.txt; do
                safe "$dest/$f"; cmp -s "$root/$f" "$dest/$f" || fail 'The stored package conflicts with the legacy package.'
            done
        fi
        safe "$dest/data-contract.env"
        if [ -f "$dest/data-contract.env" ]; then
            cmp -s "$dest/data-contract.env" "$meta/legacy-data-contract.env" || fail 'The legacy data contract differs.'
        else cp "$meta/legacy-data-contract.env" "$dest/data-contract.env"; fi
        directory "$dest/.capstone-trial"
        target=$dest/.capstone-trial/$legacy_project
        directory "$target"
        for f in installation.json internal.env; do
            safe "$target/$f"
            if [ -e "$target/$f" ]; then
                # The original runner owns its copy after registration.
                if [ ! -f "$meta/registered/$legacy_source/project" ]; then
                    cmp -s "$old/$f" "$target/$f" || fail 'The legacy state conflicts with the stored state.'
                fi
            else cp "$old/$f" "$target/$f"; chmod 600 "$target/$f"; fi
        done
    done
fi
if [ -f "$meta/project" ]; then stable_project=$(cat "$meta/project")
else stable_project=${legacy_project:-capstone-user-$identity}; fi
project_ok "$stable_project" || fail 'The installation project is unsafe.'
[ "$stable_project" = "${legacy_project:-capstone-user-$identity}" ] || fail 'The project does not belong to this installation.'
printf '%s\n' "$stable_project" > "$meta/project"
: > "$work/installed"
awk -F '\t' '{ print $1 }' "$work/available" > "$work/sources"
for record in "$meta/registered"/*; do
    [ -e "$record" ] || [ -L "$record" ] || continue
    safe "$record"
    revision=${record##*/}
    sha_ok "$revision" || fail 'A registered source path is invalid.'
    printf '%s\n' "$revision" >> "$work/sources"
done
sort -u "$work/sources" > "$work/unique-sources"
while IFS= read -r revision; do
    [ -d "$packages/$revision" ] || continue
    if ! package_check "$revision"; then
        [ ! -e "$meta/registered/$revision" ] || fail 'A registered package is incomplete or its immutable binding has changed.'
        continue
    fi
    record=$meta/registered/$revision
    directory "$record"
    safe "$record/project"; safe "$record/binding"; safe "$record/binding.new"
    project=$stable_project
    if [ -f "$record/project" ]; then
        project=$(cat "$record/project")
        project_ok "$project" || fail 'A registered project is unsafe.'
        [ "$project" = "$stable_project" ] || fail 'The project does not belong to this installation.'
    fi
    if [ -f "$record/binding" ]; then cmp -s "$record/binding" "$work/binding" || fail 'An immutable package has changed.'
    else cp "$work/binding" "$record/binding.new"; mv "$record/binding.new" "$record/binding"; fi
    printf '%s\n' "$project" > "$work/project"
    mv "$work/project" "$record/project"
    state=$packages/$revision/.capstone-trial
    safe "$state"; safe "$state/$project"
    for f in internal.env installation.json last-operation.log config-check.log; do safe "$state/$project/$f"; done
    printf '%s\t%s\n' "$revision" "$project" >> "$work/installed"
done < "$work/unique-sources"
active=${legacy_source:-}
if [ -f "$meta/active" ]; then
    active=$(cat "$meta/active")
    sha_ok "$active" && [ -f "$meta/registered/$active/project" ] || fail 'The active revision is invalid.'
fi
marker_path=$meta/data-contract.env
# A verified legacy declaration describes existing data without publishing a
# new acceptance marker before the target runner succeeds.
if [ ! -f "$marker_path" ] && [ ! -f "$meta/active" ] && [ -n "${legacy_source:-}" ]; then
    marker_path=$meta/legacy-data-contract.env
fi
if [ -f "$marker_path" ]; then
    marker_source=$(sed -n 's/^CAPSTONE_DATA_SOURCE_REVISION=//p' "$marker_path")
    sha_ok "$marker_source" || fail 'The data contract source is invalid.'
    marker_format=$(contract "$marker_path" "$marker_source") || fail 'The data contract is invalid.'
    [ -f "$meta/registered/$marker_source/binding" ] || fail 'The data contract owner is not registered.'
    owner_format=$(contract "$packages/$marker_source/data-contract.env" "$marker_source") || fail 'The data contract owner is invalid.'
    [ "$marker_format" = "$owner_format" ] || fail 'The data contract differs from its owner.'
    if [ -n "$active" ]; then
        active_format=$(contract "$packages/$active/data-contract.env" "$active") || fail 'The active data contract is invalid.'
        [ "$active_format" = "$marker_format" ] || fail 'The active data format differs.'
    fi
elif [ -n "$active" ]; then fail 'Existing data requires its data contract.'
fi
# Discover actual immutable image IDs, then require all four exact package refs.
docker image ls --all --no-trunc --quiet > "$work/images" || fail 'Cannot list cached Docker images.'
: > "$work/discovered"
sort -u "$work/images" > "$work/ids"
while IFS= read -r image; do
    [ -n "$image" ] || continue
    revision=$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$image" 2>/dev/null) || continue
    sha_ok "$revision" && known "$revision" || continue
    printf '%s\t%s\n' "$revision" "$image" >> "$work/discovered"
done < "$work/ids"
: > "$work/cached"
while IFS="$(printf '\t')" read -r revision project; do
    backend=$(sed -n 's/^CAPSTONE_BACKEND_IMAGE=//p' "$packages/$revision/release.env")
    image=$(docker image inspect --format '{{.Id}}' "$backend" 2>/dev/null) || continue
    awk -F '\t' -v s="$revision" -v i="$image" '$1==s && $2==i { found=1 } END { exit !found }' "$work/discovered" || continue
    complete=1
    for key in APP POSTGRES OBJECTS; do
        ref=$(sed -n "s/^CAPSTONE_${key}_IMAGE=//p" "$packages/$revision/release.env")
        docker image inspect --format '{{.Id}}' "$ref" >/dev/null 2>&1 || complete=0
    done
    [ "$complete" -eq 1 ] || continue
    created=$(docker image inspect --format '{{.Created}}' "$image" 2>/dev/null) || continue
    case "$created" in ????-??-??T*) ;; *) continue;; esac
    printf '%s\t%s\n' "$created" "$revision" >> "$work/cached"
done < "$work/installed"
sort -r "$work/cached" > "$work/newest"
running() {
    containers=$(docker ps --filter "label=com.docker.compose.project=$1" --format '{{.ID}}') || fail 'Cannot inspect running projects.'
    [ -n "$containers" ]
}
if [ -z "$active" ] && running "$stable_project"; then fail 'The running installation requires its active revision.'; fi
list() {
    printf '%s\n' 'Available versions (Git / package / state):'
    while IFS="$(printf '\t')" read -r revision tag url checksum published; do
        label=available
        project=$(awk -F '\t' -v s="$revision" '$1==s { print $2 }' "$work/installed")
        [ -z "$project" ] || label=installed
        if awk -F '\t' -v s="$revision" '$2==s { found=1 } END { exit !found }' "$work/cached"; then label=cached; fi
        if [ "$revision" = "$active" ] && running "$project"; then label="$label running"; fi
        printf '%s  %s  %s\n' "$revision" "$tag" "$label"
    done < "$work/available"
    while IFS="$(printf '\t')" read -r revision project; do
        if ! known "$revision"; then
            label='installed (not currently available)'
            if [ "$revision" = "$active" ] && running "$project"; then label="$label running"; fi
            printf '%s  %s\n' "$revision" "$label"
        fi
    done < "$work/installed"
}
if [ "$command" = versions ]; then list; exit 0; fi
# Redact inherited keys and .env values while streaming diagnostics.
redact() {
    awk '
      function hide(line, secret, pos) {
        if (secret=="") return line
        out=""
        while ((pos=index(line,secret))>0) { out=out substr(line,1,pos-1) "[redacted]"; line=substr(line,pos+length(secret)) }
        return out line
      }
      BEGIN { for (key in ENVIRON) if (key ~ /KEY|TOKEN|PASSWORD|SECRET|CREDENTIAL/) values[++n]=ENVIRON[key] }
      FILENAME==ARGV[1] { if ($0 ~ /^[A-Za-z_][A-Za-z0-9_]*=/) { v=$0; sub(/^[^=]*=/,"",v); if (v!="") values[++n]=v } next }
      { line=$0; for (i=1;i<=n;i++) line=hide(line,values[i]); print line }
    ' "$work/redact-env" -
}
run() {
    rr=$1; operation=$2
    rp=$(cat "$meta/registered/$rr/project")
    private=$packages/$rr/.capstone-trial/$rp/internal.env
    safe "$private"
    if [ -f "$private" ]; then cat "$private" >> "$work/redact-env"; fi
    log=$meta/logs/$rr-$operation.log
    safe "$log"
    (
        set +e
        CAPSTONE_INSTANCE=$rp sh "$packages/$rr/start.sh" "$operation"
        result=$?
        printf '%s\n' "$result" > "$work/result"
    ) 2>&1 | redact > "$work/diagnostic" || return 1
    mv "$work/diagnostic" "$log" || return 1
    result=$(cat "$work/result")
    rm -f "$work/result"
    [ "$result" -eq 0 ]
}
if [ "$command" = status ]; then
    list
    printf 'Installation: %s\n' "$root"
    failed=0
    while IFS="$(printf '\t')" read -r revision project; do
        if [ "$revision" = "$active" ] && running "$project"; then
            if run "$revision" status; then cat "$meta/logs/$revision-status.log"
            else failed=1; printf 'Status failed for %.7s. Check private diagnostics.\n' "$revision" >&2; fi
        fi
    done < "$work/installed"
    exit "$failed"
fi
if [ "$command" = stop ] || [ "$command" = logs ]; then
    failed=0
    while IFS="$(printf '\t')" read -r revision project; do
        if [ "$revision" = "$active" ] && running "$project"; then
            if run "$revision" "$command"; then
                if [ "$command" = logs ]; then cat "$meta/logs/$revision-logs.log"; fi
            else failed=1; printf 'Operation failed for %.7s. Check private diagnostics.\n' "$revision" >&2; fi
        fi
    done < "$work/installed"
    [ "$failed" -eq 0 ] || exit 1
    if [ "$command" = stop ]; then printf '%s\n' 'User-local services stopped. All data is retained.'; fi
    exit 0
fi
selected=''
case "$command" in use|switch) [ "$#" -eq 1 ] || { list; fail 'Select a Git revision to switch versions.'; };; esac
if [ "$#" -eq 1 ]; then
    case "$requested" in *[!0-9a-f]*) list; fail 'Use a Git revision of 7 to 40 hexadecimal characters.';; esac
    [ "${#requested}" -ge 7 ] && [ "${#requested}" -le 40 ] || { list; fail 'Use a Git revision of 7 to 40 hexadecimal characters.'; }
    selected=$(awk -F '\t' -v s="$requested" 'index($1,s)==1 { found=$1; n++ } END { if (n!=1) exit 1; print found }' "$work/available") || { list; fail 'The revision is unknown or ambiguous.'; }
    awk -F '\t' -v s="$selected" '$2==s { found=1 } END { exit !found }' "$work/cached" || { list; fail 'This version is not installed and fully cached. Use install with its Git revision.'; }
else
    selected=$(sed -n '1s/^[^	]*	//p' "$work/newest")
    [ -n "$selected" ] || { list; fail 'No eligible cached version exists. Use install.'; }
fi
safe "$root/.env"
[ -f "$root/.env" ] || fail 'The shared .env is missing.'
port=${CAPSTONE_APP_PORT:-$(sed -n 's/^CAPSTONE_APP_PORT=//p' "$root/.env")}
[ -n "$port" ] || port=19173
case "$port" in *[!0-9]*) fail 'CAPSTONE_APP_PORT must be a port number.';; esac
[ "${#port}" -le 5 ] && [ "$port" -ge 1 ] && [ "$port" -le 65535 ] || fail 'CAPSTONE_APP_PORT is outside 1 to 65535.'
cp "$root/.env" "$work/env"
mv "$work/env" "$packages/$selected/.env"
target_format=$(contract "$packages/$selected/data-contract.env" "$selected") || fail 'The selected data contract is invalid.'
if [ -n "${marker_format:-}" ]; then
    [ "$target_format" = "$marker_format" ] || fail 'The data format differs. A developer migration is required.'
else
    existing=$(docker ps -a --filter "label=com.docker.compose.project=$stable_project" --format '{{.ID}}') || fail 'Cannot inspect existing data.'
    volumes=$(docker volume ls --filter "label=com.docker.compose.project=$stable_project" --format '{{.Name}}') || fail 'Cannot inspect existing data.'
    [ -z "$existing$volumes" ] || fail 'Existing data requires its data contract.'
    for record in "$meta/registered"/*; do
        for file in installation.json internal.env; do
            [ ! -f "$packages/${record##*/}/.capstone-trial/$stable_project/$file" ] || fail 'Existing data requires its data contract.'
        done
    done
fi
target_state=$packages/$selected/.capstone-trial/$stable_project
directory "$target_state"
if [ -n "${marker_format:-}" ]; then
    owner=${active:-$marker_source}
    private=$packages/$owner/.capstone-trial/$stable_project/internal.env
    safe "$private"; [ -f "$private" ] || fail 'Restore the shared private configuration before switching.'
    if [ -f "$target_state/internal.env" ]; then
        cmp -s "$private" "$target_state/internal.env" || fail 'The shared private configuration differs.'
    else cp "$private" "$target_state/internal.env"; chmod 600 "$target_state/internal.env"; fi
fi
backend=$(sed -n 's/^CAPSTONE_BACKEND_IMAGE=//p' "$packages/$selected/release.env")
platform=$(sed -n 's/^CAPSTONE_TRIAL_PLATFORM=//p' "$packages/$selected/release.env")
case "$platform" in ''|linux/amd64|linux/arm64) ;; *) fail 'Unsupported trial platform.';; esac
helper() {
    set -- --rm --user "$(id -u):$(id -g)" -e "CAPSTONE_INSTANCE=$stable_project" \
        -v "$target_state:/state" -v "$packages/$selected/manifest.json:/bundle/manifest.json:ro" \
        --entrypoint /app/packages/capstone-agent/.venv/bin/python "$backend" /app/deploy/dev_trial_runtime.py "$1"
    if [ -n "$platform" ]; then docker run --platform "$platform" "$@"; else docker run "$@"; fi
}
preflight() {
    unset POSTGRES_PASSWORD S3_ACCESS_KEY S3_SECRET_KEY CAPSTONE_OPERATOR_TOKEN
    unset CAPSTONE_BACKEND_IMAGE CAPSTONE_APP_IMAGE CAPSTONE_POSTGRES_IMAGE CAPSTONE_OBJECTS_IMAGE CAPSTONE_TRIAL_PLATFORM
    helper init && docker compose --project-name "$stable_project" \
      --env-file "$packages/$selected/.env" --env-file "$packages/$selected/release.env" --env-file "$target_state/internal.env" \
      -f "$packages/$selected/compose.yaml" config --quiet && \
    docker compose --project-name "$stable_project" \
      --env-file "$packages/$selected/.env" --env-file "$packages/$selected/release.env" --env-file "$target_state/internal.env" \
      -f "$packages/$selected/compose.yaml" run --rm --no-deps config-check && helper record
}
if [ -f "$target_state/internal.env" ]; then cat "$target_state/internal.env" >> "$work/redact-env"; fi
(
    set +e
    (preflight) > "$work/preflight.log" 2>&1
    printf '%s\n' "$?" > "$work/preflight-result"
)
if [ -f "$target_state/internal.env" ]; then cat "$target_state/internal.env" >> "$work/redact-env"; fi
redact < "$work/preflight.log" > "$target_state/config-check.log"
rm -f "$work/preflight.log"
if [ "$(cat "$work/preflight-result")" -ne 0 ]; then
    fail 'Configuration preflight failed. Check private diagnostics.'
fi
: > "$work/prior"
while IFS="$(printf '\t')" read -r revision project; do
    if [ "$revision" = "$active" ] && running "$project"; then printf '%s\n' "$revision" >> "$work/prior"; fi
done < "$work/installed"
restore() {
    restore_failed=0
    # Only the prior active runner can restore this installation.
    prior=$(sed -n '1p' "$work/prior")
    if [ -n "$prior" ]; then
        if ! run "$prior" up; then restore_failed=1; printf 'Restore failed for %.7s. Check private diagnostics.\n' "$prior" >&2; fi
    fi
    return "$restore_failed"
}
while IFS= read -r prior; do
    [ "$prior" != "$selected" ] || continue
    if ! run "$prior" stop; then
        restore || :
        fail 'Cannot stop the prior version. Start was cancelled. Check private diagnostics.'
    fi
done < "$work/prior"
if ! run "$selected" up; then
    if run "$selected" stop; then restore || :
    else printf '%s\n' 'Cannot stop the failed version. Restore was withheld to prevent concurrent versions.' >&2; fi
    fail 'Start failed. Check .capstone-management/logs for private diagnostics.'
fi
printf '%s\n' "$selected" > "$work/active"
mv "$work/active" "$meta/active"
cp "$packages/$selected/data-contract.env" "$work/data-contract.env"
mv "$work/data-contract.env" "$meta/data-contract.env"
printf 'User-local ready: http://127.0.0.1:%s/\nInstallation: %s\nRunning Git: %.7s\n' "$port" "$root" "$selected"
printf '%s\n' 'Services: capstone.sh status | logs | stop | versions | use Git | install Git' 'Change CAPSTONE_APP_PORT in the shared .env to select the App port.'
