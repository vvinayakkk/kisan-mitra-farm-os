import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
const mocks = vi.hoisted(() => ({ fetch: vi.fn(), download: vi.fn(), success: vi.fn(), error: vi.fn() }));
vi.mock('@/lib/apiClient', () => ({ apiFetch: mocks.fetch }));
vi.mock('sonner', () => ({ toast: {success: mocks.success, error: mocks.error} }));
vi.mock('@/lib/assistantClient', () => ({ useAssistant: () => ({ artifacts: [] }), getAssistantSessionId: () => "session-one", downloadArtifact: mocks.download }));
import { CompanionPanel } from './CompanionPanel';
const data = { name: 'Saathi', status: 'paused', settings: { row_version: 1, name: 'Saathi', enabled: false, frequency_hours: 6, quiet_start: 22, quiet_end: 6, timezone: 'Asia/Kolkata' }, activity: [], channels: { in_app: { connected: true }, whatsapp: { connected: false } }, scope: [] };
beforeEach(() => { vi.clearAllMocks(); mocks.fetch.mockResolvedValue({ ok: true, json: async () => data }); });
afterEach(cleanup);
it('loads on demand without enabling background follow-ups', async () => {
  const { rerender } = render(<CompanionPanel open={false} onClose={vi.fn()} onVoice={vi.fn()}/>);
  expect(mocks.fetch).not.toHaveBeenCalled();
  rerender(<CompanionPanel open onClose={vi.fn()} onVoice={vi.fn()}/>);
  expect(await screen.findByText('Follow-ups paused')).toBeVisible(); expect(screen.getByText('Not linked')).toBeVisible();
  expect(mocks.fetch).toHaveBeenCalledTimes(1); expect(mocks.fetch.mock.calls[0][1].method).toBeUndefined();
});
it('enables only by explicit click with concurrency version and quiet hours', async () => {
  render(<CompanionPanel open onClose={vi.fn()} onVoice={vi.fn()}/>);
  fireEvent.click(await screen.findByRole('button', { name: 'Enable' }));
  await waitFor(() => expect(mocks.fetch).toHaveBeenCalledTimes(2));
  expect(JSON.parse(mocks.fetch.mock.calls[1][1].body)).toEqual({ ...data.settings, enabled: true });
});
it('personalizes inline and routes Talk to live voice', async () => {
  const talk = vi.fn(); render(<CompanionPanel open onClose={vi.fn()} onVoice={talk}/>);
  await screen.findByText('Follow-ups paused'); fireEvent.click(screen.getByRole('button', { name: 'Personalize' }));
  fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Moti' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save preferences' }));
  await waitFor(() => expect(mocks.fetch).toHaveBeenCalledTimes(2));
  expect(JSON.parse(mocks.fetch.mock.calls[1][1].body).name).toBe('Moti');
  fireEvent.click(screen.getByRole('button', { name: 'Talk' })); expect(talk).toHaveBeenCalledOnce();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
it('reports failures without claiming to be watching', async () => {
  mocks.fetch.mockResolvedValue({ ok: false }); render(<CompanionPanel open onClose={vi.fn()} onVoice={vi.fn()}/>);
  expect(await screen.findByRole('alert')).toHaveTextContent('could not connect'); expect(screen.queryByText('Keeping an eye on your farm')).not.toBeInTheDocument();
});

const proposal = {id:'1',area:'records',title:'Review field tasks',summary:'Organize the next visit.',steps:[{title:'Inspect the north field'}],evidence:[],status:'ready',row_version:2};
it('previews in place and keeps navigation inside the preview', async () => {
  mocks.fetch.mockResolvedValue({ok:true,json:async()=>({...data,prepared:[proposal,{...proposal,id:'bad',area:'constructor',title:'Invalid area'}]})});
  const close=vi.fn(); render(<CompanionPanel open onClose={close} onVoice={vi.fn()}/>);
  const toggle = await screen.findByRole('button',{name:'Farm notebook Review field tasks'});
  expect(screen.queryByRole('button',{name:/Approve and save/})).not.toBeInTheDocument();
  expect(screen.queryByText(/steps · saves/)).not.toBeInTheDocument();
  fireEvent.click(toggle);
  expect(screen.getByText(proposal.summary)).toBeVisible();
  expect(screen.getByText('Inspect the north field')).toBeVisible();
  expect(screen.getByRole('link',{name:'Open Farm notebook'})).toHaveAttribute('href','/workspace?view=records');
  expect(screen.queryByText('Invalid area')).not.toBeInTheDocument(); expect(close).not.toHaveBeenCalled();
  expect(screen.getByRole('button',{name:/Approve and save/})).toBeVisible();
  fireEvent.click(toggle);
  expect(screen.queryByRole('button',{name:/Approve and save/})).not.toBeInTheDocument();
});
it('approves without navigating, prevents duplicates and shows a receipt', async () => {
  let finish!: (value: unknown) => void;
  mocks.fetch.mockResolvedValueOnce({ok:true,json:async()=>({...data,prepared:[proposal]})});
  mocks.fetch.mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}));
  const close=vi.fn(); render(<CompanionPanel open onClose={close} onVoice={vi.fn()}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Farm notebook Review field tasks'}));
  const button=await screen.findByRole('button',{name:'Approve and save Review field tasks'});
  fireEvent.click(button); fireEvent.click(button);
  expect(mocks.fetch).toHaveBeenCalledTimes(2); expect(button).toBeDisabled();
  expect(JSON.parse(mocks.fetch.mock.calls[1][1].body)).toEqual({action:'approve',row_version:2});
  finish({ok:true,json:async()=>({proposal:{...proposal,status:'approved',mission_id:'m1'},mission_id:'m1'})});
  expect(await screen.findByRole('status')).toHaveTextContent('Plan saved');
  expect(screen.getByRole('link',{name:'View plan'})).toHaveAttribute('href','/workspace?view=records&tab=missions&mission=m1');
  expect(mocks.success).toHaveBeenCalledOnce(); expect(close).not.toHaveBeenCalled();
});
it('shows conflicts without claiming completion', async () => {
  mocks.fetch.mockResolvedValueOnce({ok:true,json:async()=>({...data,prepared:[proposal]})});
  mocks.fetch.mockResolvedValueOnce({ok:false,status:409,json:async()=>({detail:'This suggestion changed. Refresh before reviewing.'})});
  render(<CompanionPanel open onClose={vi.fn()} onVoice={vi.fn()}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Farm notebook Review field tasks'}));
  fireEvent.click(screen.getByRole('button',{name:'Approve and save Review field tasks'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('This suggestion changed');
  expect(screen.queryByText('Plan saved')).not.toBeInTheDocument(); expect(mocks.success).not.toHaveBeenCalled();
});
it('shows persisted approval after reopening', async () => {
  mocks.fetch.mockResolvedValue({ok:true,json:async()=>({...data,prepared:[{...proposal,status:'approved',mission_id:'m1'}]})});
  render(<CompanionPanel open onClose={vi.fn()} onVoice={vi.fn()}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Farm notebook Review field tasks'}));
  expect(await screen.findByText('Plan saved')).toBeVisible();
  expect(screen.queryByRole('button',{name:/Approve and save/})).not.toBeInTheDocument();
});
