import datetime
import os
import re

import requests
from lxml import etree

API = 'https://api.github.com/graphql'
HEADERS = {'Authorization': 'Bearer ' + os.environ['ACCESS_TOKEN']}
USER_NAME = os.environ['USER_NAME']
SVGS = ('dark_mode.svg', 'light_mode.svg')
LEFT_DOTS = 12   # left half = 28 cols: 14 fixed + 2 spaces + dots + value
RIGHT_DOTS = 19  # right half = 29 cols: 8 fixed + 2 spaces + dots + value


def gql(query):
    r = requests.post(API, json={'query': query, 'variables': {'login': USER_NAME}},
                      headers=HEADERS, timeout=30)
    r.raise_for_status()
    body = r.json()
    if 'errors' in body:
        raise RuntimeError(body['errors'])
    return body['data']['user']


def get_stats():
    user = gql('''query($login: String!) { user(login: $login) {
        createdAt
        repositories(ownerAffiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER]) { totalCount }
    } }''')
    fmt = '%Y-%m-%dT%H:%M:%SZ'
    now = datetime.datetime.now(datetime.timezone.utc)
    a = datetime.datetime.fromisoformat(user['createdAt'])
    fields = []
    while a < now:  # contributionsCollection spans max 1 year per alias
        b = min(a + datetime.timedelta(days=365), now)
        fields.append(f'y{len(fields)}: contributionsCollection(from: "{a.strftime(fmt)}", '
                      f'to: "{b.strftime(fmt)}") {{ totalCommitContributions }}')
        a = b
    years = gql('query($login: String!) { user(login: $login) { ' + ' '.join(fields) + ' } }')
    commits = sum(y['totalCommitContributions'] for y in years.values())
    return user['repositories']['totalCount'], commits


def update_svg(path, contrib, commits):
    tree = etree.parse(path)
    root = tree.getroot()
    c, m = f'{contrib:,}', f'{commits:,}'
    d1 = max(1, LEFT_DOTS - len(c))
    d2 = max(1, RIGHT_DOTS - len(m))
    for el_id, text in (('contrib_data', c), ('contrib_data_dots', f" {'.' * d1} "),
                        ('commit_data', m), ('commit_data_dots', f" {'.' * d2} ")):
        root.find(f".//*[@id='{el_id}']").text = text
    tree.write(path, encoding='utf-8', xml_declaration=True)


def update_readme(contrib, commits):
    with open('README.md', encoding='utf-8') as f:
        text = f.read()
    text = re.sub(r'(dark_mode|light_mode)\.svg(\?v=[\w-]+)?',
                  rf'\1.svg?v={contrib}-{commits}', text)
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(text)


if __name__ == '__main__':
    contrib, commits = get_stats()
    for svg in SVGS:
        update_svg(svg, contrib, commits)
    update_readme(contrib, commits)
    print(f'Contributed: {contrib:,} | Commits: {commits:,}')
