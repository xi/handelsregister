import argparse
import sys
import re

import requests
from bs4 import BeautifulSoup


SEARCH_DEFAULTS = {
    'suchTyp': 'n',
    'form': 'form',
    'form:btnSuche': 'form:btnSuche',
    'javax.faces.partial.ajax': 'true',
    'javax.faces.partial.execute': '@all',
    'javax.faces.ViewState': 'stateless',
}

REGISTERS = {
    'HRA': 'Handelsregister Abteilung A',
    'HRB': 'Handelsregister Abteilung B',
    'GnR': 'Genossenschaftsregister',
    'PR': 'Partnerschaftsregister',
    'VR': 'Vereinsregister',
    'GsR': 'Gesellschaftsregister',
}


def search(terms, register=''):
    r = requests.post(
        'https://www.handelsregister.de/rp_web/erweitertesuche.xhtml',
        data={
            **SEARCH_DEFAULTS,
            'form:registerArt_input': register,
            'form:schlagwoerter': terms,
            'form:schlagwortOptionen': 1,
            'form:aenlichLautendeSchlagwoerterBoolChkbox_input': 'on',
        }
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.content, features='html.parser')
    for item in soup.select('[data-ri]'):
        yield {
            'title': item.find(class_='marginLeft20').text,
            'id': item.find(class_='fontWeightBold').text.strip(),
        }


def get_xml(register, id):
    s = requests.Session()
    r = s.post(
        'https://www.handelsregister.de/rp_web/erweitertesuche.xhtml',
        data={
            **SEARCH_DEFAULTS,
            'form:registerArt_input': register,
            'form:registerNummer': id,
        },
    )
    r.raise_for_status()

    field = None
    for x in re.findall(r'PrimeFaces.addSubmitParam\([^)]*', r.text):
        if 'Global.Dokumentart.SI' in x:
            field = re.search(r"ergebnissForm:selectedSuchErgebnisFormTable:[^']*", x)[0]
            break
    if not field:
        raise ValueError

    view_state = re.search(r'<update id="j_id1:javax.faces.ViewState:0"><!\[CDATA\[([-0-9]*:[-0-9]*)\]\]></update>', r.text)[1]
    action = re.search('action="([^"]*)"', r.text)[1]

    r2 = s.post(
        f'https://www.handelsregister.de{action}',
        data={
            'ergebnissForm': 'ergebnissForm',
            'javax.faces.ViewState': view_state,
            'property': 'Global.Dokumentart.SI',
            field: field,
        },
    )
    r2.raise_for_status()

    return r2.text


def get_parser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)

    parser_search = subparsers.add_parser('search', help='find entries in the registers')
    parser_search.add_argument('terms')
    parser_search.set_defaults(action='search')

    parser_xml = subparsers.add_parser('xml', help='get data for a specific ID')
    parser_xml.add_argument('register', choices=REGISTERS)
    parser_xml.add_argument('id')
    parser_xml.set_defaults(action='xml')

    return parser

if __name__ == '__main__':
    args = get_parser().parse_args()
    if args.action == 'search':
        for item in search(args.terms):
            print(item['title'])
            print('\t' + item['id'])
    else:
        print(get_xml(args.register, args.id))
