import argparse
import re
import time

import requests
from bs4 import BeautifulSoup

REGISTERS = {
    'HRA': 'Handelsregister Abteilung A',
    'HRB': 'Handelsregister Abteilung B',
    'GnR': 'Genossenschaftsregister',
    'PR': 'Partnerschaftsregister',
    'VR': 'Vereinsregister',
    'GsR': 'Gesellschaftsregister',
}


def parse_id(s, ctx):
    parts = s.strip().split()
    for i in range(len(parts) - 2, 0, -1):
        reg = parts[i]
        if reg in REGISTERS:
            tail = parts[i + 1:]
            if 'früher' in tail:
                tail = tail[:tail.index('früher')]
            return {
                'court': ctx['rev_courts'][' '.join(parts[1:i])],
                'reg': reg,
                'id': ' '.join(tail),
            }
    raise ValueError(s)


def parse_si_field(item):
    si_element = item.select_one('[onclick*="Dokumentart.SI"]')
    if si_element:
        m = re.search(
            r"ergebnissForm:selectedSuchErgebnisFormTable:[^']*",
            si_element['onclick'],
        )
        if m:
            return m[0]


def parse_item(item, ctx):
    return {
        'title': item.select_one('.marginLeft20').text,
        'si_field': parse_si_field(item),
        **parse_id(item.select_one('.fontWeightBold').text, ctx)
    }


class Session(requests.Session):
    def request(self, *args, **kwargs):
        retries = 2
        while True:
            try:
                r = super().request(*args, **kwargs)
                r.raise_for_status()
                return r
            except requests.exceptions.ConnectionError:
                if retries > 0:
                    retries -= 1
                    time.sleep(1)
                else:
                    raise


def get_context(session):
    r = session.get('https://www.handelsregister.de/rp_web/erweitertesuche/welcome.xhtml')
    soup = BeautifulSoup(r.content, 'html.parser')

    return {
        'view_state': soup.select_one('input[name="javax.faces.ViewState"]')['value'],
        'courts': {
            option['value']: option.text.strip()
            for option in soup.select(r'#form\:registergericht_input option')
            if option['value']
        },
        'rev_courts': {
            option.text.strip(): option['value']
            for option in soup.select(r'#form\:registergericht_input option')
            if option['value']
        },
        'types': {
            option['value']: option.text.strip()
            for option in soup.select(r'#form\:rechtsform_input option')
            if option['value']
        },
    }


def _search(session, query):
    ctx = get_context(session)
    r = session.post(
        'https://www.handelsregister.de/rp_web/erweitertesuche/welcome.xhtml',
        data={
            'form': 'form',
            'form:btnSuche': '',
            'javax.faces.ViewState': ctx['view_state'],
            'form:schlagwortOptionen': 1,
            'form:aenlichLautendeSchlagwoerterBoolChkbox_input': 'on',
            'form:ergebnisseProSeite_input': 100,
            **query,
        },
    )
    soup = BeautifulSoup(r.content, features='html.parser')
    return {
        'action': soup.select_one('[action]')['action'],
        'view_state': soup.select_one('input[name="javax.faces.ViewState"]')['value'],
        'truncated': bool(soup.select_one(r'#ergebnissForm\:ergebnisseAnzahl_label')),
        'items': [parse_item(item, ctx) for item in soup.select('[data-ri]')],
    }


def search(terms, register=''):
    query = {
        'form:schlagwoerter': terms,
        'form:registerArt_input': register,
    }
    with Session() as session:
        data = _search(session, query)
    return data['items']


def get_xml(register, id, court):
    with Session() as session:
        data = _search(session, {
            'form:registerArt_input': register,
            'form:registerNummer': id,
            'form:registergericht_input': court,
        })
        field = data['items'][0]['si_field']

        r = session.post(
            f'https://www.handelsregister.de{data["action"]}',
            data={
                'ergebnissForm': 'ergebnissForm',
                'javax.faces.ViewState': data['view_state'],
                'property': 'Global.Dokumentart.SI',
                field: field,
            },
        )
        return r.text


def get_list(key):
    if key == 'registers':
        return REGISTERS
    else:
        with Session() as session:
            ctx = get_context(session)
        return ctx[key]


def get_parser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)

    parser_search = subparsers.add_parser('search', help='find entries in the registers')
    parser_search.add_argument('terms')
    parser_search.set_defaults(action='search')

    parser_xml = subparsers.add_parser('xml', help='get data for a specific ID')
    parser_xml.add_argument('register', choices=REGISTERS)
    parser_xml.add_argument('id')
    parser_xml.add_argument('court')
    parser_xml.set_defaults(action='xml')

    parser_list = subparsers.add_parser('list', help='get data for a specific ID')
    parser_list.add_argument('key', choices=['registers', 'courts', 'types'])
    parser_list.set_defaults(action='list')

    return parser


if __name__ == '__main__':
    args = get_parser().parse_args()
    if args.action == 'search':
        for item in search(args.terms):
            print(item['title'])
            print('\t', item['court'], item['reg'], item['id'])
    elif args.action == 'xml':
        print(get_xml(args.register, args.id, args.court))
    else:
        for key, value in get_list(args.key).items():
            print(f'{key}\t{value}')
