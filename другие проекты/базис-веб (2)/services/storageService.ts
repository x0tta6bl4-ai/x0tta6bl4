
import { ProjectSnapshot } from "../types";

const DB_NAME = 'BazisProDB';
const STORE_NAME = 'projects';
const DB_VERSION = 1;

class StorageService {
    private db: IDBDatabase | null = null;

    async init(): Promise<void> {
        if (this.db) return;

        return new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, DB_VERSION);

            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                this.db = request.result;
                resolve();
            };

            request.onupgradeneeded = (event) => {
                const db = (event.target as IDBOpenDBRequest).result;
                if (!db.objectStoreNames.contains(STORE_NAME)) {
                    const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
                    store.createIndex('timestamp', 'timestamp', { unique: false });
                }
            };
        });
    }

    async saveProject(project: ProjectSnapshot): Promise<string> {
        await this.init();
        return new Promise((resolve, reject) => {
            if (!this.db) return reject('Database not initialized');
            
            const transaction = this.db.transaction([STORE_NAME], 'readwrite');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.put(project);

            request.onsuccess = () => resolve(project.id);
            request.onerror = () => reject(request.error);
        });
    }

    async getAllProjects(): Promise<ProjectSnapshot[]> {
        await this.init();
        return new Promise((resolve, reject) => {
            if (!this.db) return reject('Database not initialized');

            const transaction = this.db.transaction([STORE_NAME], 'readonly');
            const store = transaction.objectStore(STORE_NAME);
            const index = store.index('timestamp');
            // Get all, but sort logic usually happens in memory for small datasets or via cursor
            // Here we just get all
            const request = store.getAll();

            request.onsuccess = () => {
                // Sort by timestamp desc
                const res = request.result as ProjectSnapshot[];
                res.sort((a, b) => b.timestamp - a.timestamp);
                resolve(res);
            };
            request.onerror = () => reject(request.error);
        });
    }

    async getProject(id: string): Promise<ProjectSnapshot | undefined> {
        await this.init();
        return new Promise((resolve, reject) => {
            if (!this.db) return reject('Database not initialized');

            const transaction = this.db.transaction([STORE_NAME], 'readonly');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.get(id);

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async deleteProject(id: string): Promise<void> {
        await this.init();
        return new Promise((resolve, reject) => {
            if (!this.db) return reject('Database not initialized');

            const transaction = this.db.transaction([STORE_NAME], 'readwrite');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.delete(id);

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }
}

export const storageService = new StorageService();
