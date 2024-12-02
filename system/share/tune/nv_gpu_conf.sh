#!/bin/bash
##set Persistence-M for nvidia gpu driver(eg. nvidia-smi -pm 1)

dir=$(cd `dirname $0`;pwd)

is_nv_gpu_host()
{
    gpu_info=$(lspci | grep NVIDIA)
    if [ ${#gpu_info} -gt 0 ];then
        echo "nvidia gpu host"
        return 1
    fi  

    return 0
}

is_gpu_driver_installed()
{
    driver_info=$(lsmod | grep nvidia)
    if [ ${#driver_info} -gt 0 ];then
        return 1
    fi  
    
    return 0
}

get_direct_up_port()
{
    dev=$1

    if [ -z "$dev" ]; then
        echo "ffff:ff.f"
        return 0
    fi

    if [ ! -e "/sys/bus/pci/devices/$dev" ]; then
        dev="0000:$dev"
    fi

    if [ ! -e "/sys/bus/pci/devices/$dev" ]; then
        echo "ffff:ff.f"
        return 0
    fi

    port=$(basename $(dirname $(readlink "/sys/bus/pci/devices/$dev")))

    echo $port
}

disable_upstream_pcie_ce()
{
    dev=$1
    port=$(get_direct_up_port $dev)

    if [ ! -e "/sys/bus/pci/devices/$port" ]; then
        echo "Error: device $port not found"
        return 1
    fi
    
    echo "mask ce: gpu:$1 direct up port:$port"
    setpci -s $port ecap_aer+0x14.W=f1c1
}

fatal_error_config_SD()
{
    dev=$1
    port=$(get_direct_up_port $dev)

    if [ ! -e "/sys/bus/pci/devices/$port" ]; then
        echo "Error: device $port not found"
        return 1
    fi

    echo "set aer_SD: gpu:$1 direct up port:$port"
    # config direct up port UESR(Uncorrectable Error Severity Register)
    # bit5: Surprise Down Error Severity = 0
    value=$(setpci -s $port ECAP_AER+0xc.b)
    bit_value=$((0x$value & 0x20))
    if [ "$bit_value" -eq 32 ]; then
        echo "Configuring direct up port $port"
        setpci -s $port ECAP_AER+0xc.b=0:20
    fi
}

fatal_error_config_DLP()
{
    dev=$1
    port=$(get_direct_up_port $dev)

    if [ ! -e "/sys/bus/pci/devices/$port" ]; then
        echo "Error: device $port not found"
        return 1
    fi

    echo "set aer_DLP: gpu:$1 direct up port:$port"
    # config direct up port UESR(Uncorrectable Error Severity Register)
    # bit4: DLP Error Severity = 0
    value=$(setpci -s $port ECAP_AER+0xc.b)
    bit_value=$((0x$value & 0x10))
    if [ "$bit_value" -eq 16 ]; then
        echo "Configuring direct up port $port"
        setpci -s $port ECAP_AER+0xc.b=0:10
    fi
}

nvlink_h800_check()
{
    reset=0

    for cc in {0..2}; do

    echo "check $cc; `date`"
    reset=0

    for i in {0..7}; do
        linksta=$(nvidia-smi nvlink -i $i -s)
        if echo "$linksta" | grep -i "inactive" ; then
            echo "nvlink inactive, reset gpu$i"
            fuser -k /dev/nvidia$i; nvidia-smi -r -i $i
            reset=1
        fi
    done

    output=$(nvidia-smi topo -p2p r)
    echo $output

    for i in {0..7}; do
        for j in {0..7}; do
        status=$(echo "$output" | awk -v i=$((i+2)) -v j=$((j+2)) 'NR==i{print $j}')
        #echo "GPU$i and GPU$j have $status"
        if [ "$status" = "NS" ]; then
            echo "nvlink p2p status NS, reset gpu$i"
            fuser -k /dev/nvidia$i; nvidia-smi -r -i $i
            reset=1
            output=$(nvidia-smi topo -p2p r)
            echo $output
            break
        fi
        done
    done

    if [ "$reset" = "0" ]; then
        echo "all nvlink ok"
        return 0
    fi

    done
}

# consumer gpu: nvidia-smi -pm 1
# server   gpu: nvidia-persistenced --persistence-mode
nvidia_smi_pm_on()
{
    consumer_gpu=$(lspci -d 10de::000300 | grep NVIDIA)
    if [ -n "$consumer_gpu" ];then
        nvidia-smi -pm 1
        echo "set Persistence-M for nvidia gpu driver success"
        return
    fi 

    nvidia-persistenced --persistence-mode
    echo "nvidia-persistenced starts with persistence mode enabled for all devices"
}

is_nv_gpu_host
if [ $? -eq 0 ];then
    echo "not nvidia gpu host. exit"
    exit 0
fi


product_name=$(dmidecode -t 1 | grep -i "Product Name:" | awk '{print toupper($3)}')
if [ -z "$product_name" ]; then
    product_name=$(cat /sys/devices/virtual/dmi/id/product_name | awk '{print toupper($0)}')
fi

##
# readme:
# h800/h20 machine:
# 1. mask gpu ce
# 2. set ct value
# 3. mask gpu direct up port ce (bare metal only)
#
# h800/h20 machine: tx bare metal only
# 1. mask gpu direct up port fatal error
# 2. amd(ag262): SDes & DLPes; intel(xg262): DLPes
#
# l20/l40 machine : tx bare metal only
# 1. mask gpu direct up port fatal error
# 2. amd(ag252): SDes
#
##

tx_bm_config()
{
    bdf=$1

    if [[ "$product_name" == "AG262" ]]; then
        fatal_error_config_SD $bdf
        fatal_error_config_DLP $bdf
    elif [[ "$product_name" == "XG262" ]]; then
        fatal_error_config_DLP $bdf
    elif [[ "$product_name" == "AG252" ]]; then
        fatal_error_config_SD $bdf
    else
        echo "no config"
    fi
}

# h800
gpu_info=$(lspci -d 10de:2324 -Dnn | awk '{print $1}')
if [ -z "$gpu_info" ];then
    # h20
    gpu_info=$(lspci -d 10de:2329 -Dnn | awk '{print $1}')
fi
if [ -n "$gpu_info" ];then
    echo  "h800 gpu: config"

    for bdf in $gpu_info; do
        echo "h800 mask gpu ce and set ct value"
        setpci -s $bdf ecap_aer+0x14.w=ffff >/dev/null 2>&1
        setpci -s $bdf cap_exp+0x28.w=6:f >/dev/null 2>&1
    done
fi

# L20 or L40
gpu_info=$(lspci -d 10de: -Dnn | grep -E "26ba|26b5" | awk '{print $1}')
if [ -n "$gpu_info" ];then
    echo  "L20/L40 gpu: config"

    for bdf in $gpu_info; do
        echo "L20/L40 fatal error config"
    done
fi

is_gpu_driver_installed
if [ $? -eq 0 ];then
    echo "gpu driver not installed. exit"
    exit 0
fi

command -v nvidia-smi >/dev/null 2>&1 && nvidia_smi_pm_on || { echo "no nvidia-smi command"; } 

gpu_info=$(lspci -d 10de:2324)
if [ -n "$gpu_info" ];then
    echo  "h800 gpu: nvlink check"
    # check fabric-manamger service is OK
    if [ "`which systemctl &> /dev/null;echo $?`" == 0 ] && [ "`systemctl is-enabled nvidia-fabricmanager &> /dev/null;echo $?`" == 0 ]; then
        if [ "`systemctl status nvidia-fabricmanager &> /dev/null;echo $?`" == 0 ]; then
            command -v nvidia-smi >/dev/null 2>&1 && nvlink_h800_check
        fi
    fi
fi
