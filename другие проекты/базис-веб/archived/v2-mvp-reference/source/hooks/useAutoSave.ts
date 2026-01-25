
import { useState, useEffect, useCallback, useRef } from 'react';
import { debounce } from 'lodash';

export interface AutoSaveConfig {
  enabled: boolean;
  intervalMs: number;
  storageKey: string;
}

export interface AutoSaveResult<T> {
  saveStatus: 'saved' | 'saving' | 'unsaved';
  lastSaved: Date | null;
  recoveryData: { data: T; timestamp: number } | null;
  clearRecovery: () => void;
  forceSave: () => void;
}

export function useAutoSave<T>(data: T, config: AutoSaveConfig): AutoSaveResult<T> {
  const { enabled, intervalMs, storageKey } = config;
  
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | 'unsaved'>('saved');
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [recoveryData, setRecoveryData] = useState<{ data: T; timestamp: number } | null>(null);
  
  const dataRef = useRef(data);
  const isMounted = useRef(false);

  // Keep ref updated to avoid stale closures in debounce/interval
  useEffect(() => {
    dataRef.current = data;
    if (isMounted.current) {
        setSaveStatus('unsaved');
    }
  }, [data]);

  // Core Save Logic
  const performSave = useCallback(() => {
    if (!enabled) return;
    
    try {
      setSaveStatus('saving');
      const payload = {
        timestamp: Date.now(),
        data: dataRef.current
      };
      localStorage.setItem(storageKey, JSON.stringify(payload));
      
      // Artificial delay for UX visibility if needed, but synchronous LS is fast
      setLastSaved(new Date());
      setSaveStatus('saved');
    } catch (e) {
      console.error("Auto-save failed", e);
      setSaveStatus('unsaved');
    }
  }, [enabled, storageKey]);

  // Debounced Save (Change-based)
  // We use useMemo to create a stable debounced function
  const debouncedSave = useRef(
    debounce(() => {
      performSave();
    }, 2000)
  ).current;

  // Trigger Debounced Save on data change
  useEffect(() => {
    if (!isMounted.current) {
        isMounted.current = true;
        return;
    }
    if (enabled) {
        debouncedSave();
    }
    return () => {
        debouncedSave.cancel();
    };
  }, [data, enabled, debouncedSave]);

  // Interval Save (Time-based)
  useEffect(() => {
    if (!enabled) return;

    const intervalId = setInterval(() => {
        // Only save if dirty? Or always?
        // Requirement says "Auto-save every 30 seconds". 
        // We'll perform a save to ensure timestamp is fresh even if no changes,
        // or we could check status. Let's force save to be safe against crashes.
        performSave();
    }, intervalMs);

    return () => clearInterval(intervalId);
  }, [enabled, intervalMs, performSave]);

  // Initial Recovery Check
  useEffect(() => {
    try {
      const savedItem = localStorage.getItem(storageKey);
      if (savedItem) {
        const parsed = JSON.parse(savedItem);
        // Basic validation
        if (parsed && parsed.timestamp && parsed.data) {
            setRecoveryData(parsed);
        }
      }
    } catch (e) {
      console.error("Failed to parse recovery data", e);
    }
  }, [storageKey]);

  const clearRecovery = useCallback(() => {
    localStorage.removeItem(storageKey);
    setRecoveryData(null);
  }, [storageKey]);

  return {
    saveStatus,
    lastSaved,
    recoveryData,
    clearRecovery,
    forceSave: performSave
  };
}
