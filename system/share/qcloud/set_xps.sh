#!/bin/bash
cd $(dirname $0)
g_n_dir='/sys/class/net'
g_dir='/usr/local/qcloud'
g_log='/tmp/tlinux_xps.log'
g_mod='/sys/module/virtio_net/parameters/tl2_priv_feature'


g_size=0
function log() {
    local _size=0
    # only call du one time, just assuming this script do
    # not output so many log by one-time running 
    if (( g_size == 0 ))
    then
        _size=$(du -sk "$g_log" 2>/dev/null|cut -f  1)
        g_size=$_size
        #max log size 10MB
        if (( _size > 10240)) 
        then
            mv -f $g_log ${g_log}.1
        fi
    fi
    echo "$(date '+%F_%T') $*"
    echo "$(date '+%F_%T') $*" >> $g_log
}

function check() {
    # if we fix in kernel in the feature, we will
    # add a file to tell we fixed, this script will
    # bypassed. by the wy g_mod is not exit for now #^_^
    local _fixed=$(cat "$g_mod" 2>/dev/null)
    if [[ -n "${_fixed}" ]]
    then
        local _xps_fixed_bit='0x1'
        fixed=$(( _fixed | _xps_fixed_bit ))
        if [[ "$fixed" != '0' ]]
        then
            return 1
        fi
    fi

    #only fix tlinux
    if [[ ! -e '/etc/tlinux-release' ]]
    then
        log "info: /etc/tlinux-release not exist"
        return 1
    fi

    #only fix tkernel3/4
    local os_ver=$(cat '/proc/sys/kernel/osrelease') 
    log "os_ver: $os_ver"

    local k_big_ver=$(echo $os_ver | cut -d '.' -f 1) 
    if (( k_big_ver != 3 && k_big_ver != 4 ))
    then
        return 1
    fi

    local n_need='info: no need set xps'
    # only fix tkernel 3.10.107  
    if (( k_big_ver == 3 ))
    then
        local small_ver=$(echo "$os_ver"|\
              awk -F '-' '/3.10.107.*tlinux2_kvm_guest/{print $NF}'|\
              sed -nr 's/^0*//gp')
        if [[ -z "$small_ver" ]]
        then
            return 1
        fi
        if echo "$small_ver" | grep -qsE '[[:alpha:]]' 
        then
            return 1
        fi
        if (( small_ver < 51 ))
        then
            return 1
        fi
        return 0
    fi
    # and all tkernel 4.19 babababa 4.XXXX 
    return 0
}

#get all virtio_net driver netif
function get_veth_list() {
    local _eths=''
    for _path in ${g_n_dir}/*/device/driver
    do
        local _d_path=$(realpath $_path 2>/dev/null)
        if [[ -z "$_d_path" ]]
        then
            continue
        fi

        local _d_name=$(basename $_d_path 2>/dev/null)
        if [[ "$_d_name" != 'virtio_net' ]]
        then
            continue
        fi

        _eth=$(echo "$_path" | awk -F '/' '{print $(NF-2)}')
        _eths="$_eth $_eths"
    done
    echo "$_eths"
}

#error: return null
#error: return cpumask u32list from list
function u32list() {
    local max_cpu=0
    local cpulist="${1}"
    local ii=0

    if [[ -z "${cpulist}" ]]
    then
        return
    fi

    #find max cpu in cpulist
    local _cpu
    for _cpu in ${cpulist}
    do
        if ((max_cpu < _cpu))
        then
            max_cpu=$_cpu
        fi
    done

    #echo max_cpu=$max_cpu
    #init a bitmap
    for ((ii=0; ii <= max_cpu; ii++))
    do
        map[$ii]=0
    done

    # set bit map according to cpulist
    for _cpu in $cpulist
    do
        map[$_cpu]=1
    done

    #format a u32list
    local seg=0
    local mask=''
    local ii=0
    for ((ii=0; ii <= max_cpu; ii++))
    do
        if (( ii % 4 == 0  && ii != 0))
        then
            seg=$(printf '%0x' $seg)
            mask=${seg}${mask} 
            seg=0
        fi

        if (( ii % 32 == 0 && ii != 0))
        then
            mask=",${mask}"
        fi

        cur=${map[$ii]}
        if ((cur == 1 ))
        then
            val=$((1<<(ii%4)))
            seg=$((seg+val))
        fi
    done

    if [[ "$seg" != '0' ]]
    then
        seg=$(printf '%0x' $seg)
        mask=${seg}${mask}
    fi
    echo "${mask}"
}

function set_eth_xps() {
    local tx_qs=$(ls "${g_n_dir}/${1}/queues" 2>/dev/null|\
                  grep -E '^tx-[[:digit:]]+$'|wc -l)
    if (( tx_qs <= 1 ))
    then
        log "info: eth: $1 qnum: $tx_qs"
        return 0
    fi

    local cpus=$(nproc --all 2>/dev/null)
    if (( cpus <= 1 ))
    then
        log "info: cpus: $cpus"
        return 0
    fi
    #tx_qs=5
    #cpus=100

    #here is what take from tkernel-5.4
    local stride=$((cpus / tx_qs))
    if (( stride == 0 ))
    then
        stride=1
    fi

    local stragglers=0
    if (( cpus > tx_qs ))
    then
        stragglers=$((cpus % tx_qs)) 
    fi

    local _i=0
    local _curcpu=0
    for (( _i=0; _i < tx_qs; _i++ ))
    do
        local _list=''
        local gsize=$stride
        if (( _i < stragglers ))
        then
            gsize=$((gsize + 1 ))
        fi
        local _j=0
        for ((_j=0; _j < gsize; _j++ ))
        do
            _list="$_curcpu $_list"
            ((_curcpu++))
        done

        local mask=$(u32list "$_list")
        log "$mask -> ${g_n_dir}/${1}/queues/tx-${_i}/xps_cpus"
        echo "$mask" > ${g_n_dir}/${1}/queues/tx-${_i}/xps_cpus
    done 
}

function set_eth_xps_numa_sensed()
{
    echo "set_eth_xps_numa_sensed..."
    local tx_qs=$(ls "${g_n_dir}/${1}/queues" 2>/dev/null|\
                  grep -E '^tx-[[:digit:]]+$'|wc -l)
    if (( tx_qs <= 1 ))
    then
        log "info: eth: $1 qnum: $tx_qs"
        return 0
    fi

    local cpus=$(nproc --all 2>/dev/null)
    if (( cpus <= 1 ))
    then
        log "info: cpus: $cpus"
        return 0
    fi

    local numa_cnt=`ls -d /sys/devices/system/node/node*|wc -l`
    local random_tag=`tr -dc 'a-zA-Z0-9' </dev/urandom | head -c 10`
    local cpu_numa_map=/tmp/set_xps_tmpfile.$random_tag
    > $cpu_numa_map
    for ((i = 0; i < numa_cnt; i++)); do
        local numa_cpus=`ls -d /sys/devices/system/node/node$i/cpu*|grep -Po "cpu\d+"|grep -Po "\d+"|sort -n`
        echo $numa_cpus >> $cpu_numa_map
    done

    local curr_idx=1
    local txq_aff_per_numa=$((cpus/numa_cnt/tx_qs))
    local left=$(((cpus/numa_cnt) % tx_qs))
    for ((i = 0; i < tx_qs; i++ )); do
        local aff_pnuma=$txq_aff_per_numa
        [ $((i + left)) -ge $tx_qs ] && aff_pnuma=$((aff_pnuma+1))
        cpulist=`awk -v idx="$curr_idx" -v aff_pnuma="$aff_pnuma" '{for(i=idx;i<idx+aff_pnuma;i++){printf "%d ",$i}}' $cpu_numa_map`
        local mask=$(u32list "$cpulist")
        log "$mask -> ${g_n_dir}/${1}/queues/tx-${i}/xps_cpus"
        echo "$mask" > ${g_n_dir}/${1}/queues/tx-${i}/xps_cpus
        curr_idx=$((curr_idx+aff_pnuma))
    done

    rm -f $cpu_numa_map
}

function set_eth_xps_lag_sensed()
{
    echo "set_eth_xps_lag_sensed..."
    local tx_qs=$(ls "${g_n_dir}/${1}/queues" 2>/dev/null|\
                  grep -E '^tx-[[:digit:]]+$'|wc -l)
    if (( tx_qs <= 1 ))
    then
        log "info: eth: $1 qnum: $tx_qs"
        return 0
    fi

    local cpus=$(nproc --all 2>/dev/null)
    if (( cpus <= 1 ))
    then
        log "info: cpus: $cpus"
        return 0
    fi

    local cpu_nums=`cat /proc/cpuinfo |grep processor |wc -l`
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

    for ((i = 0; i < tx_qs; i++ )); do
        log "$mask -> ${g_n_dir}/${1}/queues/tx-${i}/xps_cpus"
        echo "$mask" > ${g_n_dir}/${1}/queues/tx-${i}/xps_cpus
        curr_idx=$((curr_idx+aff_pnuma))
    done
}

function set_eth_xps_alternative_queue()
{
    echo "set_eth_xps_alternative_queue..."
    local tx_qs=$(ls "${g_n_dir}/${1}/queues" 2>/dev/null|\
                  grep -E '^tx-[[:digit:]]+$'|wc -l)
    if (( tx_qs <= 1 ))
    then
        log "info: eth: $1 qnum: $tx_qs"
        return 0
    fi

    local cpus=$(nproc --all 2>/dev/null)
    if (( cpus <= 1 ))
    then
        log "info: cpus: $cpus"
        return 0
    fi
    #tx_qs=5
    #cpus=100

    #here is what take from tkernel-5.4
    local stride=$((cpus / tx_qs))
    if (( stride == 0 ))
    then
        stride=1
    fi

    local stragglers=0
    if (( cpus > tx_qs ))
    then
        stragglers=$((cpus % tx_qs))
    fi

    local _i=0
    local _curcpu=0
    for (( _i=0; _i < tx_qs; _i++ ))
    do
        local _list=''
        local gsize=$stride
        if (( _i < stragglers ))
        then
            gsize=$((gsize + 1 ))
        fi
        local _j=0
        _curcpu=$_i
        for ((_j=0; _j < gsize; _j++ ))
        do
            _list="$_curcpu $_list"
            _curcpu=$((_curcpu + tx_qs))
        done

        local mask=$(u32list "$_list")
        log "$mask -> ${g_n_dir}/${1}/queues/tx-${_i}/xps_cpus"
        echo "$mask" > ${g_n_dir}/${1}/queues/tx-${_i}/xps_cpus
    done

}

function set_xps_tlinux() {
    local _eths=$(get_veth_list)
    for _eth in $_eths
    do
        set_eth_xps $_eth
    done
}

function set_xps_generic()
{
    local _eths=$(get_veth_list)
    local _callback=$1
    for _eth in $_eths$
    do
        $_callback $_eth
    done

}

# return 0 is milan baremetal()
function is_milan_baremetal() {
    # Only AMD baremetal has svm feature.
    grep -q svm /proc/cpuinfo
    [ $? != 0 ] && return 1

    # check number check
    local cpunr=`lscpu|grep -i "^CPU(s)"|awk '{print $2}'`
    [ $cpunr != 256 ] && return 1

    lscpu | grep -q "AMD EPYC 7K83 64-Core Processor"
    [ $? != 0 ] && return 1

    return 0
}

# return 0 means OK. return 1 means not found.
function is_target_cpu_baremetal()
{
    grep -Pq "svm|vmx" /proc/cpuinfo
    [ $? != 0 ] && return 1

    local model_name=$(grep -i "model name" /proc/cpuinfo|uniq)
    local found=0
    for model in "$@";do
        echo $model_name|grep -q "$model"
        [ $? == 0 ] && found=1 && echo "found $model_name of $model" && break
    done

    [ $found == 0 ] && return 1 || return 0
}

function is_target_cpu_cvm_numad()
{
    grep -Pq "svm|vmx" /proc/cpuinfo
    [ $? == 0 ] && return 1
    grep -Pq "CVM|KVM" /sys/class/dmi/id/product_name
    [ $? != 0 ] && return 1

    local numa_count=$(ls /sys/bus/node/devices/| wc -l)
    [ $numa_count -le 1 ] && return 1

    local model_name=$(grep -i "model name" /proc/cpuinfo|uniq)
    local found=0
    for model in "$@";do
        echo $model_name|grep -q "$model"
        [ $? == 0 ] && found=1 && echo "found $model_name of $model" && break
    done

    [ $found == 0 ] && return 1 || return 0
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

new_type_set_xps()
{
    ethSet=`ls -d /sys/class/net/eth*`

    for entry in $ethSet
    do
        eth=`basename $entry`
        nic_queues=`ls -l /sys/class/net/$eth/queues/ |grep rx- |wc -l`
        if (($nic_queues==0)) ;then
            continue
        fi

        echo "start to set xps for queues:$nic_queues"
        i=0
        while (($i < $nic_queues))
        do
             echo "ffffffff,ffffffff,ffffffff,ffffffff,ffffffff,ffffffff,ffffffff" > /sys/class/net/$eth/queues/tx-$i/xps_cpus
             i=$(( $i+1 ))
        done
    done
}

##<==main
#udev may export a  env var:
#ACTION=='add' when add a nic
#ACTION=='remove' when remove a nic
#we need not to set xps when remove a nic
if [[ ${ACTION} == 'remove' ]]
then
    exit 0
fi

if ! check 
then # Non-tlinux
    get_cvm_instance_type "S8.56XLARGE1024"
    [ $? == 0 ] && new_type_set_xps

    # set xps for milan baremetal.
    is_target_cpu_baremetal "7K83"
    if [ $? == 0 ]; then  
        grep -q lag /usr/local/qcloud/qcloud_init.ini
        if [ $? == 0 ]; then
            set_xps_generic set_eth_xps_lag_sensed
        else
            set_xps_generic set_eth_xps_alternative_queue
        fi
    fi

    grep -q lag /usr/local/qcloud/qcloud_init.ini
    if [ $? == 0 ]; then
        set_xps_generic set_eth_xps_lag_sensed
    else
        # set xps for icx baremetal.
        #is_target_cpu_baremetal "8372C" "8374B" "8374C"
        #[ $? == 0 ] && set_xps_generic set_eth_xps_numa_sensed
        is_target_cpu_cvm_numad "7K83" "8374B" "8374C" "8372C"
        if [ $? == 0 ]; then
            set_xps_generic set_eth_xps_numa_sensed
        fi
    fi

    exit 0
else
    set_xps_tlinux
    exit 0
fi
