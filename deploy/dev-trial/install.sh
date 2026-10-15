#!/bin/sh
# POSIX entry: curl <entry URL> | sh -s -- [Git revision]
set -eu
LC_ALL=C
export LC_ALL
umask 077

fail() { printf '%s\n' "$1" >&2; exit 1; }
work=$(mktemp -d "${TMPDIR:-/tmp}/capstone-entry.XXXXXXXX") || exit 1
cleanup() {
    rm -f "$work/catalog" "$work/records" "$work/selected" "$work/install.sh"
    rmdir "$work"
}
trap cleanup 0
trap 'exit 1' HUP INT TERM

# Time and size limits also apply to redirects. Suppress remote diagnostics.
download() {
    curl --disable --fail --silent --show-error --location --max-redirs 5 \
        --proto '=https' --proto-redir '=https' --connect-timeout 15 \
        --max-time 60 --max-filesize "$3" -o "$2" "$1" 2>/dev/null || return 1
    [ "$(wc -c < "$2")" -le "$3" ]
}
download 'https://raw.githubusercontent.com/uukuguy/capstone/dev/docs/status/USER-LOCAL-VERSIONS.tsv' \
    "$work/catalog" 1048576 || fail 'Cannot download the release catalog.'

# Validate the complete catalog before using or displaying any record.
awk -F '\t' '
function hex(s,n) { return length(s)==n && s !~ /[^0-9a-f]/ }
function date(s, a,y,m,d,days) {
    if (length(s)!=10 || s !~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$/) return 0
    split(s,a,"-"); y=a[1]+0; m=a[2]+0; d=a[3]+0
    if (y<1 || m<1 || m>12) return 0
    days=31
    if (m==4 || m==6 || m==9 || m==11) days=30
    if (m==2) days=28+(y%4==0 && (y%100!=0 || y%400==0))
    return d>=1 && d<=days
}
/^#/ || /^$/ { next }
{
    prefix=substr($2,12)
    if (NF!=5 || !hex($1,40) || substr($2,1,11)!="user-local-" ||
        length(prefix)<7 || length(prefix)>40 || prefix ~ /[^0-9a-f]/ ||
        substr($1,1,length(prefix))!=prefix ||
        $3!="https://github.com/uukuguy/capstone/releases/download/" $2 "/install.sh" ||
        !hex($4,64) || !date($5) || sources[$1]++ || versions[$2]++) { bad=1; exit }
    source[++count]=$1; version[count]=$2; url[count]=$3; digest[count]=$4; published[count]=$5
}
END {
    if (bad || !count) exit 1
    for (i=1;i<=count;i++) print source[i] "\t" version[i] "\t" url[i] "\t" digest[i] "\t" published[i]
}' "$work/catalog" > "$work/records" || fail 'The release catalog is invalid.'

list() {
    printf '%s\n' 'Available Git revisions:'
    awk -F '\t' '{ print $1 "  " $2 "  " $5 }' "$work/records"
}
invalid() { printf '%s\n' 'Select one available Git revision, or use --list.' >&2; list; exit 1; }
[ "$#" -le 1 ] || invalid
if [ "$#" -eq 0 ]; then
    sed -n '1p' "$work/records" > "$work/selected"
elif [ "$1" = '--list' ]; then
    list
    exit 0
elif [ "$1" = '--catalog' ]; then
    cat "$work/records"
    exit 0
else
    case "$1" in ''|*[!0-9a-f]*) invalid ;; esac
    [ "${#1}" -ge 7 ] && [ "${#1}" -le 40 ] || invalid
    awk -F '\t' -v revision="$1" 'index($1,revision)==1 { print; count++ }
        END { if (count!=1) exit 1 }' "$work/records" > "$work/selected" || invalid
fi
tab=$(printf '\t')
IFS="$tab" read -r source version url digest published < "$work/selected"
download "$url" "$work/install.sh" 1048576 || fail 'Cannot download the release installer.'
if command -v sha256sum >/dev/null 2>&1; then
    actual=$(sha256sum "$work/install.sh") || fail 'Cannot check the installer checksum.'
elif command -v shasum >/dev/null 2>&1; then
    actual=$(shasum -a 256 "$work/install.sh") || fail 'Cannot check the installer checksum.'
else
    fail 'Install sha256sum or shasum to check the installer.'
fi
[ "${actual%% *}" = "$digest" ] || fail 'The installer checksum does not match.'
awk -v expected="source=\047$source\047" '
    /^source=/ { count++; if ($0!=expected) bad=1 }
    END { if (count!=1 || bad) exit 1 }
' "$work/install.sh" || fail 'The installer source revision does not match.'
CAPSTONE_INSTALL_CATALOG="$work/records" sh "$work/install.sh"
