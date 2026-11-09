#!/bin/sh
# 首次启动时把镜像内置的记忆数据播种到挂载卷，之后卷里的数据为准（重启不丢）
if [ ! -e /app/data/memory ] && [ -d /app/data_seed/memory ]; then
  echo "[entrypoint] 播种记忆数据到 data/"
  cp -rn /app/data_seed/* /app/data/ 2>/dev/null
fi
exec python /app/main.py
