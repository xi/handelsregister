import argparse
import asyncio

import aiohttp
from bs4 import BeautifulSoup

SESSION_DEFAULTS = {
    'base_url': 'https://www.handelsregister.de',
    'raise_for_status': True,
}

REGISTERS = {
    'HRA': 'Handelsregister Abteilung A',
    'HRB': 'Handelsregister Abteilung B',
    'GnR': 'Genossenschaftsregister',
    'PR': 'Partnerschaftsregister',
    'VR': 'Vereinsregister',
    'GsR': 'Gesellschaftsregister',
}

STATES = {
    'BW': 'Baden-Württemberg',
    'BY': 'Bayern',
    'BE': 'Berlin',
    'BB': 'Brandenburg',
    'HB': 'Bremen',
    'HH': 'Hamburg',
    'HE': 'Hessen',
    'MV': 'Mecklenburg-Vorpommern',
    'NI': 'Niedersachsen',
    'NW': 'Nordrhein-Westfalen',
    'RP': 'Rheinland-Pfalz',
    'SL': 'Saarland',
    'SN': 'Sachsen',
    'ST': 'Sachsen-Anhalt',
    'SH': 'Schleswig-Holstein',
    'TH': 'Thüringen',
}


def remove_none(d):
    return {k: v for k, v in d.items() if v is not None}


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
    si_element = item.find(string='SI')
    if si_element:
        si_element = si_element.find_parent('a')
    if si_element:
        return si_element.attrs['id']


def parse_item(item, ctx):
    return {
        'title': item.select_one('.marginLeft20').text,
        'si_field': parse_si_field(item),
        **parse_id(item.select_one('.fontWeightBold').text, ctx)
    }


async def retry(session, method, path, **kwargs):
    retries = 2
    while True:
        try:
            return await session.request(method, path, **kwargs)
        except aiohttp.client_exceptions.ServerDisconnectedError:
            if retries > 0:
                retries -= 1
                await asyncio.sleep(1)
            else:
                raise


async def get_context(session):
    r = await retry(session, 'GET', '/rp_web/erweitertesuche/welcome.xhtml')
    soup = BeautifulSoup(await r.read(), 'html.parser')

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
            int(option['value'], 10): option.text.strip()
            for option in soup.select(r'#form\:rechtsform_input option')
            if option['value']
        },
    }


async def _search(session, query):
    ctx = await get_context(session)
    r = await retry(session, 'POST', '/rp_web/erweitertesuche/welcome.xhtml', data={
        'form': 'form',
        'form:btnSuche': '',
        'javax.faces.ViewState': ctx['view_state'],
        'form:schlagwortOptionen': 1,
        'form:ergebnisseProSeite_input': 100,
        **remove_none(query),
    })
    soup = BeautifulSoup(await r.read(), features='html.parser')
    return {
        'action': soup.select_one('[action]')['action'],
        'view_state': soup.select_one('input[name="javax.faces.ViewState"]')['value'],
        'truncated': bool(soup.select_one(r'#ergebnissForm\:ergebnisseAnzahl_label')),
        'items': [parse_item(item, ctx) for item in soup.select('[data-ri]')],
    }


async def search(*, terms=[], register='', id='', court='', type='', state=''):
    query = {
        'form:schlagwoerter': ' '.join(terms),
        'form:registerArt_input': register,
        'form:registerNummer': id,
        'form:registergericht_input': court,
        'form:rechtsform_input': type,
    }
    if state:
        query[f'form:{state}_input'] = 'on',
    async with aiohttp.ClientSession(**SESSION_DEFAULTS) as session:
        data = await _search(session, query)
    return data['items']


async def get_xml(register, id, court):
    async with aiohttp.ClientSession(**SESSION_DEFAULTS) as session:
        data = await _search(session, {
            'form:registerArt_input': register,
            'form:registerNummer': id,
            'form:registergericht_input': court,
        })
        field = data['items'][0]['si_field']

        r = await retry(session, 'POST', data['action'], data={
            'ergebnissForm': 'ergebnissForm',
            'javax.faces.ViewState': data['view_state'],
            'property': 'Global.Dokumentart.SI',
            field: field,
        })
        return await r.text()


async def get_list(key):
    if key == 'registers':
        return REGISTERS
    else:
        async with aiohttp.ClientSession(**SESSION_DEFAULTS) as session:
            ctx = await get_context(session)
        return ctx[key]


def get_parser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)

    parser_search = subparsers.add_parser('search', help='find entries in the registers')
    parser_search.add_argument('terms', nargs='*')
    parser_search.add_argument('--register', choices=REGISTERS)
    parser_search.add_argument('--id')
    parser_search.add_argument('--court')
    parser_search.add_argument('--type')
    parser_search.add_argument('--state', choices=STATES)
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


async def amain():
    args = get_parser().parse_args()
    if args.action == 'search':
        for item in await search(
            terms=args.terms,
            register=args.register,
            id=args.id,
            court=args.court,
            type=args.type,
            state=args.state,
        ):
            print(f'{item["reg"]} {item["id"]} {item["court"]}\t{item["title"]}')
    elif args.action == 'xml':
        print(await get_xml(args.register, args.id, args.court))
    else:
        result = await get_list(args.key)
        for key, value in sorted(result.items()):
            print(f'{key}\t{value}')


if __name__ == '__main__':
    asyncio.run(amain())
