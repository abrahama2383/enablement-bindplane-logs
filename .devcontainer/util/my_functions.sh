#!/bin/bash
# ======================================================================
#          ------- Custom Functions -------                            #
#  Space for adding custom functions so each repo can customize as.    # 
#  needed.                                                             #
# ======================================================================


customFunction(){
  printInfoSection "This is a custom function that calculates 1 + 1"

  printInfo "1 + 1 = $(( 1 + 1 ))"

}

startLogGenerator(){
local logdir="${1:-/var/log/bpsystem}"

# Ensure the target directory exists and is writable by the current user.
if [ ! -d "$logdir" ]; then
  sudo mkdir -p "$logdir"
fi
if [ ! -w "$logdir" ]; then
  sudo chown -R "$USER":"$USER" "$logdir"
fi

nohup python3 .devcontainer/util/generate_logs.py \
  --logdir "$logdir" \
  --scenario leak_bch_key \
  --scenario-after 20 \
  --scenario-repeat 50 \
  --interval 0.5 \
  --quiet > /dev/null 2>&1 &
echo $! > ./generator.pid  # save the PID so you can kill it later
}

stopLogGenerator(){
if [ -f ./generator.pid ]; then
  local pid
  pid="$(cat ./generator.pid)"
  if [ -n "$pid" ] && ps -p "$pid" > /dev/null 2>&1; then
    kill "$pid"
  fi
fi
}

startBindplane(){
  sudo env \
  PATH=/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin \
  BINDPLANE_COLLECTOR_HOME=/opt/observiq-otel-collector \
  BINDPLANE_COLLECTOR_STORAGE=/opt/observiq-otel-collector/storage \
  sh -c 'cd /opt/observiq-otel-collector && /opt/observiq-otel-collector/observiq-otel-collector --config config.yaml' &
}

stopBindplane(){
  sudo pkill -f observiq-otel-collector
}