
import { ProjectSnapshot } from "../types";

const DB_NAME = 'BazisProDB';
const STORE_NAME = 'projects';
const DB_VERSION = 1;

/**
 * Database error with context information
 */
class DatabaseError extends Error {
    constructor(
        message: string,
        public operation: string,
        public context?: Record<string, any>
    ) {
        super(`[${operation}] ${message}`);
        this.name = 'DatabaseError';
    }
}

class StorageService {
    private db: IDBDatabase | null = null;

    async init(): Promise<void> {
        if (this.db) return;

        return new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, DB_VERSION);

            request.onerror = () => {
                const error = request.error;
                reject(new DatabaseError(
                    error?.message || 'Failed to open database',
                    'init',
                    { code: error?.code }
                ));
            };
            
            request.onsuccess = () => {
                this.db = request.result;
                resolve();
            };

            request.onupgradeneeded = (event) => {
                try {
                    const db = (event.target as IDBOpenDBRequest).result;
                    if (!db.objectStoreNames.contains(STORE_NAME)) {
                        const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
                        store.createIndex('timestamp', 'timestamp', { unique: false });
                    }
                } catch (error) {
                    reject(new DatabaseError(
                        'Failed to create object store',
                        'init.upgrade',
                        { error: error instanceof Error ? error.message : String(error) }
                    ));
                }
            };
        });
    }

    async saveProject(project: ProjectSnapshot): Promise<string> {
        await this.init();
        return new Promise((resolve, reject) => {
            if (!this.db) {
                return reject(new DatabaseError('Database not initialized', 'saveProject'));
            }
            
            try {
                const transaction = this.db.transaction([STORE_NAME], 'readwrite');
                const store = transaction.objectStore(STORE_NAME);
                const request = store.put(project);

                request.onsuccess = () => resolve(project.id);
                request.onerror = () => {
                    reject(new DatabaseError(
                        'Failed to save project',
                        'saveProject',
                        { projectId: project.id, error: request.error?.message }
                    ));
                };
                
                transaction.onerror = () => {
                    reject(new DatabaseError(
                        'Transaction failed',
                        'saveProject',
                        { projectId: project.id, error: transaction.error?.message }
                    ));
                };
            } catch (error) {
                reject(new DatabaseError(
                    'Unexpected error during save',
                    'saveProject',
                    { projectId: project.id, error: error instanceof Error ? error.message : String(error) }
                ));
            }
        });
    }

    async getAllProjects(): Promise<ProjectSnapshot[]> {
        await this.init();
        return new Promise((resolve, reject) => {
            if (!this.db) {
                return reject(new DatabaseError('Database not initialized', 'getAllProjects'));
            }

            try {
                const transaction = this.db.transaction([STORE_NAME], 'readonly');
                const store = transaction.objectStore(STORE_NAME);
                const request = store.getAll();

                request.onsuccess = () => {
                    try {
                        const res = request.result as ProjectSnapshot[];
                        res.sort((a, b) => b.timestamp - a.timestamp);
                        resolve(res);
                    } catch (error) {
                        reject(new DatabaseError(
                            'Failed to process results',
                            'getAllProjects.process',
                            { error: error instanceof Error ? error.message : String(error) }
                        ));
                    }
                };
                
                request.onerror = () => {
                    reject(new DatabaseError(
                        'Failed to retrieve projects',
                        'getAllProjects',
                        { error: request.error?.message }
                    ));
                };
                
                transaction.onerror = () => {
                    reject(new DatabaseError(
                        'Transaction failed',
                        'getAllProjects',
                        { error: transaction.error?.message }
                    ));
                };
            } catch (error) {
                reject(new DatabaseError(
                    'Unexpected error during retrieval',
                    'getAllProjects',
                    { error: error instanceof Error ? error.message : String(error) }
                ));
            }
        });
    }

    async getProject(id: string): Promise<ProjectSnapshot | undefined> {
        await this.init();
        return new Promise((resolve, reject) => {
            if (!this.db) {
                return reject(new DatabaseError('Database not initialized', 'getProject'));
            }

            try {
                const transaction = this.db.transaction([STORE_NAME], 'readonly');
                const store = transaction.objectStore(STORE_NAME);
                const request = store.get(id);

                request.onsuccess = () => resolve(request.result);
                request.onerror = () => {
                    reject(new DatabaseError(
                        'Failed to retrieve project',
                        'getProject',
                        { projectId: id, error: request.error?.message }
                    ));
                };
                
                transaction.onerror = () => {
                    reject(new DatabaseError(
                        'Transaction failed',
                        'getProject',
                        { projectId: id, error: transaction.error?.message }
                    ));
                };
            } catch (error) {
                reject(new DatabaseError(
                    'Unexpected error during retrieval',
                    'getProject',
                    { projectId: id, error: error instanceof Error ? error.message : String(error) }
                ));
            }
        });
    }

    async deleteProject(id: string): Promise<void> {
        await this.init();
        return new Promise((resolve, reject) => {
            if (!this.db) {
                return reject(new DatabaseError('Database not initialized', 'deleteProject'));
            }

            try {
                const transaction = this.db.transaction([STORE_NAME], 'readwrite');
                const store = transaction.objectStore(STORE_NAME);
                const request = store.delete(id);

                request.onsuccess = () => resolve();
                request.onerror = () => {
                    reject(new DatabaseError(
                        'Failed to delete project',
                        'deleteProject',
                        { projectId: id, error: request.error?.message }
                    ));
                };
                
                transaction.onerror = () => {
                    reject(new DatabaseError(
                        'Transaction failed',
                        'deleteProject',
                        { projectId: id, error: transaction.error?.message }
                    ));
                };
            } catch (error) {
                reject(new DatabaseError(
                    'Unexpected error during deletion',
                    'deleteProject',
                    { projectId: id, error: error instanceof Error ? error.message : String(error) }
                ));
            }
        });
    }
}

export const storageService = new StorageService();

