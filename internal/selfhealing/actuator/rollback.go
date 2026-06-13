package actuator

import (
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// SnapshotManager handles creating and restoring system state snapshots.
type SnapshotManager struct {
	BackupDir string
	mappings  map[string]string // snapshotID -> originalPath
	mu        sync.RWMutex
}

func NewSnapshotManager() *SnapshotManager {
	dir := filepath.Join(os.TempDir(), "x0tta-healing-backups")
	if err := os.MkdirAll(dir, 0700); err != nil {
		log.Printf("[Rollback] Warning: failed to create backup dir: %v\n", err)
	}
	return &SnapshotManager{
		BackupDir: dir,
		mappings:  make(map[string]string),
	}
}

// CreateSnapshot creates a backup of the current state (e.g., config files).
// Returns a snapshot ID.
func (sm *SnapshotManager) CreateSnapshot(target string) string {
	// If target is not a file path, we just record a virtual snapshot (e.g. for service status)
	if !filepath.IsAbs(target) {
		snapshotID := fmt.Sprintf("virtual-%s-%d", filepath.Base(target), time.Now().UnixNano())
		log.Printf("[Rollback] Created virtual snapshot: %s\n", snapshotID)
		return snapshotID
	}

	snapshotID := fmt.Sprintf("snap-%s-%d", filepath.Base(target), time.Now().UnixNano())
	backupPath := filepath.Join(sm.BackupDir, snapshotID)

	if err := sm.copyFile(target, backupPath); err != nil {
		log.Printf("[Rollback] Error creating snapshot for %s: %v\n", target, err)
		return ""
	}

	sm.mu.Lock()
	sm.mappings[snapshotID] = target
	sm.mu.Unlock()

	log.Printf("[Rollback] Created file snapshot: %s (backup at %s)\n", snapshotID, backupPath)
	return snapshotID
}

// Rollback restores the state from a snapshot.
func (sm *SnapshotManager) Rollback(snapshotID string) {
	if snapshotID == "" {
		return
	}

	// Virtual snapshots don't need file restoration
	if len(snapshotID) > 8 && snapshotID[:8] == "virtual-" {
		log.Printf("[Rollback] Skipping virtual snapshot: %s\n", snapshotID)
		return
	}

	sm.mu.RLock()
	originalPath, exists := sm.mappings[snapshotID]
	sm.mu.RUnlock()

	if !exists {
		log.Printf("[Rollback] Warning: no mapping found for snapshot %s\n", snapshotID)
		return
	}

	backupPath := filepath.Join(sm.BackupDir, snapshotID)
	log.Printf("[Rollback] Restoring %s from %s\n", originalPath, backupPath)

	if err := sm.copyFile(backupPath, originalPath); err != nil {
		log.Printf("[Rollback] FAILED to restore %s: %v\n", originalPath, err)
	}
}

// Cleanup removes a snapshot if the action was successful.
func (sm *SnapshotManager) Cleanup(snapshotID string) {
	if snapshotID == "" || (len(snapshotID) > 8 && snapshotID[:8] == "virtual-") {
		return
	}
	log.Printf("[Rollback] Cleaning up snapshot: %s\n", snapshotID)

	sm.mu.Lock()
	delete(sm.mappings, snapshotID)
	sm.mu.Unlock()

	backupPath := filepath.Join(sm.BackupDir, snapshotID)
	os.Remove(backupPath)
}

func (sm *SnapshotManager) copyFile(src, dst string) error {
	sourceFile, err := os.Open(src)
	if err != nil {
		return err
	}
	defer sourceFile.Close()

	destFile, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer destFile.Close()

	_, err = io.Copy(destFile, sourceFile)
	return err
}
