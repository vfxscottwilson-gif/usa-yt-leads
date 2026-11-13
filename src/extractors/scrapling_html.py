"""Scrapling parses already-downloaded HTML; this module performs no network calls."""
import re
from scrapling.parser import Selector

# Ignore scripts, templates and explicitly hidden markup. CSS visibility is not computed.
VISIBLE = "not(ancestor-or-self::script or ancestor-or-self::style or ancestor-or-self::noscript or ancestor-or-self::template or ancestor-or-self::*[@hidden or @aria-hidden='true'])"


def extract(document):
    tree = Selector(document, adaptive=False)
    def values(path):
        return [str(v).strip() for v in tree.xpath(path).get_all() if str(v).strip()]
    result = {
        'emails': [], 'phones': [], 'people': [],
        'links': values('//*[' + VISIBLE + ']/@href'),
    }
    for kind, target in [('email', 'emails'), ('telephone', 'phones')]:
        nodes = tree.xpath('//*[@itemprop="' + kind + '" and ' + VISIBLE + ']')
        for node in nodes:
            value = node.attrib.get('content') or node.attrib.get('href') or ' '.join(node.xpath('.//text()').get_all())
            result[target].append(str(value).strip())
    # A name and job title must occur in the SAME explicit Person scope.
    for person in tree.xpath('//*[@itemscope and (@itemtype="https://schema.org/Person" or @itemtype="http://schema.org/Person") and ' + VISIBLE + ']'):
        def field(name):
            matches = person.xpath('.//*[@itemprop="' + name + '" and not(ancestor::*[@hidden or @aria-hidden="true"])]')
            if not matches:
                return ''
            node = matches[0]
            return str(node.attrib.get('content') or ' '.join(node.xpath('.//text()').get_all())).strip()
        name, role = field('name'), field('jobTitle')
        if name and role and re.search(r'founder|chief executive|\bceo\b|manager|team lead', role, re.I):
            result['people'].append({'@type': 'Person', 'name': name, 'givenName': field('givenName'), 'jobTitle': role})
    return result
