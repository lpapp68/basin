#!/bin/bash
# elonezet.sh — kitétel előnézeti címre: https://elonezet.basin-8fn.pages.dev
#
# Ugyanaz a csomag és ugyanazok az ellenőrzések, mint a publikal.sh-ban, de a Cloudflare Pages előnézeti ágára.
# Az éles basin.equora.institute érintetlen marad; az élesítés a publikal.sh.
set -euo pipefail
cd "$(dirname "$0")"
BASIN_AG=elonezet bash ./publikal.sh
echo ""
echo "Előnézet: https://elonezet.basin-8fn.pages.dev"
