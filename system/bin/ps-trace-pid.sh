#!/bin/sh
pid=$1
if [ -z "$pid" ]; then
	echo "usage: $0 {pid}"
	exit 1
fi
echo "Tracing PID path for: $pid"
while [ "$pid" -ne 1 ]; do
    cmd="$(ps -p $pid -o comm=)"
    echo "Current PID: $pid -> $cmd"
    pid="$(ps -o ppid= -p $pid)"
	pid="$(echo $pid | sed 's/^[[:space:]]*//')"
    if [ -z "$pid" ]; then
        echo "No more parents found."
        break
    fi
done
echo "Reached PID 1."

