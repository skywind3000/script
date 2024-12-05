#!/bin/bash

if [ -f /sys/kernel/debug/sched_features ]; then
    if grep -wq RT_RUNTIME_SHARE /sys/kernel/debug/sched_features; then
        echo NO_RT_RUNTIME_SHARE >/sys/kernel/debug/sched_features
    fi
fi

