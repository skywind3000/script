#!/bin/bash
echo "--------------------------------------------"
date
mask=0
i=0
total_nic_queues=0

get_all_mask()
{
    local cpu_nums=$1
    if [ $cpu_nums -gt 32 ]; then
        mask_tail=""
        mask_low32="ffffffff"
        idx=$((cpu_nums/32))
        cpu_reset=$((cpu_nums-idx*32))

        if [ $cpu_reset -eq 0 ]; then
            mask=$mask_low32
            for((i=2;i<=idx;i++))
            do
                mask="$mask,$mask_low32"
            done
        else
            for ((i=1;i<=idx;i++))
            do
                mask_tail="$mask_tail,$mask_low32"
            done
            mask_head_num=$((2**cpu_reset-1))
            mask=`printf "%x%s" $mask_head_num $mask_tail`
        fi
    else
        mask_num=$((2**cpu_nums-1))
        mask=`printf "%x" $mask_num`
    fi

    if [ $cpu_nums -ge 32 ]; then
        echo ${mask%?}0
    else
        echo $mask
    fi
}

get_lag_mask()
{
    local cpu_nums=$1
    local cpu_quen=$2
    if [ $cpu_nums -gt 32 ]; then
        mask_tail=""
        if [ "$cpu_quen" = "0" ]; then    
            mask_low32="ffffffff" 
        else
            mask_low32="00000000"
        fi
        idx=$((cpu_nums/32))
        cpu_reset=$((cpu_nums-idx*32))

        if [ $cpu_reset -eq 0 ]; then
            mask=$mask_low32
            for((i=2;i<=idx;i++))
            do
                if [ $i -gt $((idx/2)) ]; then
                    if [ "$cpu_quen" = "0" ]; then    
                        mask_low32="00000000" 
                    else
                        mask_low32="ffffffff"
                    fi
                fi
                mask="$mask,$mask_low32"
            done
        else
            for ((i=1;i<=idx;i++))
            do
                mask_tail="$mask_tail,$mask_low32"
            done
            mask_head_num=$((2**cpu_reset-1))
            mask=`printf "%x%s" $mask_head_num $mask_tail`
        fi
    else
        mask_num=$((2**cpu_nums-1))
        mask=`printf "%x" $mask_num`
    fi

    if [ $cpu_nums -ge 32 ]; then
        echo ${mask%?}0
    else
        echo $mask
    fi
}

set_rps_lag()
{
    echo "Enter set_rps_lag"
    if ! command -v ethtool &> /dev/null; then
        source /etc/profile
    fi

    ethtool=`which ethtool`

    cpu_nums=`cat /proc/cpuinfo |grep processor |wc -l`
    if [ $cpu_nums -eq 0 ] ;then
        exit 0
    fi


    mask=`get_lag_mask $cpu_nums 1`
    echo "cpu number:$cpu_nums  mask:0x$mask"

    ethSet=`ls -d /sys/class/net/eth*`

    for entry in $ethSet
    do
        eth=`basename $entry`
        nic_queues=`ls -l /sys/class/net/$eth/queues/ |grep rx- |wc -l`
        if (($nic_queues==0)) ;then
            continue
        fi

        cat /proc/interrupts  | grep "LiquidIO.*rxtx" &>/dev/null
        if [ $? -ne 0 ]; then # not smartnic
            #multi queue don't set rps
            max_combined=`$ethtool -l $eth 2>/dev/null | grep -i "combined" | head -n 1 | awk '{print $2}'`
            #if ethtool -l $eth goes wrong.
            [[ ! "$max_combined" =~ ^[0-9]+$ ]] && max_combined=1
            if [ ${max_combined} -ge ${cpu_nums} ]; then
                echo "$eth has equally nic queue as cpu, don't set rps for it..."
                continue
            fi
        else
            echo "$eth is smartnic, set rps for it..."
        fi

        echo "eth:$eth  queues:$nic_queues"
        total_nic_queues=$(( $total_nic_queues+$nic_queues ))
        i=0
        while (($i < $nic_queues))  
        do
		if [ $i -ge $((nic_queues/2)) ]; then
			mask=`get_lag_mask $cpu_nums 0`
		fi

            echo "echo $mask > /sys/class/net/$eth/queues/rx-$i/rps_cpus"
            echo $mask > /sys/class/net/$eth/queues/rx-$i/rps_cpus
            if [ $cpu_nums -ge 32 ]; then
                echo 0 > /sys/class/net/$eth/queues/rx-$i/rps_flow_cnt
            else
                echo 4096 > /sys/class/net/$eth/queues/rx-$i/rps_flow_cnt
            fi
            i=$(( $i+1 )) 
        done
    done

    flow_entries=$((total_nic_queues * 4096))
    echo "total_nic_queues:$total_nic_queues  flow_entries:$flow_entries"
    echo $flow_entries > /proc/sys/net/core/rps_sock_flow_entries 
}

set_rps_default()
{
    echo "Enter set_rps_default"
    if ! command -v ethtool &> /dev/null; then
        source /etc/profile
    fi

    ethtool=`which ethtool`

    cpu_nums=`cat /proc/cpuinfo |grep processor |wc -l`
    if [ $cpu_nums -eq 0 ] ;then
        exit 0
    fi


    mask=`get_all_mask $cpu_nums`
    echo "cpu number:$cpu_nums  mask:0x$mask"

    ethSet=`ls -d /sys/class/net/eth*`

    for entry in $ethSet
    do
        eth=`basename $entry`
        nic_queues=`ls -l /sys/class/net/$eth/queues/ |grep rx- |wc -l`
        if (($nic_queues==0)) ;then
            continue
        fi

        cat /proc/interrupts  | grep "LiquidIO.*rxtx" &>/dev/null
        if [ $? -ne 0 ]; then # not smartnic
            #multi queue don't set rps
            max_combined=`$ethtool -l $eth 2>/dev/null | grep -i "combined" | head -n 1 | awk '{print $2}'`
            #if ethtool -l $eth goes wrong.
            [[ ! "$max_combined" =~ ^[0-9]+$ ]] && max_combined=1
            if [ ${max_combined} -ge ${cpu_nums} ]; then
                echo "$eth has equally nic queue as cpu, don't set rps for it..."
                continue
            fi
        else
            echo "$eth is smartnic, set rps for it..."
        fi

        echo "eth:$eth  queues:$nic_queues"
        total_nic_queues=$(( $total_nic_queues+$nic_queues ))
        i=0
        while (($i < $nic_queues))  
        do
            echo "echo $mask > /sys/class/net/$eth/queues/rx-$i/rps_cpus"
            echo $mask > /sys/class/net/$eth/queues/rx-$i/rps_cpus
            if [ $cpu_nums -ge 32 ]; then
                echo 0 > /sys/class/net/$eth/queues/rx-$i/rps_flow_cnt
            else
                echo 4096 > /sys/class/net/$eth/queues/rx-$i/rps_flow_cnt
            fi
            i=$(( $i+1 )) 
        done
    done

    flow_entries=$((total_nic_queues * 4096))
    echo "total_nic_queues:$total_nic_queues  flow_entries:$flow_entries"
    echo $flow_entries > /proc/sys/net/core/rps_sock_flow_entries 
}

set_rps_default_numa_sense()
{
    echo "Enter set_rps_default_numa_sense"
    if ! command -v ethtool &> /dev/null; then
        source /etc/profile
    fi

    ethtool=`which ethtool`
    cpu_nums=`cat /proc/cpuinfo |grep processor |wc -l`
    if [ $cpu_nums -eq 0 ] ;then
        exit 0
    fi


    ethSet=`ls -d /sys/class/net/eth*`
    for entry in $ethSet
    do
        eth=`basename $entry`
        nic_queues=`ls -l /sys/class/net/$eth/queues/ |grep rx- |wc -l`
        if (($nic_queues==0)) ;then
            continue
        fi

        cat /proc/interrupts  | grep "LiquidIO.*rxtx" &>/dev/null
        if [ $? -ne 0 ]; then # not smartnic
            #multi queue don't set rps
            max_combined=`$ethtool -l $eth 2>/dev/null | grep -i "combined" | head -n 1 | awk '{print $2}'`
            #if ethtool -l $eth goes wrong.
            [[ ! "$max_combined" =~ ^[0-9]+$ ]] && max_combined=1
            if [ ${max_combined} -ge ${cpu_nums} ]; then
                echo "$eth has equally nic queue as cpu, don't set rps for it..."
                continue
            fi
        else
            echo "$eth is smartnic, set rps for it..."
        fi

        local dev_numa=`udevadm info -a numa -p $entry|grep numa_node|uniq|grep -Po "\d+"|tail -n 1`
        local mask=`cat /sys/devices/system/node/node$dev_numa/cpumap`
        echo "eth:$eth  queues:$nic_queues dev_numa:$dev_numa mask:$mask"
        total_nic_queues=$(( $total_nic_queues+$nic_queues ))
        i=0
        while (($i < $nic_queues))
        do
            echo "echo $mask > /sys/class/net/$eth/queues/rx-$i/rps_cpus"
            echo $mask > /sys/class/net/$eth/queues/rx-$i/rps_cpus
            echo 4096 > /sys/class/net/$eth/queues/rx-$i/rps_flow_cnt
            i=$(( $i+1 ))
        done
    done

    flow_entries=$((total_nic_queues * 4096))
    echo "total_nic_queues:$total_nic_queues  flow_entries:$flow_entries"
    echo $flow_entries > /proc/sys/net/core/rps_sock_flow_entries
}

cloudinit_softpass_last_numa_id=0
set_rps_default_cloudinit_softpass_numa()
{
    echo "Enter set_rps_default_cloudinit_softpass_numa"
    if ! command -v ethtool &> /dev/null; then
        source /etc/profile
    fi

    ethtool=`which ethtool`
    cpu_nums=`cat /proc/cpuinfo |grep processor |wc -l`
    if [ $cpu_nums -eq 0 ] ;then
        exit 0
    fi


    ethSet=`ls -d /sys/class/net/eth*`
    for entry in $ethSet
    do
        eth=`basename $entry`
        nic_queues=`ls -l /sys/class/net/$eth/queues/ |grep rx- |wc -l`
        if (($nic_queues==0)) ;then
            continue
        fi

        cat /proc/interrupts  | grep "LiquidIO.*rxtx" &>/dev/null
        if [ $? -ne 0 ]; then # not smartnic
            #multi queue don't set rps
            max_combined=`$ethtool -l $eth 2>/dev/null | grep -i "combined" | head -n 1 | awk '{print $2}'`
            #if ethtool -l $eth goes wrong.
            [[ ! "$max_combined" =~ ^[0-9]+$ ]] && max_combined=1
            if [ ${max_combined} -ge ${cpu_nums} ]; then
                echo "$eth has equally nic queue as cpu, don't set rps for it..."
                continue
            fi
        else
            echo "$eth is smartnic, set rps for it..."
        fi

        local dev_numa=$cloudinit_softpass_last_numa_id
        local numanr=`ls /sys/devices/system/node/ |grep node|wc -l`
        cloudinit_softpass_last_numa_id=$(((cloudinit_softpass_last_numa_id + 1) % numanr))
        local mask=`cat /sys/devices/system/node/node$dev_numa/cpumap`
        echo "eth:$eth  queues:$nic_queues dev_numa:$dev_numa mask:$mask"
        total_nic_queues=$(( $total_nic_queues+$nic_queues ))
        i=0
        while (($i < $nic_queues))
        do
            echo "echo $mask > /sys/class/net/$eth/queues/rx-$i/rps_cpus"
            echo $mask > /sys/class/net/$eth/queues/rx-$i/rps_cpus
            echo 4096 > /sys/class/net/$eth/queues/rx-$i/rps_flow_cnt
            i=$(( $i+1 ))
        done
    done

    flow_entries=$((total_nic_queues * 4096))
    echo "total_nic_queues:$total_nic_queues  flow_entries:$flow_entries"
    echo $flow_entries > /proc/sys/net/core/rps_sock_flow_entries
}

# return 0: yes, I'm a kvm vm
# return 1: no, I'm not
is_kvm_vm()
{
    local ret1
    local ret2

    # For ARM, ARM device not modelname
    archtype=`lscpu  | grep Architecture | awk '{print $2}'`
    if [ $archtype == "aarch64" ];then
        sys_vendor=`cat /sys/class/dmi/id/sys_vendor`
        chassis_vendor=`cat /sys/class/dmi/id/chassis_vendor`

        if [[ $sys_vendor == "Tencent Cloud" ]] || [[ $chassis_vendor == "QEMU" ]];then
            return 0
        else
            return 1
        fi
    fi

    # Quirk for 2080ti:
    #    We added a kvm:off parameter in qemu command line.
    #    This parameter hidden all kvm related featrues in vm,
    #    such as cpu tag and kvm clock source.
    #
    #    We passthough 2080ti function 0(vga) to vm only,
    #    So if there is 2080ti vga without function 1(audio),
    #    We know it is in vm enviroment.
    local vga=$(lspci -d 10de:1e04)
    local audio=$(lspci -d 10de:10f7)

    if [ "$vga" != '' ] && [ "$audio" == '' ]; then
        return 0
    fi

    # For ARM CVM. Cpu model name would be masked.
    local modelname=$(cat /proc/cpuinfo |grep "model name"|awk -F':' '{print $2}'|uniq|head -n 1)
    local modelname="${modelname#"${modelname%%[![:space:]]*}"}"
    [ -z "$modelname" ] && return 0
    [ "$modelname" == "Virtual" ] && return 0

    lscpu 2>/dev/null | grep -i kvm | grep -i Hypervisor >/dev/null 2>&1
    ret1=$?

    cat /sys/devices/system/clocksource/clocksource0/available_clocksource 2>/dev/null  | grep -i kvm >/dev/null 2>&1
    ret2=$?

    if [ "$ret1" == "0" -o "$ret2" == "0" ];then
        return 0
    else
        return 1
    fi
}

# qcloud_init.conf with nic_numa = 1/0 tag
CLOUDINIT_SOFTPASS_NUMA=-1
CLOUDINIT_SOFTPASS_LAG=-1
is_VM_cloudinit_softpass_numa()
{
    local default_numa_file=/usr/local/qcloud/qcloud_init.ini

    grep -q nic_numa $default_numa_file
    NIC_NUMA_FLAG=$?
    grep -q lag $default_numa_file
    LAG_FLAG=$?

    if [ "$NIC_NUMA_FLAG" != "0" ] && [ "$LAG_FLAG" != "0" ]; then
        return
    elif [ "$NIC_NUMA_FLAG" != "0" ] && [ "$LAG_FLAG" == "0" ]; then
        CLOUDINIT_SOFTPASS_LAG=$(awk -F '=' '{if ($1 ~ /lag/) print $2}' $default_numa_file|grep -Po "\d+")
        echo "Founding cloudinit config with lag.. loading $CLOUDINIT_SOFTPASS_LAG"
    else
        CLOUDINIT_SOFTPASS_NUMA=$(awk -F '=' '{if ($1 ~ /nic_numa/) print $2}' $default_numa_file|grep -Po "\d+")
        echo "Founding cloudinit config with nic_numa.. loading $CLOUDINIT_SOFTPASS_NUMA"
    fi
}

# return 0: yes sa3 and cpu >= 128
# return 1: not
is_milan_icx_genoa_spr_cross_node()
{
    local cpu_model_list=("7K83" "9K24" "9K84" "8372C" "8374B" "8374C" "8476C")
    local model_name=$(grep -i "model name" /proc/cpuinfo|uniq)
    local found=0
    for cpu_model in ${cpu_model_list[*]};do
        echo $model_name|grep -q "$cpu_model" >/dev/null 2>&1
        [ $? == 0 ] && found=1 && break
    done
    [ $found != 1 ] && return 1

    local numa_cnt=`ls -d /sys/devices/system/node/node*|wc -l`
    [ $numa_cnt -gt 1 ] && return 0 || return 1
}

get_cvm_instance_type()
{
    #支持后续扩展
    local instance_list=("$1")
    local instype="http://metadata.tencentyun.com/latest/meta-data/instance/instance-type"
    local found=0

    #if url unaccessible
    curlinfo=`curl --connect-timeout 10 $instype -s`
    [ $? -ne 0 ] && { echo "$instype unaccessible, basic donot get instance type"; return 1; }

    ret=`echo "$curlinfo" | grep 404`
    [ -n "$ret" ] && { echo "$instype curl 404, basic donot get instance type"; return 1; }


    for ins_type in ${instance_list[*]};do
        echo $curlinfo|grep -q "$ins_type" >/dev/null 2>&1
        [ $? == 0 ] && found=1 && echo "found $ins_type device" && break
    done
    [ $found != 1 ] && return 1

    return 0
}

disable_rps()
{
    ethSet=`ls -d /sys/class/net/eth*`
    for entry in $ethSet
    do
        eth=`basename $entry`
        nic_queues=`ls -l /sys/class/net/$eth/queues/ |grep rx- |wc -l`
        if (($nic_queues==0)) ;then
            continue
        fi

        echo "start to disable rps for queues:$nic_queues"
        i=0
        while (($i < $nic_queues))
        do
            echo 0 > /sys/class/net/$eth/queues/rx-$i/rps_cpus
            i=$(( $i+1 ))
        done
    done
}

new_type_set_rps()
{
    ethSet=`ls -d /sys/class/net/eth*`

    for entry in $ethSet
    do
        eth=`basename $entry`
        nic_queues=`ls -l /sys/class/net/$eth/queues/ |grep rx- |wc -l`
        if (($nic_queues==0)) ;then
            continue
        fi

        echo "start to set rps for queues:$nic_queues"
        i=0
        while (($i < $nic_queues))
        do
            if [ $i -lt 24 ]; then
                echo "00000000,00000000,00000000,0000ffff,ffffffff,ffffffff,fffffff0" > /sys/class/net/$eth/queues/rx-$i/rps_cpus
            else
                echo "ffffffff,ffffffff,ffffffff,ffff0000,00000000,00000000,00000000" > /sys/class/net/$eth/queues/rx-$i/rps_cpus
            fi
            i=$(( $i+1 ))
        done
    done
}

function set_rps()
{
    is_kvm_vm
    if [ $? == 0 ];then
        # CVM guest

        #tapd: https://tapd.woa.com/20422209/prong/stories/view/1020422209115250770
        get_cvm_instance_type "PTX1.56XLARGE928"
        [ $? == 0 ] && disable_rps && return

        get_cvm_instance_type "S8.56XLARGE1024"
        [ $? == 0 ] && new_type_set_rps && return

        is_VM_cloudinit_softpass_numa
        if [ $CLOUDINIT_SOFTPASS_NUMA == -1 ] && [ $CLOUDINIT_SOFTPASS_LAG == -1 ];then
        	set_rps_default
	    elif [ $CLOUDINIT_SOFTPASS_LAG != -1 ]; then
            set_rps_lag
        else
            cloudinit_softpass_last_numa_id=$CLOUDINIT_SOFTPASS_NUMA
            set_rps_default_cloudinit_softpass_numa
        fi
    else
        is_milan_icx_genoa_spr_cross_node
        # MILAN/ICX/GENOA/SPR and more than one numa
        [ $? == 0 ] && set_rps_default_numa_sense && return

        # other baremetal host
        set_rps_default
    fi
}

set_rps
