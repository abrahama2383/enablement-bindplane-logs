#!/bin/bash
##############################################################
##  In here you add whatever action should happen after the container ha been created
##  such as exposing the application.
##############################################################
#Load the functions into the shell
source .devcontainer/util/source_framework.sh

# ensure hostname resolves (workaround for Rancher Desktop / Lima)
if ! getent hosts "$(hostname)" > /dev/null 2>&1; then
	echo "127.0.1.1 $(hostname)" | sudo tee -a /etc/hosts > /dev/null 2>&1
fi

startLogGenerator

#TODO: BeforeGoLive comment this so the Mkdocs are not exposed in the container.
# we want to monitor all interactions of the users in the live github pages.
#exposeMkdocs

printInfoSection "Your dev.container finished starting up"