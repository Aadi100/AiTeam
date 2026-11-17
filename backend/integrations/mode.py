"""How people connect their apps. The owner picks ONE way for everyone, so the Apps tab never shows two sets of buttons:
  direct = the Connect buttons (Google, GitHub, Slack... each person signs in to each service; free, full access)
  zapier = tool servers (each person adds their own Zapier / MCP link; one link covers thousands of apps)
Switching keeps everything people already connected; it is just not used while the other way is selected."""

import os
from models import UserDocument

MODES = ('direct', 'zapier')


def get():
    for row in UserDocument.objects(role='admin'):
        if row.connect_mode in MODES:
            return row.connect_mode
    m = os.getenv('ADION_CONNECT_MODE', 'direct')
    return m if m in MODES else 'direct'


def set_mode(m):
    if m not in MODES:
        raise ValueError('mode must be direct or zapier')
    UserDocument.objects(role='admin').update(set__connect_mode=m)
