import { beforeEach, expect, it, vi } from 'vitest';
const permission = vi.hoisted(() => ({ enabled: true }));
vi.mock('./offlineConsent', () => ({ offlineEnabled: () => permission.enabled }));
import { clearAttachmentDrafts, DRAFT_BYTE_LIMIT, DRAFT_TTL_MS, listAttachmentDrafts, readAttachmentDraft, removeAttachmentDraft, storeAttachmentDraft } from './attachmentDrafts';



const records = new Map<string, any>();
function transaction() {
  const tx: any = { pending: 0, aborted: false, abort() { this.aborted = true; queueMicrotask(() => this.onabort?.()); } };
  const operation = (work: () => any) => {
    const request: any = {}; tx.pending++;
    queueMicrotask(() => {
      if (!tx.aborted) { request.result = work(); request.onsuccess?.(); }
      tx.pending--;
      queueMicrotask(() => { if (!tx.pending && !tx.aborted) tx.oncomplete?.(); });
    });
    return request;
  };
  const store = { index: () => ({ getAll: (session: string) => operation(() => [...records.values()].filter(item => item.session === session)) }), get: (id: string) => operation(() => records.get(id)), put: (item: any) => operation(() => records.set(item.id, item)), delete: (id: string) => operation(() => records.delete(id)), clear: () => operation(() => records.clear()) };
  tx.objectStore = () => store;
  return tx;
}
const db = { transaction, createObjectStore: () => ({ createIndex() {} }), close() {} };
vi.stubGlobal('indexedDB', { open() { const request: any = {}; queueMicrotask(() => { request.result = db; request.onupgradeneeded?.(); request.onsuccess?.(); }); return request; } });
beforeEach(async () => {
  permission.enabled = true; records.clear(); vi.restoreAllMocks();
  vi.stubGlobal('fetch', vi.fn(() => { throw new Error('Draft storage must never call the network'); }));
  clearAttachmentDrafts(); await new Promise(resolve => setTimeout(resolve, 0));
});
it('keeps selected bytes local and isolates owners without sending or inventing server IDs', async () => {
  const saved = await storeAttachmentDraft('farmer-a', new File(['private-photo'], 'leaf.jpg', { type: 'image/jpeg' }));
  expect(saved.id).toMatch(/^local-/);
  expect((await listAttachmentDrafts('farmer-a'))[0].name).toBe('leaf.jpg');
  expect(await listAttachmentDrafts('farmer-b')).toEqual([]);
  await expect(readAttachmentDraft('farmer-b', saved.id)).rejects.toThrow('another farm');
  await removeAttachmentDraft('farmer-b', saved.id);
  expect(await listAttachmentDrafts('farmer-a')).toHaveLength(1);
  const file = await readAttachmentDraft('farmer-a', saved.id);
  expect(file.size).toBe(13); expect(file.name).toBe('leaf.jpg');
  expect(fetch).not.toHaveBeenCalled();
});
it('requires explicit opt-in and enforces per-file and per-owner limits', async () => {
  permission.enabled = false;
  await expect(storeAttachmentDraft('a', new File(['x'], 'a.txt'))).rejects.toThrow('Enable offline copies');
  permission.enabled = true;
  await expect(storeAttachmentDraft('a', new File([new Uint8Array(DRAFT_BYTE_LIMIT + 1)], 'large.bin'))).rejects.toThrow('5 MB');
  for (let i = 0; i < 3; i++) await storeAttachmentDraft('a', new File(['x'], `file${i}.txt`));
  await expect(storeAttachmentDraft('a', new File(['x'], 'fourth.txt'))).rejects.toThrow('3 pending files');
  expect(await listAttachmentDrafts('a')).toHaveLength(3);
  expect(await storeAttachmentDraft('b', new File(['x'], 'other.txt'))).toMatchObject({ session: 'b' });
});
it('expires after 24 hours and frees a pending slot rather than uploading anything', async () => {
  const now = Date.now();
  await storeAttachmentDraft('a', new File(['x'], 'old.txt'));
  vi.spyOn(Date, 'now').mockReturnValue(now + DRAFT_TTL_MS + 1000);
  expect(await listAttachmentDrafts('a')).toEqual([]);
  expect(records.size).toBe(0); expect(fetch).not.toHaveBeenCalled();
});
it('logout or disabling storage invalidates in-flight work and deletes all owners’ bytes', async () => {
  await storeAttachmentDraft('a', new File(['x'], 'one.txt'));
  await storeAttachmentDraft('b', new File(['x'], 'two.txt'));
  const pending = storeAttachmentDraft('a', new File(['x'], 'late.txt'));
  clearAttachmentDrafts(); permission.enabled = false;
  await expect(pending).rejects.toThrow('cleared or disabled');
  await new Promise(resolve => setTimeout(resolve, 0));
  expect(records.size).toBe(0);
  expect(await listAttachmentDrafts('a')).toEqual([]);
});
