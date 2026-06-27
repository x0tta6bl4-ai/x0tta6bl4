/*
 * x0tta6bl4 Mobile SDK Core — C API
 * =================================
 *
 * This header defines the bridge between native mobile apps (Swift/Kotlin)
 * and the x0tta6bl4 self-healing mesh core.
 */

#ifndef X0T_MOBILE_H
#define X0T_MOBILE_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// --- Initialization & Lifecycle ---

/**
 * Initializes the x0t core on the mobile device.
 * @param mesh_id The target mesh identifier.
 * @param enrollment_token Signed token from Control Plane.
 * @return 0 on success, negative error code otherwise.
 */
int x0t_init(const char* mesh_id, const char* enrollment_token);

/**
 * Starts the mesh background service.
 * Mobile SDK uses aggressive power saving (sleeping neighbors when idle).
 */
int x0t_start();

/**
 * Stops all mesh activities and releases resources.
 */
void x0t_stop();

// --- Connectivity & Status ---

typedef struct {
    bool connected;
    bool pqc_active;
    int neighbor_count;
    float battery_impact_score; // 0.0 - 1.0
    char last_error[256];
} x0t_status_t;

x0t_status_t x0t_get_status();

// --- Security ---

/**
 * Performs a hardware-backed attestation (if TPM/Enclave available).
 * Required for Enterprise meshes.
 */
int x0t_perform_attestation(uint8_t* out_nonce, uint32_t* out_len);

#ifdef __cplusplus
}
#endif

#endif // X0T_MOBILE_H
