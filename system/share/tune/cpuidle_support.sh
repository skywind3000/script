#!/bin/bash - 
set -o nounset                              # Treat unset variables as an error

function config_current()
{
    echo "cpuidle support: config_current"
    for p in `ls -d /sys/devices/system/cpu/cpu*/cpuidle/state*/disable|grep -Pv "state[01]"`;do
        echo "echo 1 > $p"
        echo 1 > $p
    done
}

if [ -e /sys/devices/system/cpu/cpu0/cpuidle/ ];then
    echo "cpuidle support: begin"
    config_current
    echo "cpuidle support: done"
else
    echo "cpuidle support:skipped because of cpuidle not exist"
fi
