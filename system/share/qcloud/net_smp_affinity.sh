#!/bin/bash
##used to bind virtio-input interrupt to last cpu
export PATH=$PATH:/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin:/root/bin
dir=$(cd `dirname $0`;pwd)

echo "--------------------------------------------"
date

get_highest_mask()
{
    cpu_nums=$1
    if [ $cpu_nums -gt 32 ]; then
        mask_tail=""
        mask_low32="00000000"
        idx=$((cpu_nums/32))
        cpu_reset=$((cpu_nums-idx*32))

        if [ $cpu_reset -eq 0 ]; then
            mask="80000000"
            for((i=2;i<=idx;i++))
            do
                mask="$mask,$mask_low32"
            done
        else
            for ((i=1;i<=idx;i++))
            do
                mask_tail="$mask_tail,$mask_low32"
            done
            mask_head_num=$((1<<(cpu_reset-1)))
            mask=`printf "%x%s" $mask_head_num $mask_tail`
        fi

    else
        mask_num=$((1<<(cpu_nums-1)))
        mask=`printf "%x" $mask_num`
    fi
    echo $mask
}

get_smp_affinity_mask()
{
    local cpuNums=$1

    if [ $cpuNums -gt $gCpuCount ]; then
        cpuNums=$(((cpuNums - 1) % gCpuCount + 1))
    fi

    if [ $gReverse == 1 ];then
        cpuNums=$((gCpuCount + 1 - cpuNums))
    fi

    get_highest_mask $cpuNums
}

input_irq_bind()
{
    local netQueueCount=`cat /proc/interrupts  | grep -i ".*virtio.*input.*" | wc -l`
    local irqSet=`cat /proc/interrupts  | grep -i ".*virtio.*input.*" | awk -F ':' '{print $1}'`
    if [ $((gCpuCount-2*netQueueCount)) -lt 0 ]; then
        i=0
        for irq in $irqSet
        do
            cpunum=$((i%gCpuCount+1))
            mask=`get_smp_affinity_mask $cpunum`
            echo $mask > /proc/irq/$irq/smp_affinity
            echo "[input]bind irq $irq with mask 0x$mask affinity"
            ((i++))
        done
    else
        if [ $gCpuCount -ge 32 ]; then
            cpunum=$((gCpuCount-1))
            for irq in $irqSet
            do
                echo $cpunum > /proc/irq/$irq/smp_affinity_list
                echo "[input]bind irq $irq with mask 0x$(cat /proc/irq/$irq/smp_affinity) affinity"
                cpunum=$(((cpunum-2) % gCpuCount))
            done
        else
            cpunum=0
            for irq in $irqSet
            do
                echo $cpunum > /proc/irq/$irq/smp_affinity_list
                echo "[input]bind irq $irq with mask 0x$(cat /proc/irq/$irq/smp_affinity) affinity"
                cpunum=$(((cpunum+2) % gCpuCount))
            done
        fi
    fi
}

output_irq_bind()
{
    local netQueueCount=`cat /proc/interrupts  | grep -i ".*virtio.*input.*" | wc -l`
    local irqSet=`cat /proc/interrupts  | grep -i ".*virtio.*output.*" | awk -F ':' '{print $1}'`
    if [ $((gCpuCount-2*netQueueCount)) -lt 0 ]; then
        i=0
        for irq in $irqSet
        do
            cpunum=$((i%gCpuCount+1))
            mask=`get_smp_affinity_mask $cpunum`
            echo $mask > /proc/irq/$irq/smp_affinity
            echo "[output]bind irq $irq with mask 0x$mask affinity"
            ((i++))
        done
    else
        if [ $gCpuCount -ge 32 ]; then
            cpunum=$((gCpuCount-1))
            for irq in $irqSet
            do
                echo $cpunum > /proc/irq/$irq/smp_affinity_list
                echo "[output]bind irq $irq with mask 0x$(cat /proc/irq/$irq/smp_affinity) affinity"
                cpunum=$(((cpunum-2) % gCpuCount))
            done
        else
            cpunum=0
            for irq in $irqSet
            do
                echo $cpunum > /proc/irq/$irq/smp_affinity_list
                echo "[output]bind irq $irq with mask 0x$(cat /proc/irq/$irq/smp_affinity) affinity"
                cpunum=$(((cpunum+2) % gCpuCount))
            done
        fi
    fi
}

declare -A aff_nodeoffset
declare -A aff_nodecpu
init_numa_support()
{
    numa_support=0
    aff=0

    numanr=`ls /sys/devices/system/node/ |grep node|wc -l`
    [ $? != 0 ] && echo "numa not support" && return

    numacpunr=$((gCpuCount/numanr))

    for((i=0;i<numanr;i++));do
        aff_nodeoffset[$i]=0
        aff_nodecpu[$i]=`ls /sys/devices/system/node/node$i/|grep cpu|grep -Po "\d+"|sort -n`
        [ $? != 0 ] && echo "numa not support" && return
    done

    numa_support=1
    echo "numa supported numa($numanr) cpu per numa($numacpunr)"
}

get_next_affinity_origin()
{
    aff=$(((aff+2) % gCpuCount))
}

cloudinit_softpass_last_pci_addr=0
cloudinit_softpass_last_numa_id=0
get_irq_numa()
{
    local irq=$1
    if [ -f /proc/irq/$irq/node -a `cat /proc/irq/$irq/node` != -1 ];then
        cat /proc/irq/$irq/node
        return
    else
        local irq_numa=0
        # AS a result of FPGA & Virt Teams' discuss:
        # The first nic is on numa $CLOUDINIT_SOFTPASS_NUMA
        # The second nic is on next numa. And so on.
        for msi_irqs in `find /sys/devices/ -name "*msi_irqs"`;do
            if [ -f $msi_irqs/$irq ];then
                [ "$cloudinit_softpass_last_pci_addr" == 0 ] && cloudinit_softpass_last_pci_addr=$msi_irqs
                if [ "$msi_irqs" == "$cloudinit_softpass_last_pci_addr" ];then
                    if [ $CLOUDINIT_SOFTPASS_LAG != -1 ];then
                        if [ $irq -gt $irqQueueHalf ]; then
                            echo 1
                        else
                            echo 0
                        fi
                    else
                        echo $cloudinit_softpass_last_numa_id
                    fi 
                else
                    cloudinit_softpass_last_pci_addr=$msi_irqs
                    local numanr=`ls /sys/devices/system/node/ |grep node|wc -l`
                    cloudinit_softpass_last_numa_id=$(((cloudinit_softpass_last_numa_id + 1) % numanr))
                fi
            else
                continue
            fi
        done
        return
    fi
}

get_next_affinity()
{
    local irq=$1
    if [ $numa_support != 0 ];then
        [ ! -f /proc/irq/$irq/node ] && get_next_affinity_origin && return

        local irqnuma=$(get_irq_numa $irq)
        local irqnodeoffset=${aff_nodeoffset[${irqnuma}]}
        local forward=1
        [ $IS_VM == 0 ] && forward=2 # CVM always keep hyper-thread every 2 cores
        if [ $((irqnodeoffset+forward)) -ge $numacpunr ];then
            aff_nodeoffset[${irqnuma}]=0
        else
            aff_nodeoffset[${irqnuma}]=$((irqnodeoffset+forward))
        fi
        if [ $gReverse == 1 ];then
            irqnodeoffset=$((numacpunr-irqnodeoffset-forward))
        fi
        aff=`echo ${aff_nodecpu[${irqnuma}]}|awk -v iter=$((irqnodeoffset+1)) '{print $iter}'`
    else
        get_next_affinity_origin
    fi
}

input_irq_bind_numaopt()
{
    local netQueueCount=`cat /proc/interrupts  | grep -i ".*virtio.*input.*" | wc -l`
    local irqSet=`cat /proc/interrupts  | grep -i ".*virtio.*input.*" | awk -F ':' '{print $1}'`
    local irqQueueHead=`cat /proc/interrupts  | grep -i ".*virtio.*input.*" | awk -F ':' '{print $1}' | head -n 1`
    local irqQueueTail=`cat /proc/interrupts  | grep -i ".*virtio.*input.*" | awk -F ':' '{print $1}' | tail -n 1`
    irqQueueHalf=$(( (irqQueueTail + irqQueueHead) / 2))

    init_numa_support

    echo "shuishan host rss input config"
    for irq in $irqSet
    do
        get_next_affinity $irq
        echo $aff > /proc/irq/$irq/smp_affinity_list
        echo "[input]bind irq $irq with mask 0x$(cat /proc/irq/$irq/smp_affinity) affinity"
    done
}

output_irq_bind_numaopt()
{
    local netQueueCount=`cat /proc/interrupts  | grep -i ".*virtio.*output.*" | wc -l`
    local irqSet=`cat /proc/interrupts  | grep -i ".*virtio.*output.*" | awk -F ':' '{print $1}'`
    local irqQueueHead=`cat /proc/interrupts  | grep -i ".*virtio.*output.*" | awk -F ':' '{print $1}' | head -n 1`
    local irqQueueTail=`cat /proc/interrupts  | grep -i ".*virtio.*output.*" | awk -F ':' '{print $1}' | tail -n 1`
    irqQueueHalf=$(( (irqQueueTail + irqQueueHead) / 2))

    init_numa_support

    echo "shuishan host rss output config"
    for irq in $irqSet
    do
        get_next_affinity $irq
        echo $aff > /proc/irq/$irq/smp_affinity_list
        echo "[output]bind irq $irq with mask 0x$(cat /proc/irq/$irq/smp_affinity) affinity"
    done
}

ethConfig()
{
    ethSet=`ls -d /sys/class/net/eth*`
    if ! command -v ethtool &> /dev/null; then
        source /etc/profile
    fi

    ethtool=`which ethtool`

    for ethd in $ethSet
    do
        eth=`basename $ethd`
        pre_max=`$ethtool -l $eth 2>/dev/null | grep -i "combined" | head -n 1 | awk '{print $2}'`
        cur_max=`$ethtool -l $eth 2>/dev/null | grep -i "combined" | tail -n 1 | awk '{print $2}'`
        # if ethtool not work. we have to deal with this situation.
        [[ ! "$pre_max" =~ ^[0-9]+$ ]] || [[ ! "$cur_max" =~ ^[0-9]+$ ]] && continue

        if [ $pre_max -ne $cur_max ]; then
            $ethtool -L $eth combined $pre_max
            echo "Set [$eth] Current Combined to <$pre_max>"
        fi
    done
}

smartnic_bind()
{
    irqSet=`cat /proc/interrupts  | grep "LiquidIO.*rxtx" | awk -F ':' '{print $1}'`
    i=0
    for irq in $irqSet
    do
        cpunum=$((i%gCpuCount+1))
        mask=`get_smp_affinity_mask $cpunum`
        echo $mask > /proc/irq/$irq/smp_affinity
        echo "[smartnic]bind irq $irq with mask 0x$mask affinity"
        ((i++))
    done
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

# return 0: yes shuishan bm
# return 1: not shuishan
is_shuishan()
{
    virtionum=`cat /proc/interrupts  | grep -i ".*virtio.*input.*" | wc -l`
    if [ $virtionum == 0 ]; then
        return 1
    else
        return 0
    fi
}

set_vm_net_legacy_affinity()
{
    ps ax | grep -v grep | grep -q irqbalance && killall irqbalance 2>/dev/null
    cat /proc/interrupts  | grep "LiquidIO.*rxtx" &>/dev/null
    if [ $? -eq 0 ]; then #smartnic
        echo "SET VM RSS SMARTNIC"
        smartnic_bind
    else
        ethConfig
        local cpuarch=`lscpu|grep Architecture|awk '{print $2}'`
        if [ "$cpuarch" == "aarch64" -a\
             "$gCpuCount" == 120 -a\
             -f $dir/armvirt120c_set_irqaffinity.sh ];then #ARM64 120C spec#
            echo "SET VM RSS AARCH64 120C spec.."
            $dir/armvirt120c_set_irqaffinity.sh
            return 
        fi
        echo "SET VM RSS NORMAL"
        #X86 and ARM64 other#
        input_irq_bind
        output_irq_bind
    fi
}

set_eth_bm_net_affinity()
{
    if [ $gCpuCount -ge 32 ]; then
        aff=$((gCpuCount-1))
        for i in $(awk -F ":" '/eth0/{print $1}' /proc/interrupts)
        do
            echo $aff > /proc/irq/$i/smp_affinity_list
            echo "$aff > /proc/irq/$i/smp_affinity_list"
            aff=$((aff-1))
            [ $aff == 0 ] && aff=$((gCpuCount-1))
        done
    else
        aff=1
        for i in $(awk -F ":" '/eth0/{print $1}' /proc/interrupts)
        do
            echo $aff > /proc/irq/$i/smp_affinity
            echo "$aff > /proc/irq/$i/smp_affinity"
            aff=$(echo "ibase=16;obase=10;$aff*2"|bc)
        done
    fi
}

set_virtio_bm_net_affinity()
{
    # assume that bm cpu must larger than 32.
    gReverse=1
    input_irq_bind_numaopt
    output_irq_bind_numaopt
}

set_numaopt_vm_net_affinity()
{
    input_irq_bind_numaopt
    output_irq_bind_numaopt
}

set_bm_net_affinity()
{
    if [ $gCpuCount == 0 ];then
        echo cpunumber error
        return
    fi

    is_shuishan
    if [ $? -ne 0 ]; then
        ethConfig
        set_eth_bm_net_affinity
    else
        ethConfig
        set_virtio_bm_net_affinity
    fi
}

set_vm_net_affinity()
{
    if [ $CLOUDINIT_SOFTPASS_NUMA == -1 ] && [ $CLOUDINIT_SOFTPASS_LAG == -1 ];then
        set_vm_net_legacy_affinity
    elif [ $CLOUDINIT_SOFTPASS_LAG != -1 ]; then
        echo "Founding cloudinit config with lag.. loading $CLOUDINIT_SOFTPASS_LAG"
        set_numaopt_vm_net_affinity
    else
        cloudinit_softpass_last_numa_id=$CLOUDINIT_SOFTPASS_NUMA
        set_numaopt_vm_net_affinity
    fi
}

reverse_irq_for_nvme()
{
    lspci -nn | grep -q "Non-Volatile memory controller"
    [ $? == 0 ] && gReverse=1 || gReverse=0
}


# return 0: yes sa3 and cpu >= 128
# return 1: not
is_sa3_cross_node()
{
    milan=0
    cross_node=0
    is_milan=`cat /proc/cpuinfo | awk '{FS=":";if (NR==5) {print $2}}' | grep "AMD EPYC 7K83 64-Core Processor"`
    cpu_num=`cat /proc/cpuinfo | grep processor |wc -l`

    echo "is_milan:$is_milan cpu_num:$cpu_num"

    if [ -n "${is_milan}" ];then
        milan=1
    fi

    if [ $cpu_num -ge 128 ];then
        cross_node=1;
    fi


    if [ $milan -eq 1 -a $cross_node -eq 1 ];then
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

# 初始化数组来保存每个NUMA节点上最后一次映射的CPU
declare -a last_cpu_on_numa

handle_interrupts() 
{
    local interrupts=$1

    # 遍历所有的中断
    for irq in $interrupts
    do
        echo ${last_cpu_on_numa[$numa]} > /proc/irq/$irq/smp_affinity_list

        last_cpu_on_numa[$numa]=$((last_cpu_on_numa[$numa]+2))
        count=$((count+1))

        # 检查是否需要切换 NUMA 节点
        if (( count % (round_width / numa_nodes) == 0 ))
        then
        numa=$((numa + 1))

        # 如果超过了NUMA节点数，重置为0
        if (( numa >= numa_nodes ))
        then
            numa=0
        fi
        fi
    done
}


reset_smp_affinity()
{
    if [ $# -ne 1 ]; then
        echo "Usage: $0 <round_width>"
        exit 1
    fi

    # 队列映射的循环宽度，即DPDK worker数量
    round_width=$1

    # 获取CPU个数和NUMA节点数
    total_cpus=$(nproc)
    numa_nodes=$(numactl --hardware | awk '/available:/ {print $2}')
    cpus_per_numa=$((total_cpus / numa_nodes))

    cpu_id=0
    numa=0
    count=0

    # 获取所有的input中断并处理
    for (( i=0; i<numa_nodes; i++ ))
    do
        last_cpu_on_numa[$i]=$((i * cpus_per_numa))
    done
    input_interrupts=$(cat /proc/interrupts | grep "input" | awk -F':' '{print $1}')
    handle_interrupts "$input_interrupts"

    # 获取所有的output中断并处理
    for (( i=0; i<numa_nodes; i++ ))
    do
        last_cpu_on_numa[$i]=$((i * cpus_per_numa))
    done
    output_interrupts=$(cat /proc/interrupts | grep "output" | awk -F':' '{print $1}')
    handle_interrupts "$output_interrupts"
}

new_type_set_irq()
{
    ethSet=`ls -d /sys/class/net/eth*`
    base_core0=111
    base_core1=223
    for entry in $ethSet
    do
        eth=`basename $entry`
        eth_number=$(echo "$eth" | grep -o -E '[0-9]+' | head -1)
        nic_queues=`ls -l /sys/class/net/$eth/queues/ |grep rx- |wc -l`
        if (($nic_queues==0)) ;then
            continue
        fi
        echo "start to set irq for queues:$nic_queues"
        i=0
        while (($i < $nic_queues))
        do
            input_irq=`cat /proc/interrupts | grep -w virtio$eth_number-input.$i | cut -d : -f 1`
            input_irq=`echo $input_irq | sed -e 's/^[ ]*//g'`
            if [ $i -lt 24 ];then
                irq_core=`expr $base_core0 - $i`
            else
                irq_core=`expr $base_core1 - $i + 24`
            fi
            echo $irq_core > /proc/irq/$input_irq/smp_affinity_list
            echo "Bind virtio$eth_number queue$i rx irq $input_irq to cpu core$irq_core"
            sleep 0.1
            output_irq=`cat /proc/interrupts | grep -w virtio$eth_number-output.$i | cut -d : -f 1`
            output_irq=`echo $output_irq | sed -e 's/^[ ]*//g'`
            echo $irq_core > /proc/irq/$output_irq/smp_affinity_list
            echo "Bind virtio$eth_number queue$i tx irq $output_irq to cpu core$irq_core"
            sleep 0.1
            i=$(( $i+1 ))
        done
    done
}


set_net_affinity()
{
    get_cvm_instance_type "S8.56XLARGE1024"
    [ $? == 0 ] && new_type_set_irq  && return

    get_cvm_instance_type "PTX1.56XLARGE928"
    [ $? == 0 ] && reset_smp_affinity 16 && return 

    sa3_cross_node=0
    is_sa3_cross_node

    if [ $? -eq 0 ]; then
        sa3_cross_node=1
    fi

    if [ $gCpuCount -ge 32 -a $sa3_cross_node -ne 1 ]; then
        gReverse=1
    else
        reverse_irq_for_nvme
    fi
    is_kvm_vm
    IS_VM=$? 
    if [ $IS_VM -ne 0 ];then
        set_bm_net_affinity
    else
        set_vm_net_affinity
    fi

}

gCpuCount=`cat /proc/cpuinfo |grep processor |wc -l`
if [ $gCpuCount -eq 0 ] ;then
    echo "machine cpu count get error!"
    exit 0
elif [ $gCpuCount -eq 1 ]; then
    echo "machine only have one cpu, needn't set affinity for net interrupt"
    exit 0
fi

is_VM_cloudinit_softpass_numa
set_net_affinity
