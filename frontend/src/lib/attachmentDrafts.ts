import { offlineEnabled } from './offlineConsent';

export interface AttachmentDraft { id: string; session: string; name: string; type: string; size: number; createdAt: number; blob: Blob }
export const DRAFT_BYTE_LIMIT = 5 * 1024 * 1024;
export const DRAFT_COUNT_LIMIT = 3;
export const DRAFT_TTL_MS = 24 * 60 * 60 * 1000;
const DATABASE = 'skyview-attachment-drafts-v1';
const STORE = 'drafts';
let connection: Promise<IDBDatabase> | null = null;
let generation = 0;
function changed() { window.dispatchEvent(new Event('skyview-attachment-drafts-change')); }
function database(): Promise<IDBDatabase> {
  if (connection) return connection;
  if (typeof indexedDB === 'undefined') return Promise.reject(new Error('This browser cannot keep offline files. Nothing was uploaded.'));
  connection = new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => {
      const store = request.result.createObjectStore(STORE, { keyPath: 'id' });
      store.createIndex('session', 'session');
    };
    request.onsuccess = () => {
      const db = request.result;
      db.onversionchange = () => { db.close(); connection = null; };
      resolve(db);
    };
    request.onerror = () => { connection = null; reject(new Error('Offline file storage is unavailable. Nothing was uploaded.')); };
    request.onblocked = () => { connection = null; reject(new Error('Close another open farm tab and retry saving this file.')); };
  });
  return connection;
}
function active(token: number): void {
  if (token !== generation || !offlineEnabled()) throw new Error('Offline file storage was cleared or disabled. Nothing was uploaded.');
}
function valid(record: AttachmentDraft) { const age = Date.now() - record.createdAt; return age >= 0 && age <= DRAFT_TTL_MS && record.size > 0 && record.size <= DRAFT_BYTE_LIMIT; }
function transactionDone(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => { tx.oncomplete = () => resolve(); tx.onerror = () => reject(tx.error || new Error('The file could not be kept on this device.')); tx.onabort = () => reject(tx.error || new Error('The file storage operation was cancelled.')); });
}
function requested<T>(request: IDBRequest<T>): Promise<T> { return new Promise((resolve, reject) => { request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error || new Error('Offline files could not be read.')); }); }


export async function storeAttachmentDraft(session: string, file: File): Promise<AttachmentDraft> {
  if (!session || !offlineEnabled()) throw new Error('Enable offline copies before keeping a file on this device. Nothing was uploaded.');
  if (!file.size || file.size > DRAFT_BYTE_LIMIT) throw new Error('Choose a non-empty file smaller than 5 MB. Nothing was uploaded.');
  const token = generation, db = await database(); active(token);
  const record: AttachmentDraft = { id: 'local-' + crypto.randomUUID(), session, name: file.name.slice(0, 120), type: file.type, size: file.size, createdAt: Date.now(), blob: file };
  const tx = db.transaction(STORE, 'readwrite'); const done = transactionDone(tx);
  const store = tx.objectStore(STORE);
  let failure: Error | undefined;
  const find = store.index('session').getAll(session);
  find.onsuccess = () => {
    try {
      active(token);
      const records = find.result as AttachmentDraft[];
      records.filter(item => !valid(item)).forEach(item => store.delete(item.id));
      if (records.filter(valid).length >= DRAFT_COUNT_LIMIT) throw new Error('Keep up to 3 pending files. Remove or upload one before adding another.');
      store.put(record);
    } catch (error) { failure = error instanceof Error ? error : new Error('The local file could not be saved.'); tx.abort(); }
  };
  try { await done; } catch (error) { throw failure || error; }
  active(token); changed(); return record;
}
export async function listAttachmentDrafts(session: string): Promise<AttachmentDraft[]> {
  if (!session || !offlineEnabled()) return [];
  const token = generation, db = await database(); active(token);
  const tx = db.transaction(STORE, 'readwrite'); const done = transactionDone(tx);
  const store = tx.objectStore(STORE);
  const records = await requested(store.index('session').getAll(session)) as AttachmentDraft[];
  records.filter(item => !valid(item)).forEach(item => store.delete(item.id));
  await done; active(token);
  return records.filter(valid).sort((a, b) => a.createdAt - b.createdAt);
}
export async function removeAttachmentDraft(session: string, id: string): Promise<void> {
  const db = await database();
  const tx = db.transaction(STORE, 'readwrite'); const done = transactionDone(tx);
  const store = tx.objectStore(STORE), record = await requested(store.get(id)) as AttachmentDraft | undefined;
  if (record?.session === session) store.delete(id);
  await done; changed();
}

export function clearAttachmentDrafts(): void {
  generation++; changed();
  void database().then(async db => { const tx = db.transaction(STORE, 'readwrite'); const done = transactionDone(tx); tx.objectStore(STORE).clear(); await done; }).catch(() => {});
}
export async function readAttachmentDraft(session: string, id: string): Promise<File> {
  const draft = (await listAttachmentDrafts(session)).find(item => item.id === id);
  if (!draft) throw new Error('This local file expired or belongs to another farm. Please choose it again.');
  return new File([draft.blob], draft.name, { type: draft.type });
}
