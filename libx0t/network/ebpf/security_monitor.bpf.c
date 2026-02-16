// SPDX-License-Identifier: Apache-2.0
// Security Monitor eBPF Program for x0tta6bl4
// Monitors security events and potential threats at kernel level

#include <linux/socket.h>
#include <linux/in.h>
#include <linux/in6.h>
#include <linux/fs.h>
#include <linux/binfmts.h>
#include <linux/cred.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>

// Maximum number of connections to track
#define MAX_CONNECTIONS 1024
#define MAX_CPUS 128
#define MAX_SECURITY_EVENTS 1024

// Connection key structure
struct connection_key {
    __u32 saddr;  // Source IP (hashed)
    __u32 daddr;  // Destination IP (hashed)
    __u16 sport;  // Source port
    __u16 dport;  // Destination port
    __u8 protocol; // TCP/UDP
};

// Connection info structure
struct connection_info {
    __u64 timestamp_ns;
    __u32 pid;
    __u32 uid;
    __u8 state;  // 0=connecting, 1=established, 2=closing
    __u64 bytes_sent;
    __u64 bytes_received;
    __u32 failed_attempts;
};

// Security event structure
struct security_event {
    __u32 event_type;  // 1=connection, 2=auth_fail, 3=file_access, 4=exec, 5=priv_esc
    __u32 pid;
    __u32 uid;
    __u64 timestamp_ns;
    __u32 saddr_hash;
    __u32 daddr_hash;
    __u16 sport;
    __u16 dport;
    __u8 protocol;
    __u32 severity;  // 1=low, 2=medium, 3=high, 4=critical
    char comm[16];
    char filename[64];
};

// Connection tracking map
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, MAX_CONNECTIONS);
    __type(key, struct connection_key);
    __type(value, struct connection_info);
} connections SEC(".maps");

// Security events map
struct {
    __uint(type, BPF_MAP_TYPE_PERF_EVENT_ARRAY);
    __uint(max_entries, MAX_CPUS);
    __type(key, __u32);
    __type(value, struct security_event);
} security_events SEC(".maps");

// Failed authentication tracking
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 256);
    __type(key, __u32);  // IP hash
    __type(value, __u64);  // Failed attempts count
} failed_auth_map SEC(".maps");

// Suspicious file access tracking
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 256);
    __type(key, __u32);  // PID
    __type(value, __u64);  // Suspicious access count
} suspicious_file_map SEC(".maps");

// System-wide security metrics
struct system_security_metrics {
    __u64 total_connection_attempts;
    __u64 failed_auth_attempts;
    __u64 suspicious_file_access;
    __u64 executable_executions;
    __u64 privilege_escalation_attempts;
    __u64 unusual_syscall_patterns;
    __u64 active_connections;
};

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct system_security_metrics);
} system_security_map SEC(".maps");

// Helper function to hash IP address
static __always_inline __u32 hash_ip(__be32 ip) {
    return ip;
}

// Helper function to get current timestamp
static __always_inline __u64 get_timestamp(void) {
    return bpf_ktime_get_ns();
}

// Helper function to create connection key
static __always_inline void create_connection_key(
    struct connection_key *key,
    __be32 saddr,
    __be32 daddr,
    __be16 sport,
    __be16 dport,
    __u8 protocol
) {
    key->saddr = hash_ip(saddr);
    key->daddr = hash_ip(daddr);
    key->sport = sport;
    key->dport = dport;
    key->protocol = protocol;
}

// Tracepoint: sys_enter_connect - Connection attempt monitoring
SEC("tp/syscalls/sys_enter_connect")
int trace_sys_enter_connect(struct trace_event_raw_sys_enter *ctx) {
    __u32 pid = bpf_get_current_pid_tgid();
    __u32 uid = bpf_get_current_uid_gid();
    
    // Get socket address
    struct sockaddr_in *addr = (struct sockaddr_in *)PT_REGS_PARM2(ctx);
    if (!addr)
        return 0;
    
    __be32 daddr = addr->sin_addr.s_addr;
    __be16 dport = addr->sin_port;
    
    // Update system-wide metrics
    struct system_security_metrics *sys_metrics = bpf_map_lookup_elem(&system_security_map, &(__u32){0});
    if (sys_metrics) {
        __sync_fetch_and_add(&sys_metrics->total_connection_attempts, 1);
    }
    
    // Create connection key
    struct connection_key key;
    create_connection_key(&key, 0, daddr, 0, dport, IPPROTO_TCP);
    
    // Update connection info
    struct connection_info info = {
        .timestamp_ns = get_timestamp(),
        .pid = pid,
        .uid = uid,
        .state = 0,  // connecting
        .bytes_sent = 0,
        .bytes_received = 0,
        .failed_attempts = 0
    };
    
    bpf_map_update_elem(&connections, &key, &info, BPF_ANY);
    
    // Send security event
    struct security_event event = {
        .event_type = 1,  // connection
        .pid = pid,
        .uid = uid,
        .timestamp_ns = get_timestamp(),
        .daddr_hash = hash_ip(daddr),
        .dport = dport,
        .protocol = IPPROTO_TCP,
        .severity = 1  // low
    };
    
    bpf_get_current_comm(&event.comm, sizeof(event.comm));
    
    bpf_perf_event_output(ctx, &security_events, bpf_get_smp_processor_id(), 
                        sizeof(event), &event);
    
    return 0;
}

// Tracepoint: sys_enter_accept - Accept connection monitoring
SEC("tp/syscalls/sys_enter_accept")
int trace_sys_enter_accept(struct trace_event_raw_sys_enter *ctx) {
    __u32 pid = bpf_get_current_pid_tgid();
    __u32 uid = bpf_get_current_uid_gid();
    
    // Update system-wide metrics
    struct system_security_metrics *sys_metrics = bpf_map_lookup_elem(&system_security_map, &(__u32){0});
    if (sys_metrics) {
        __sync_fetch_and_add(&sys_metrics->active_connections, 1);
    }
    
    // Send security event
    struct security_event event = {
        .event_type = 1,  // connection
        .pid = pid,
        .uid = uid,
        .timestamp_ns = get_timestamp(),
        .severity = 1  // low
    };
    
    bpf_get_current_comm(&event.comm, sizeof(event.comm));
    
    bpf_perf_event_output(ctx, &security_events, bpf_get_smp_processor_id(), 
                        sizeof(event), &event);
    
    return 0;
}

// Tracepoint: security_inode_permission - File access monitoring
SEC("tp/security/inode_permission")
int trace_security_inode_permission(struct trace_event_raw_security_inode_permission *ctx) {
    __u32 pid = bpf_get_current_pid_tgid();
    __u32 uid = bpf_get_current_uid_gid();
    
    // Get filename
    char filename[64];
    bpf_probe_read_kernel_str(filename, sizeof(filename), ctx->inode);
    
    // Check for suspicious file access patterns
    // (e.g., accessing /etc/passwd, /etc/shadow, etc.)
    if (filename[0] == '/' && filename[1] == 'e' && filename[2] == 't' && filename[3] == 'c') {
        // Update suspicious file access tracking
        __u64 *count = bpf_map_lookup_elem(&suspicious_file_map, &pid);
        if (count) {
            __sync_fetch_and_add(count, 1);
        } else {
            __u64 new_count = 1;
            bpf_map_update_elem(&suspicious_file_map, &pid, &new_count, BPF_ANY);
        }
        
        // Update system-wide metrics
        struct system_security_metrics *sys_metrics = bpf_map_lookup_elem(&system_security_map, &(__u32){0});
        if (sys_metrics) {
            __sync_fetch_and_add(&sys_metrics->suspicious_file_access, 1);
        }
        
        // Send security event
        struct security_event event = {
            .event_type = 3,  // file access
            .pid = pid,
            .uid = uid,
            .timestamp_ns = get_timestamp(),
            .severity = 3  // high
        };
        
        bpf_get_current_comm(&event.comm, sizeof(event.comm));
        __builtin_memcpy(event.filename, filename, sizeof(event.filename));
        
        bpf_perf_event_output(ctx, &security_events, bpf_get_smp_processor_id(), 
                            sizeof(event), &event);
    }
    
    return 0;
}

// Tracepoint: sched_process_exec - Executable execution monitoring
SEC("tp/sched/sched_process_exec")
int trace_sched_process_exec(struct trace_event_raw_sched_process_exec *ctx) {
    __u32 pid = bpf_get_current_pid_tgid();
    __u32 uid = bpf_get_current_uid_gid();
    
    // Get executable name
    char filename[64];
    bpf_probe_read_kernel_str(filename, sizeof(filename), ctx->filename);
    
    // Update system-wide metrics
    struct system_security_metrics *sys_metrics = bpf_map_lookup_elem(&system_security_map, &(__u32){0});
    if (sys_metrics) {
        __sync_fetch_and_add(&sys_metrics->executable_executions, 1);
    }
    
    // Send security event
    struct security_event event = {
        .event_type = 4,  // exec
        .pid = pid,
        .uid = uid,
        .timestamp_ns = get_timestamp(),
        .severity = 2  // medium
    };
    
    bpf_get_current_comm(&event.comm, sizeof(event.comm));
    __builtin_memcpy(event.filename, filename, sizeof(event.filename));
    
    bpf_perf_event_output(ctx, &security_events, bpf_get_smp_processor_id(), 
                        sizeof(event), &event);
    
    return 0;
}

// Tracepoint: security_prepare_creds - Privilege escalation monitoring
SEC("tp/security/prepare_creds")
int trace_security_prepare_creds(struct trace_event_raw_security_prepare_creds *ctx) {
    __u32 pid = bpf_get_current_pid_tgid();
    __u32 old_uid = bpf_get_current_uid_gid();
    __u32 new_uid = 0;
    
    // Get new UID
    bpf_probe_read_kernel(&new_uid, sizeof(new_uid), &ctx->new->uid.val);
    
    // Check for privilege escalation
    if (new_uid < old_uid) {
        // Update system-wide metrics
        struct system_security_metrics *sys_metrics = bpf_map_lookup_elem(&system_security_map, &(__u32){0});
        if (sys_metrics) {
            __sync_fetch_and_add(&sys_metrics->privilege_escalation_attempts, 1);
        }
        
        // Send security event
        struct security_event event = {
            .event_type = 5,  // privilege escalation
            .pid = pid,
            .uid = new_uid,
            .timestamp_ns = get_timestamp(),
            .severity = 4  // critical
        };
        
        bpf_get_current_comm(&event.comm, sizeof(event.comm));
        
        bpf_perf_event_output(ctx, &security_events, bpf_get_smp_processor_id(), 
                            sizeof(event), &event);
    }
    
    return 0;
}

// Kprobe: tcp_connect - Failed connection monitoring
SEC("kprobe/tcp_connect")
int BPF_KPROBE(tcp_connect) {
    // This will be called on connection failures
    // Update failed authentication tracking
    __u32 ip_hash = 0;
    __u64 *count = bpf_map_lookup_elem(&failed_auth_map, &ip_hash);
    if (count) {
        __sync_fetch_and_add(count, 1);
    } else {
        __u64 new_count = 1;
        bpf_map_update_elem(&failed_auth_map, &ip_hash, &new_count, BPF_ANY);
    }
    
    // Update system-wide metrics
    struct system_security_metrics *sys_metrics = bpf_map_lookup_elem(&system_security_map, &(__u32){0});
    if (sys_metrics) {
        __sync_fetch_and_add(&sys_metrics->failed_auth_attempts, 1);
    }
    
    // Send security event
    struct security_event event = {
        .event_type = 2,  // auth fail
        .pid = bpf_get_current_pid_tgid(),
        .uid = bpf_get_current_uid_gid(),
        .timestamp_ns = get_timestamp(),
        .severity = 2  // medium
    };
    
    bpf_get_current_comm(&event.comm, sizeof(event.comm));
    
    bpf_perf_event_output(ctx, &security_events, bpf_get_smp_processor_id(), 
                        sizeof(event), &event);
    
    return 0;
}

// License string
char _license[] SEC("license") = "GPL";
