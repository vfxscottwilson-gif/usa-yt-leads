"""Offline end-to-end orchestration regression: later emails append, never insert or duplicate."""
import copy
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from src.config import load
from src.models import HEADERS, REPORT_HEADERS, iso, utcnow
from src.pipeline import run
from test_core import CID, channel, video

class FakeSheets:
    def __init__(self,cfg,niches):
        self.niches=niches
        self.headers={t:HEADERS for t in ['All Leads','Needs Review']+[n['name'] for n in niches]}
        self.headers['Daily Report']=REPORT_HEADERS
        self.rows={t:[] for t in self.headers}
        self.states={'Channel Memory':{},'Search Memory':{}}

    def setup(self): pass
    def repair_ids(self,*a,**k): pass
    def records(self,title):
        return [dict(zip(self.headers[title],r)) for r in self.rows[title]]
    def channel_ids(self,title): return {r.get('Channel ID') for r in self.records(title) if r.get('Channel ID')}
    def remove_review_duplicates(self):
        in_all=self.channel_ids('All Leads'); header=self.headers['Needs Review']; i=header.index('Channel ID')
        keep=[r for r in self.rows['Needs Review'] if r[i] not in in_all]
        removed=len(self.rows['Needs Review'])-len(keep); self.rows['Needs Review']=keep
        return removed
    def memory(self,title): return copy.deepcopy(self.states[title])
    def save_memory(self,title,data): self.states[title]=copy.deepcopy(data)
    def append(self,title,records):
        if not records: return None
        start=len(self.rows[title])+2
        self.rows[title].extend([[r.get(h,'') for h in self.headers[title]] for r in records])
        return start,start+len(records)-1
    def patch_contact(self,title,contact,changes):
        header=self.headers[title]
        for row in self.rows[title]:
            if row[header.index('Contact ID')]==contact:
                for key,value in changes.items(): row[header.index(key)]=value
    def export_local(self,*args): pass
    def patch_channel_status(self,cid,status,reason,checked):
        for title in ['All Leads']+[n['name'] for n in self.niches]:
            header=self.headers[title]
            for row in self.rows[title]:
                if row[header.index('Channel ID')]==cid:
                    row[header.index('Current Qualification')]=status
                    row[header.index('Qualification Checked At')]=checked
                    row[header.index('Review Reason')]=reason

class FakeApi:
    def channels(self,ids): return {CID:channel()} if CID in ids else {}
    def videos(self,playlist): return [video(days=3),video(days=8),video(days=13)],True
    def featured(self,cid): return ['UC' + 'f'*22]

class PipelineTests(unittest.TestCase):
    def test_later_discovered_contact_is_bottom_append_and_existing_lead_is_not_new(self):
        cfg,niches=load()
        cfg['confirmed_talking_head_channel_ids']=[CID]
        sheet=FakeSheets(cfg,niches)
        emails=['first@example.org']
        class Research:
            def collect(self,*args):
                return dict(contacts={email:dict(email=email,source='https://site.org/contact',supported=True,
                    evidence='Published contact') for email in emails},links={},phones=[],team_pages=[],people=[],failure=False)
        with tempfile.TemporaryDirectory() as temporary, \
                patch('src.pipeline.load',return_value=(cfg,niches)), \
                patch('src.pipeline.ROOT',Path(temporary)), \
                patch('src.pipeline.Sheets',return_value=sheet), \
                patch('src.pipeline.YouTube',return_value=FakeApi()), \
                patch('src.pipeline.Research',return_value=Research()), \
                patch('src.pipeline.discover',return_value={CID:'Real Estate'}), \
                patch('src.pipeline.dashboard'), \
                patch.dict('os.environ',YOUTUBE_API_KEY='test',GOOGLE_SERVICE_ACCOUNT_JSON='{}',GOOGLE_SHEET_ID='test'):
            self.assertEqual(run(),0)
            first=copy.deepcopy(sheet.rows['All Leads'][0])
            # A second channel's pre-existing row separates later discoveries from the first channel.
            other=dict(zip(HEADERS,first))
            other.update({'Channel ID':'UC'+'b'*22,'Contact ID':'other','Email':'other@example.org'})
            sheet.append('All Leads',[other])
            sheet.states['Channel Memory'][CID]['next_review']=iso(utcnow()-timedelta(days=1))
            emails.append('later@gmail.com')
            self.assertEqual(run(),0)
            rows=sheet.records('All Leads')
            self.assertEqual(len(rows),3)
            self.assertEqual(rows[0]['Email'],'first@example.org')
            self.assertEqual(rows[0]['Run ID'],dict(zip(HEADERS,first))['Run ID'])
            self.assertEqual(rows[-1]['Email'],'later@gmail.com')
            summaries=[r for r in sheet.records('Daily Report') if r.get('Niche')=='All']
            self.assertEqual([r['New Qualified Leads'] for r in summaries],[1,0])
            self.assertEqual(summaries[-1]['New Emails'],1)
            # Rerunning before the next review must not append anything.
            self.assertEqual(run(),0)
            self.assertEqual(len(sheet.rows['All Leads']),3)
            # A later failed activity check changes only operational status, never removes contacts.
            sheet.states['Channel Memory'][CID]['next_review']=iso(utcnow()-timedelta(days=1))
            with patch.object(FakeApi,'videos',return_value=([video(days=3),video(days=8)],True)):
                self.assertEqual(run(),0)
            rows=sheet.records('All Leads')
            self.assertEqual(len(rows),3)
            self.assertEqual(rows[0]['Current Qualification'],'No Longer Meets Filters')
            self.assertEqual(rows[0]['Email'],'first@example.org')

class StickyDecisionTests(unittest.TestCase):
    def run_once(self, sheet, cfg, niches):
        class Research:
            def collect(self,*args):
                return dict(contacts={'a@example.org':dict(email='a@example.org',source='https://site.org',supported=True,
                    evidence='Published contact')},links={},phones=[],team_pages=[],people=[],failure=False)
        with tempfile.TemporaryDirectory() as temporary,                 patch('src.pipeline.load',return_value=(cfg,niches)),                 patch('src.pipeline.ROOT',Path(temporary)),                 patch('src.pipeline.Sheets',return_value=sheet),                 patch('src.pipeline.YouTube',return_value=FakeApi()),                 patch('src.pipeline.Research',return_value=Research()),                 patch('src.pipeline.discover',return_value={CID:'Real Estate'}),                 patch('src.pipeline.dashboard'),                 patch.dict('os.environ',YOUTUBE_API_KEY='test',GOOGLE_SERVICE_ACCOUNT_JSON='{}',GOOGLE_SHEET_ID='test'):
            self.assertEqual(run(),0)

    def test_channel_sitting_in_needs_review_is_not_added_to_all_leads(self):
        cfg,niches=load()
        cfg['confirmed_talking_head_channel_ids']=[CID]
        sheet=FakeSheets(cfg,niches)
        sheet.append('Needs Review',[{'Channel ID':CID,'Contact ID':'old','Email':'old@example.org'}])
        self.run_once(sheet,cfg,niches)
        self.assertEqual(sheet.rows['All Leads'],[])

    def test_channel_you_moved_to_all_leads_is_not_added_back_to_needs_review(self):
        cfg,niches=load()
        cfg['require_talking_head_confirmation']=True      # makes this channel evaluate as Needs Review
        control=FakeSheets(cfg,niches)
        self.run_once(control,cfg,niches)
        self.assertEqual(len(control.rows['Needs Review']),1)     # without your move it would go to review
        sheet=FakeSheets(cfg,niches)
        sheet.append('All Leads',[{'Channel ID':CID,'Contact ID':'moved','Email':'moved@example.org'}])
        self.run_once(sheet,cfg,niches)
        self.assertEqual(sheet.rows['Needs Review'],[])


    def test_existing_duplicate_in_needs_review_is_removed_and_nothing_comes_back(self):
        cfg,niches=load()
        cfg['require_talking_head_confirmation']=True      # this channel would be sent to Needs Review
        sheet=FakeSheets(cfg,niches)
        sheet.append('All Leads',[{'Channel ID':CID,'Contact ID':'kept','Email':'kept@example.org'}])
        sheet.append('Needs Review',[{'Channel ID':CID,'Contact ID':'dup','Email':'dup@example.org'},
                                     {'Channel ID':'UC'+'z'*22,'Contact ID':'other','Email':'other@example.org'}])
        self.run_once(sheet,cfg,niches)
        self.assertEqual([r['Contact ID'] for r in sheet.records('Needs Review')],['other'])   # duplicate gone, other lead untouched
        self.assertEqual([r['Contact ID'] for r in sheet.records('All Leads')],['kept'])
        self.run_once(sheet,cfg,niches)                                                          # a second run changes nothing
        self.assertEqual(len(sheet.rows['Needs Review']),1)


if __name__=='__main__': unittest.main()
