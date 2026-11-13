from collections import Counter
from .config import time_zone
from .models import REPORT_HEADERS

def local_time(value, cfg):
    return value.astimezone(time_zone(cfg['timezone'])).strftime('%d %b %Y, %I:%M:%S %p')

def report(sheet, metrics, run_id, start, end, status, error, ranges, cfg):
    mapping = {'Search Calls':'search_calls', 'Other API Calls':'other_api_calls',
        'Retries':'retries', 'Failed Requests':'failed_requests', 'Results Received':'results_received',
        'Unique Channels Found':'unique_channels_found', 'Duplicates Skipped':'duplicates_skipped',
        'New Channels Checked':'new_channels_checked', 'Old Channels Checked':'old_channels_checked',
        'New Qualified Leads':'new_qualified_leads', 'Old Channels Newly Qualified':'old_newly_qualified',
        'New Emails':'new_emails', 'Contact Rows Added':'contact_rows_added',
        'Needs Review Rows Added':'review_rows_added', 'Rechecks Deferred':'rechecks_deferred',
        'Website Requests':'website_requests', 'Website Failures':'website_failures',
        'Scrapling Pages':'scrapling_pages', 'Scrapling Failures':'scrapling_failures',
        'Browser Pages':'browser_pages', 'Browser Failures':'browser_failures',
        'YouTube Panel Checks':'youtube_panel_pages', 'YouTube Panel Blocks':'youtube_panel_blocked',
        'YouTube Panel Timeouts':'youtube_panel_timeout'}
    summary = {key: metrics[value] for key, value in mapping.items()}
    summary.update({'ID':len(sheet.rows['Daily Report'])+1, 'Run ID':run_id, 'Worker':cfg['worker_name'],
        'Niche':'All', 'Start Time':local_time(start,cfg), 'End Time':local_time(end,cfg),
        'Duration Seconds':round((end-start).total_seconds()), 'Quota Units':metrics['other_api_calls'],
        'Status':status, 'Error':error, 'Rejection Reasons':str(dict(metrics['rejections']))})
    records = [summary]
    for niche, count in sorted(metrics['niche_new'].items()):
        records.append({'Run ID':run_id, 'Worker':cfg['worker_name'], 'Niche':niche,
                        'New Qualified Leads':count, 'Status':'Niche Summary'})
    for title, first, last in ranges:
        records.append({'Run ID':run_id, 'Worker':cfg['worker_name'], 'Target Tab':title,
                        'Start Row':first, 'End Row':last, 'Status':'Row Tracking'})
    sheet.append('Daily Report', records)

def dashboard(sheet, end, cfg):
    leads = sheet.records('All Leads')
    by_id = {r['Channel ID']:r for r in leads if r.get('Channel ID')}
    emails = {(r.get('Channel ID'),r.get('Email')) for r in leads if r.get('Email')}
    review_ids = {r['Channel ID'] for r in sheet.records('Needs Review')
                  if r.get('Channel ID') and r.get('Current Qualification') != 'Promoted'}
    rows = [['Metric','Value'], ['Total Recorded Unique Leads',len(by_id)],
            ['Published Contact Addresses',len(emails)], ['Needs Review Channels',len(review_ids)],
            ['Last Report Update',local_time(end,cfg)],
            ['Currently Marked Qualified',sum(r.get('Current Qualification')=='Qualified' for r in by_id.values())],
            [''], ['Niche','Recorded Unique Leads']]
    niche_start = len(rows)-1
    counts = Counter(r.get('Niche','') for r in by_id.values())
    for niche in sheet.niches:
        rows.append([niche['name'],counts[niche['name']]])
    rows += [[''],['Run Date','New Qualified Leads']]
    daily_start = len(rows)-1
    totals = Counter()
    for row in sheet.records('Daily Report'):
        if row.get('Niche') == 'All':
            totals[str(row.get('Start Time',''))[:11]] += int(row.get('New Qualified Leads') or 0)
    for date, count in list(totals.items())[-30:]:
        rows.append([date,count])
    sheet.grow('Dashboard', len(rows)+1)
    previous = len(sheet.rows['Dashboard']) + 1
    sheet.write('Dashboard','A1',rows)
    if previous > len(rows):
        sheet.call('POST','/values:batchClear',body={'ranges':[f"'Dashboard'!A{len(rows)+1}:B{previous}"]})
    sheet.rows['Dashboard'] = rows[1:]
    # Replace only charts owned by this app; preserve unrelated user charts.
    meta = sheet.call('GET',params={'fields':'sheets(properties(sheetId,title),charts(chartId,spec(title)))'})
    tab = next(s for s in meta['sheets'] if s['properties']['title']=='Dashboard')
    reqs = [{'deleteEmbeddedObject':{'objectId':c['chartId']}} for c in tab.get('charts',[])
            if c.get('spec',{}).get('title') in ('Leads Per Niche','Daily New Leads')]
    sid = tab['properties']['sheetId']
    for title, first, stop, position, kind in [
        ('Leads Per Niche',niche_start,niche_start+1+len(sheet.niches),0,'BAR'),
        ('Daily New Leads',daily_start,len(rows),20,'LINE')]:
        if stop <= first+1:
            continue
        source = lambda column: {'sourceRange':{'sources':[{'sheetId':sid,'startRowIndex':first,
            'endRowIndex':stop,'startColumnIndex':column,'endColumnIndex':column+1}]}}
        reqs.append({'addChart':{'chart':{'spec':{'title':title,'basicChart':{'chartType':kind,
            'legendPosition':'NO_LEGEND','headerCount':1,'domains':[{'domain':source(0)}],
            'series':[{'series':source(1),'targetAxis':'BOTTOM_AXIS' if kind=='BAR' else 'LEFT_AXIS'}]}},
            'position':{'overlayPosition':{'anchorCell':{'sheetId':sid,'rowIndex':position,'columnIndex':4},
                'widthPixels':640,'heightPixels':350}}}}})
    if reqs:
        sheet.call('POST',':batchUpdate',body={'requests':reqs})
