import {beforeEach,describe,it,expect,vi} from 'vitest';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {ImportPanel} from './ImportPanel';
import {GroupPanel} from './GroupPanel';
import {AnalysisPanel} from './AnalysisPanel';
import {Group} from './types';
import {request} from './api';
vi.mock('./api',()=>({request:vi.fn()}));
const group:Group={id:'g1',repository:'demo/app',workflow:'CI',job:'test',test:'checkout',canonical:'Error: connection refused',classification:'heuristic',occurrences:[],failure_count:2,failed_job_minutes:4,estimated_investigation_minutes:20,estimated_impact_minutes:24,flaky_candidate:false,scope_failure_rate:1,scope_failure_rate_ci95:[.3,1],observed_outcomes:2,mixed_commit_evidence:[],triage:{status:'new',owner:'',note:'',revision:0},first_seen:'2026-01-01',last_seen:'2026-01-02'};
beforeEach(()=>vi.resetAllMocks());
describe('CI workflows',()=>{
 it('imports structured JSON and distinguishes idempotent replay',async()=>{
  vi.mocked(request).mockResolvedValue({id:'r1',replayed:true});const changed=vi.fn();render(<ImportPanel onImported={changed}/>);
  fireEvent.click(screen.getByText('Import run'));
  expect(await screen.findByText(/Identical run already retained/)).toBeInTheDocument();expect(changed).toHaveBeenCalledOnce();expect(request).toHaveBeenCalledWith('/api/runs','POST',expect.objectContaining({external_id:'build-101'}));
 });
 it('rejects invalid JSON before contacting the API',async()=>{
  render(<ImportPanel onImported={vi.fn()}/>);fireEvent.change(screen.getByLabelText('Run JSON'),{target:{value:'not JSON'}});fireEvent.click(screen.getByText('Import run'));
  await screen.findByRole('alert');expect(request).not.toHaveBeenCalled();
 });
 it('preserves revision conflict feedback without reporting success',async()=>{
  vi.mocked(request).mockRejectedValue(new Error('Triage changed; reload'));const saved=vi.fn();render(<GroupPanel group={group} editable onSaved={saved} onClose={vi.fn()}/>);
  fireEvent.change(screen.getByLabelText('Reason for this change'),{target:{value:'Investigating network failures'}});fireEvent.click(screen.getByText('Save triage'));
  expect(await screen.findByRole('alert')).toHaveTextContent('Triage changed; reload');expect(saved).not.toHaveBeenCalled();
 });
 it('keeps read-only triage fields disabled',()=>{
  render(<GroupPanel group={group} editable={false} onSaved={vi.fn()} onClose={vi.fn()}/>);expect(screen.getByLabelText('Owner')).toBeDisabled();expect(screen.queryByText('Save triage')).not.toBeInTheDocument();
 });
 it('requires explicit consent before sending evidence to a model',async()=>{
  vi.mocked(request).mockResolvedValue({suggestions:[]});render(<AnalysisPanel repository="demo/app" branch="main" editable/>);
  expect(screen.getByText('Request advice')).toBeDisabled();fireEvent.click(screen.getByRole('checkbox'));fireEvent.click(screen.getByText('Request advice'));
  await waitFor(()=>expect(request).toHaveBeenCalledWith('/api/advice?repository=demo%2Fapp&branch=main','POST',{consent:true}));
 });
});
