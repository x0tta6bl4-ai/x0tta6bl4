// SPDX-License-Identifier: Apache-2.0
// Performance Monitor eBPF Program for x0tta6bl4
// Monitors CPU, memory, and system performance at kernel level

#include <linux/sched.h>
#include <linux/ptrace.h>
#include <uapi/linux/limits.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>

// Maximum number of processes to track
#define MAX_PROCESSES 1024
#define MAX_CPUS 128

// Process metrics structure
struct process_metrics {
    __u32 pid;
    __u32 ppid;
    char comm[16];
    __u64 cpu_time_ns;
    __u64 context_switches;
    __u64 syscalls;
    __u64 memory_allocations;
    __u64 io_operations;
    __u64 last_update_ns;
};

// Performance event structure
struct perf_event {
    __u32 pid;
    __u32 cpu_id;
    __u64 timestamp_ns;
    __u32 event_type;  // 1=cpu, 2=memory, 3=io, 4=ctx_switch
    __u64 value;
};

// Process metrics map (PID -> metrics)
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, MAX_PROCESSES);
    __type(key, __u32);
    __type(value, struct process_metrics);
} process_map SEC(".maps");

// Per-CPU performance events
struct {
    __uint(type, BPF_MAP_TYPE_PERF_EVENT_ARRAY);
    __uint(max_entries, MAX_CPUS);
    __type(key, __u32);
    __type(value, struct perf_event);
} perf_events SEC(".maps");

// System-wide metrics
struct system_metrics {
    __u64 total_context_switches;
    __u64 total_syscalls;
    __u64 total_memory_allocs;
    __u64 total_io_ops;
    __u64 cpu_cycles;
    __u64 cpu_instructions;
    __u64 cache_references;
    __u64 cache_misses;
};

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct system_metrics);
} system_metrics_map SEC(".maps");

// Helper function to get current timestamp
static __always_inline __u64 get_timestamp(void) {
    return bpf_ktime_get_ns();
}

// Helper function to update process metrics
static __always_inline void update_process_metrics(__u32 pid, __u32 event_type, __u64 value) {
    struct process_metrics *metrics = bpf_map_lookup_elem(&process_map, &pid);
    
    if (metrics) {
        __sync_fetch_and_add(&metrics->cpu_time_ns, value);
        __sync_fetch_and_add(&metrics->context_switches, 1);
        __sync_fetch_and_add(&metrics->syscalls, 1);
        metrics->last_update_ns = get_timestamp();
    }
}

// Tracepoint: sched_switch - Context switch monitoring
SEC("tp/sched/sched_switch")
int trace_sched_switch(struct trace_event_raw_sched_switch *ctx) {
    __u32 prev_pid = ctx->prev_pid;
    __u32 next_pid = ctx->next_pid;
    
    // Update previous process metrics
    struct process_metrics *prev_metrics = bpf_map_lookup_elem(&process_map, &prev_pid);
    if (prev_metrics) {
        __sync_fetch_and_add(&prev_metrics->context_switches, 1);
    }
    
    // Update system-wide metrics
    struct system_metrics *sys_metrics = bpf_map_lookup_elem(&system_metrics_map, &(__u32){0});
    if (sys_metrics) {
        __sync_fetch_and_add(&sys_metrics->total_context_switches, 1);
    }
    
    // Send perf event
    struct perf_event event = {
        .pid = prev_pid,
        .cpu_id = bpf_get_smp_processor_id(),
        .timestamp_ns = get_timestamp(),
        .event_type = 4,  // context switch
        .value = 1
    };
    
    bpf_perf_event_output(ctx, &perf_events, bpf_get_smp_processor_id(), 
                        sizeof(event), &event);
    
    return 0;
}

// Tracepoint: sys_enter - System call monitoring
SEC("tp/syscalls/sys_enter_execve")
int trace_sys_enter_execve(struct trace_event_raw_sys_enter *ctx) {
    __u32 pid = bpf_get_current_pid_tgid();
    
    // Update process metrics
    struct process_metrics *metrics = bpf_map_lookup_elem(&process_map, &pid);
    if (metrics) {
        __sync_fetch_and_add(&metrics->syscalls, 1);
        metrics->last_update_ns = get_timestamp();
    }
    
    // Update system-wide metrics
    struct system_metrics *sys_metrics = bpf_map_lookup_elem(&system_metrics_map, &(__u32){0});
    if (sys_metrics) {
        __sync_fetch_and_add(&sys_metrics->total_syscalls, 1);
    }
    
    return 0;
}

// Kprobe: kmem_cache_alloc - Memory allocation monitoring
SEC("kprobe/kmem_cache_alloc")
int BPF_KPROBE(kmem_cache_alloc) {
    __u32 pid = bpf_get_current_pid_tgid();
    __u64 size = PT_REGS_PARM2(ctx);
    
    // Update process metrics
    struct process_metrics *metrics = bpf_map_lookup_elem(&process_map, &pid);
    if (metrics) {
        __sync_fetch_and_add(&metrics->memory_allocations, 1);
    }
    
    // Update system-wide metrics
    struct system_metrics *sys_metrics = bpf_map_lookup_elem(&system_metrics_map, &(__u32){0});
    if (sys_metrics) {
        __sync_fetch_and_add(&sys_metrics->total_memory_allocs, 1);
    }
    
    // Send perf event
    struct perf_event event = {
        .pid = pid,
        .cpu_id = bpf_get_smp_processor_id(),
        .timestamp_ns = get_timestamp(),
        .event_type = 2,  // memory allocation
        .value = size
    };
    
    bpf_perf_event_output(ctx, &perf_events, bpf_get_smp_processor_id(), 
                        sizeof(event), &event);
    
    return 0;
}

// Tracepoint: block_rq_insert - I/O operation monitoring
SEC("tp/block/block_rq_insert")
int trace_block_rq_insert(struct trace_event_raw_block_rq_insert *ctx) {
    __u32 pid = bpf_get_current_pid_tgid();
    
    // Update process metrics
    struct process_metrics *metrics = bpf_map_lookup_elem(&process_map, &pid);
    if (metrics) {
        __sync_fetch_and_add(&metrics->io_operations, 1);
    }
    
    // Update system-wide metrics
    struct system_metrics *sys_metrics = bpf_map_lookup_elem(&system_metrics_map, &(__u32){0});
    if (sys_metrics) {
        __sync_fetch_and_add(&sys_metrics->total_io_ops, 1);
    }
    
    // Send perf event
    struct perf_event event = {
        .pid = pid,
        .cpu_id = bpf_get_smp_processor_id(),
        .timestamp_ns = get_timestamp(),
        .event_type = 3,  // I/O operation
        .value = 1
    };
    
    bpf_perf_event_output(ctx, &perf_events, bpf_get_smp_processor_id(), 
                        sizeof(event), &event);
    
    return 0;
}

// Tracepoint: sched_process_exec - Process execution monitoring
SEC("tp/sched/sched_process_exec")
int trace_sched_process_exec(struct trace_event_raw_sched_process_exec *ctx) {
    __u32 pid = bpf_get_current_pid_tgid();
    char comm[16];
    
    // Get process name
    bpf_probe_read_kernel_str(comm, sizeof(comm), ctx->filename);
    
    // Initialize process metrics
    struct process_metrics metrics = {
        .pid = pid,
        .ppid = bpf_get_current_pid_tgid(),  // Will be updated by parent
        .cpu_time_ns = 0,
        .context_switches = 0,
        .syscalls = 0,
        .memory_allocations = 0,
        .io_operations = 0,
        .last_update_ns = get_timestamp()
    };
    
    bpf_get_current_comm(&metrics.comm, sizeof(metrics.comm));
    
    // Store in map
    bpf_map_update_elem(&process_map, &pid, &metrics, BPF_ANY);
    
    return 0;
}

// Tracepoint: sched_process_exit - Process exit monitoring
SEC("tp/sched/sched_process_exit")
int trace_sched_process_exit(struct trace_event_raw_sched_process_exit *ctx) {
    __u32 pid = bpf_get_current_pid_tgid();
    
    // Remove from process map
    bpf_map_delete_elem(&process_map, &pid);
    
    return 0;
}

// License string
char _license[] SEC("license") = "GPL";
