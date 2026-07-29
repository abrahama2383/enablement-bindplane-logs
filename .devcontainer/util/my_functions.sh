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
nohup python3 .devcontainer/util/generate_logs.py --logdir ./logs --quiet > /dev/null 2>&1 &
echo $! > ./generator.pid  # save the PID so you can kill it later
}

stopLogGenerator(){
sudo kill $(cat ./generator.pid)
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