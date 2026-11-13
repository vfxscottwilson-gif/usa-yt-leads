import hashlib
from datetime import datetime, timezone

HEADERS = ['ID', 'Channel Name', 'First Name', 'Full Name', 'Designation', 'Email', 'Guessed Email',
           'YouTube Link', 'Niche', 'Score', 'Tier', 'Pitch Angle', 'Website', 'Instagram', 'Facebook', 'LinkedIn',
           'Personal LinkedIn', 'Company LinkedIn', 'Twitter And X', 'All Discovered Links', 'Link Sources',
           'Phone Number', 'Business Address', 'Subscribers', 'Videos Checked',
           'Videos Meeting View Threshold', 'Average Views', 'Long Uploads In Activity Window',
           'Last Upload', 'Suggested Editing Quote', 'Notes', 'Contact Source',
           'Evidence Note', 'Email Added At', 'Last Checked', 'Email Status',
           'Current Qualification', 'Qualification Checked At', 'Review Reason', 'Review Decision',
           'Channel ID', 'Contact ID', 'Run ID']

REPORT_HEADERS = ['ID', 'Run ID', 'Worker', 'Niche', 'Start Time', 'End Time',
 'Duration Seconds', 'Search Calls', 'Other API Calls', 'Quota Units', 'Retries',
 'Failed Requests', 'Results Received', 'Unique Channels Found', 'Duplicates Skipped',
 'New Channels Checked', 'Old Channels Checked', 'New Qualified Leads',
 'Old Channels Newly Qualified', 'New Emails', 'Contact Rows Added',
 'Needs Review Rows Added', 'Rechecks Deferred', 'Website Requests', 'Website Failures',
 'Rejection Reasons', 'Target Tab', 'Start Row', 'End Row', 'Status', 'Error', 'Scrapling Pages', 'Scrapling Failures', 'Browser Pages', 'Browser Failures', 'YouTube Panel Checks', 'YouTube Panel Blocks', 'YouTube Panel Timeouts']

def utcnow():
    return datetime.now(timezone.utc)

def iso(value=None):
    return (value or utcnow()).isoformat()

def parse(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))

def contact_id(channel, email):
    # An email is not assumed to identify the same person across different channels.
    return hashlib.sha256(f'{channel}|{email.strip().lower()}'.encode()).hexdigest()[:24]

def next_delay(attempts, cfg):
    delays = cfg['recheck_delays_days']
    return delays[min(attempts, len(delays) - 1)]
