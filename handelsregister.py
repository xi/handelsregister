import argparse
import re

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


def fetch_view_state(session):
    r = session.get('https://www.handelsregister.de/rp_web/erweitertesuche/welcome.xhtml')
    r.raise_for_status()
    soup = BeautifulSoup(r.content, 'html.parser')
    return soup.find('input', {'name': 'javax.faces.ViewState'})['value']


def _search(session, data):
    view_state = fetch_view_state(session)
    r = session.post(
        'https://www.handelsregister.de/rp_web/erweitertesuche/welcome.xhtml',
        data={
            'form': 'form',
            'form:btnSuche': '',
            'javax.faces.ViewState': view_state,
            'form:schlagwortOptionen': 1,
            **data,
        },
    )
    r.raise_for_status()
    return BeautifulSoup(r.content, features='html.parser')


def search(terms, register=''):
    with requests.Session() as session:
        soup = _search(session, {
            'form:schlagwoerter': terms,
            'form:aenlichLautendeSchlagwoerterBoolChkbox_input': 'on',
            'form:registerArt_input': register,
        })

    for item in soup.select('[data-ri]'):
        yield {
            'title': item.find(class_='marginLeft20').text,
            'id': item.find(class_='fontWeightBold').text.strip(),
        }


def get_xml(register, id):
    with requests.Session() as session:
        soup = _search(session, {
            'form:registerNummer': id,
            'form:registerArt_input': register,
        })

        link = soup.select_one('[onclick*="Dokumentart.SI"]')
        field = re.search(
            r"ergebnissForm:selectedSuchErgebnisFormTable:[^']*",
            link['onclick'],
        )[0]

        view_state = soup.select_one('input[name="javax.faces.ViewState"]')['value']
        action = soup.select_one('[action]')['action']

        r2 = session.post(
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
