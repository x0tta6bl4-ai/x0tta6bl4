// src/network/ebpf/programs/tc_classifier.c

#include <linux/bpf.h>
#include <linux/pkt_cls.h>
#include <bpf/bpf_helpers.h>

SEC("classifier")
int tc_classify_prog(struct __sk_buff *skb)
{
    return TC_ACT_OK;
}

char LICENSE[] SEC("license") = "GPL";