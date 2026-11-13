import copy
import json
import unittest
from collections import Counter
from datetime import timedelta
from unittest.mock import patch

from src.config import load
from src.models import contact_id, next_delay, iso, utcnow, HEADERS
from src.qualification import evaluate, precheck, duration
from src.contacts import Page, Research, people_from_structured, safe_public_url
from src.youtube import YouTube, BudgetStop
from src.sheets import Sheets, SheetsError
from src.pipeline import build_rows

CID = 'UC' + 'a' * 22

def channel(subscribers=100000, country=None):
    country = country or load()[0]['countries'][0]   # tests follow whichever country this package targets
    return {'id':CID,'snippet':{'title':'Real Estate Creator','description':'Real estate advice', 'country':country},
        'statistics':{'subscriberCount':str(subscribers)},
        'contentDetails':{'relatedPlaylists':{'uploads':'UPLOADS'}}}

def video(views=25000, days=3, seconds=600):
    return dict(id=str(days),title='Real estate investing',description='',
        published=iso(utcnow()-timedelta(days=days)),views=views,seconds=seconds,language='en')

class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.cfg,self.niches=load()

    def check(self, videos, **kwargs):
        return evaluate(channel(),videos,kwargs.get('complete',True),self.cfg,self.niches,kwargs.get('confirmed',True))

    def test_two_strong_videos_qualify_even_if_median_is_low(self):
        values=[video(25000,3),video(40000,7),video(1000,11),video(1000,15),video(1000,20)]
        self.assertEqual(self.check(values)['status'],'qualified')

    def test_one_strong_video_is_rejected(self):
        self.assertEqual(self.check([video(25000,3),video(1000,7),video(1000,12)])['status'],'rejected')

    def test_two_uploads_fail_three_uploads_pass(self):
        self.assertEqual(self.check([video(days=3),video(days=9)])['status'],'rejected')
        self.assertEqual(self.check([video(days=3),video(days=9),video(1000,15)])['status'],'qualified')

    def test_shorts_do_not_count_as_uploads_or_successful_views(self):
        values=[video(1000000,1,60),video(1000000,2,180),video(25000,3),video(25000,6)]
        self.assertEqual(self.check(values)['status'],'rejected')

    def test_fewer_than_twenty_available_is_allowed(self):
        result=self.check([video(days=3),video(days=8),video(days=13)])
        self.assertEqual(result['status'],'qualified')
        self.assertEqual(result['videos_checked'],3)

    def test_hits_outside_latest_twenty_do_not_count(self):
        values=[video(1000,day+1) for day in range(20)]+[video(999999,25),video(999999,26)]
        self.assertEqual(self.check(values)['status'],'rejected')

    def test_unknown_format_is_review_when_explicitly_required(self):
        self.cfg['require_talking_head_confirmation']=True
        self.assertEqual(self.check([video(days=3),video(days=8),video(days=13)],confirmed=False)['status'],'review')

    def test_reviewer_qualifies_without_talking_head_confirmation(self):
        self.assertFalse(self.cfg['require_talking_head_confirmation'])
        self.assertEqual(self.check([video(days=3),video(days=8),video(days=13)],confirmed=False)['status'],'qualified')

    def test_incomplete_scan_does_not_falsely_reject(self):
        self.assertEqual(self.check([video(1000)],complete=False)['status'],'review')

    def test_subscriber_boundaries_and_country(self):
        self.assertEqual(precheck(channel(50000),self.cfg)[0],'')
        self.assertEqual(precheck(channel(1000000),self.cfg)[0],'')
        self.assertEqual(precheck(channel(49999),self.cfg)[0],'rejected')
        self.assertEqual(precheck(channel(country='FR'),self.cfg)[0],'rejected')

    def test_duration(self):
        self.assertEqual(duration('P1DT1H2M3S'),90123)
        self.assertEqual(duration('PT3M'),180)

    def test_review_schedule(self):
        self.assertEqual([next_delay(i,self.cfg) for i in range(5)],[20,30,30,90,90])

class ContactTests(unittest.TestCase):
    def test_personal_and_company_linkedin_preserve_all_sources(self):
        from src.contacts import record_link
        result={'links':{}}
        for url in ['https://www.linkedin.com/in/person-one','https://linkedin.com/in/person-two','https://linkedin.com/company/business']:
            record_link(result,url,'https://youtube.com/channel/example')
        self.assertEqual(len(result['links']['Personal LinkedIn'].splitlines()),2)
        self.assertEqual(len(result['links']['Company LinkedIn'].splitlines()),1)
        self.assertEqual(len(result['_link_evidence']),3)

    def test_channel_ids_not_names_control_identity(self):
        self.assertNotEqual(contact_id(CID,'same@example.org'),contact_id('UC'+'b'*22,'same@example.org'))
        self.assertEqual(contact_id(CID,' ME@EXAMPLE.ORG '),contact_id(CID,'me@example.org'))

    def test_parser_ignores_script_emails_and_keeps_mailto(self):
        page=Page()
        page.feed('<script>"wrong@example.org"</script><a href="mailto:hello@example.org">Email</a>')
        self.assertNotIn('wrong@example.org',' '.join(page.text))
        self.assertEqual(page.mail,['hello@example.org'])

    def test_explicit_structured_name_and_role_only(self):
        value={'@type':'Organization','founder':{'name':'Example Person','givenName':'Example'}}
        self.assertEqual(people_from_structured(value,'https://site.org/team')[0]['designation'],'Founder')
        self.assertEqual(people_from_structured({'@type':'Person','name':'Unknown'},'url'),[])

    def test_private_targets_blocked(self):
        self.assertFalse(safe_public_url('http://127.0.0.1/contact'))
        self.assertFalse(safe_public_url('file:///etc/passwd'))
        self.assertFalse(safe_public_url('https://user:password@example.org'))

    def test_all_addresses_have_separate_rows_and_no_inferred_name(self):
        cfg,niches=load()
        evaluation=evaluate(channel(),[video(days=3),video(days=8),video(days=13)],True,cfg,niches,True)
        result={'contacts':{},'links':{},'phones':[],'team_pages':[],'people':[]}
        for email in ['oliver@example.org','info@example.org','creator@gmail.com']:
            Research.add(result,email,'https://site.org/contact',True,'Published business contact')
        rows=build_rows(channel(),evaluation,result,cfg,'run',utcnow())
        self.assertEqual(len(rows),3)
        self.assertTrue(all(r['Full Name']=='Team' for r in rows))
        self.assertTrue(all(r['YouTube Link'] for r in rows))
        self.assertNotIn('Email Type',HEADERS)

    def test_uncertain_email_keeps_a_qualified_channel_qualified(self):
        cfg,niches=load()
        evaluation=evaluate(channel(),[video(days=3),video(days=8),video(days=13)],True,cfg,niches,True)
        result={'contacts':{},'links':{},'phones':[],'team_pages':[],'people':[]}
        Research.add(result,'maybe@example.org','https://site.org',False,'Unclear relationship')
        row=build_rows(channel(),evaluation,result,cfg,'run',utcnow())[0]
        self.assertEqual(row['Current Qualification'],'Qualified')   # channel qualifies; the email is flagged separately
        self.assertEqual(row['Email Status'],'Needs Verification')

class SheetTests(unittest.TestCase):
    def test_new_sheet_grid_expands_before_wide_headers(self):
        cfg,niches=load()
        sheet=object.__new__(Sheets)
        sheet.cfg,sheet.niches=cfg,niches
        sheet.headers,sheet.rows={},{}
        titles=['Dashboard','Daily Report','All Leads','Needs Review']+[n['name'] for n in niches]+[
            'Settings','Channel Memory','Search Memory']
        props={name:{'title':name,'sheetId':i,'gridProperties':{'columnCount':26,'rowCount':1000}}
               for i,name in enumerate(titles)}
        def call(method,path='',body=None,params=None,**kwargs):
            if method=='GET':
                return {'sheets':[{'properties':copy.deepcopy(p)} for p in props.values()]}
            for request in (body or {}).get('requests',[]):
                if 'updateSheetProperties' in request:
                    value=request['updateSheetProperties']['properties']
                    for p in props.values():
                        if p['sheetId']==value['sheetId']:
                            p['gridProperties'].update(value.get('gridProperties',{}))
            return {}
        def write(title,cell,values,**kwargs):
            self.assertGreaterEqual(props[title]['gridProperties']['columnCount'],max(map(len,values)))
        sheet.call,sheet.write=call,write
        sheet.read=lambda title:[]
        sheet.setup()
        self.assertEqual(len(sheet.headers['All Leads']),len(HEADERS))

    def fake(self):
        sheet=object.__new__(Sheets)
        sheet.cfg={'max_formula_rows':50000}
        sheet.headers={'All Leads':list(reversed(HEADERS))}
        sheet.rows={'All Leads':[]}
        sheet.tabs={}
        sheet.grow=lambda *args:None
        sheet.read=lambda title:[sheet.headers[title]]+copy.deepcopy(sheet.rows[title])
        sheet.writes=[]
        sheet.write=lambda title,cell,values,formula=False:sheet.writes.append((cell,values,formula))
        return sheet

    def test_header_reordering_and_append_only(self):
        sheet=self.fake()
        sheet.append('All Leads',[{'Channel ID':CID,'Contact ID':'one','Email':'first@example.org'}])
        first=copy.deepcopy(sheet.rows['All Leads'][0])
        sheet.append('All Leads',[{'Channel ID':CID,'Contact ID':'two','Email':'later@example.org'}])
        self.assertEqual(sheet.rows['All Leads'][0],first)
        self.assertEqual(sheet.records('All Leads')[1]['Email'],'later@example.org')
        self.assertTrue(any('COUNTIF' in str(values) for _,values,_ in sheet.writes))
        # Raw data is separate from formulas to avoid interpreting website text as formulas.
        self.assertFalse(sheet.writes[0][2])

    def test_status_patch_after_rows_move_never_writes_to_wrong_row(self):
        sheet=self.fake()
        sheet.append('All Leads',[{'Channel ID':CID,'Contact ID':'one'}])
        sheet.read=lambda title:[sheet.headers[title], ['']*len(HEADERS)]
        before=len(sheet.writes)
        sheet.patch_contact('All Leads','one',{'Current Qualification':'Qualified'})  # refreshes, finds nothing, no crash
        self.assertEqual(len(sheet.writes),before)

    def test_id_formula_uses_channel_identifier_column(self):
        sheet=self.fake()
        sheet.append('All Leads',[{'Channel ID':CID}])
        formula=sheet.writes[-1][1][0][0]
        # Reversed header puts Channel ID at C, not a hard-coded D column.
        self.assertIn('C$2:C2',formula)

class ApiTests(unittest.TestCase):
    def test_search_budget_stops_before_call(self):
        cfg,_=load()
        from unittest.mock import Mock
        api=YouTube('fake',cfg,Counter(search_calls=cfg['max_searches']),session=Mock())
        with self.assertRaises(BudgetStop):
            api.get('search')
        api.session.get.assert_not_called()

    def test_upload_pagination_goes_past_shorts(self):
        cfg,_=load()
        api=YouTube('fake',cfg,Counter(),session=object())
        pages=iter([
            {'items':[{'contentDetails':{'videoId':'short'}}], 'nextPageToken':'page2'},
            {'items':[{'id':'short','snippet':{'title':'Short','publishedAt':iso()},
                'contentDetails':{'duration':'PT1M'},'statistics':{'viewCount':'999999'}}]},
            {'items':[{'contentDetails':{'videoId':'long'}}]},
            {'items':[{'id':'long','snippet':{'title':'Long','publishedAt':iso()},
                'contentDetails':{'duration':'PT10M'},'statistics':{'viewCount':'30000'}}]}
        ])
        api.get=lambda *a,**k:next(pages)
        videos,complete=api.videos('playlist')
        self.assertTrue(complete)
        self.assertEqual(sorted(v['seconds'] for v in videos),[60,600])

if __name__=='__main__':
    unittest.main()
