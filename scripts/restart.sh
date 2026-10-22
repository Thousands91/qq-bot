#!/usr/bin/env bash
# 重启机器人
set -e
cd "$(dirname "$0")"
bash stop.sh
sleep 2
bash run.sh
