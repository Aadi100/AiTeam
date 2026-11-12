"""
PC control policy: which paths Adion may touch, and when it must ask.

Rules (decided with the owner):
  * Only the Desktop is open by default.
  * Any other folder needs a permission prompt: "Allow once" or "Always allow this folder".
  * Some places are never allowed, whatever anyone says (keys, passwords, browser profiles, Windows itself).

check_path(path, write, granted) -> {status: allow|ask|deny, real, root, reason}
"""

import os
import fnmatch
import uuid
import ctypes

try:
    from ctypes import wintypes
except ValueError:  # non-Windows
    wintypes = None

_FOLDER_IDS = {
    'desktop': '{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}',
    'documents': '{FDD39AD0-238F-46AF-ADB4-6C85480369C7}',
    'downloads': '{374DE290-123F-4565-9164-39C4925E467B}',
    'pictures': '{33E28130-4E1E-4676-835A-98395C3BC3BB}',
    'music': '{4BD8D571-6D19-48D3-BE97-422220080E43}',
    'videos': '{18989B1D-99B5-48AC-AC57-B6F3D63B9FF9}',
}
KNOWN = tuple(_FOLDER_IDS)


def _win_known_folder(guid_str):
    class GUID(ctypes.Structure):
        _fields_ = [('Data1', wintypes.DWORD), ('Data2', wintypes.WORD), ('Data3', wintypes.WORD), ('Data4', ctypes.c_ubyte * 8)]
    u = uuid.UUID(guid_str)
    guid = GUID(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8).from_buffer_copy(u.bytes[8:]))
    out = ctypes.c_wchar_p()
    if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(out)):
        return None
    value = out.value
    ctypes.windll.ole32.CoTaskMemFree(out)
    return value


def known_folder(name):
    """Real location of Desktop/Documents/... (follows OneDrive redirection). ADION_PC_<NAME> overrides (tests)."""
    name = name.lower()
    override = os.getenv('ADION_PC_' + name.upper())
    if override:
        return os.path.realpath(override)
    if os.name == 'nt' and name in _FOLDER_IDS:
        try:
            p = _win_known_folder(_FOLDER_IDS[name])
            if p:
                return os.path.realpath(p)
        except Exception:  # noqa: BLE001
            pass
    return os.path.realpath(os.path.join(os.path.expanduser('~'), name.capitalize()))


def home():
    return os.path.realpath(os.getenv('ADION_PC_HOME') or os.path.expanduser('~'))


ALIASES = {'desktop': 'desktop', 'my desktop': 'desktop', 'documents': 'documents', 'my documents': 'documents',
           'downloads': 'downloads', 'my downloads': 'downloads', 'pictures': 'pictures', 'my pictures': 'pictures',
           'photos': 'pictures', 'music': 'music', 'videos': 'videos', 'home': 'home'}


def resolve(path):
    """'~/x', '%USERPROFILE%\\x', 'Desktop', 'downloads/invoices' -> absolute real path (not checked yet)."""
    p = os.path.expandvars(os.path.expanduser(str(path or '').strip().strip('"')))
    first, _, rest = p.replace('\\', '/').partition('/')
    key = first.lower()
    if key in ALIASES and not os.path.isabs(p):
        base = home() if ALIASES[key] == 'home' else known_folder(ALIASES[key])
        p = os.path.join(base, rest) if rest else base
    elif not os.path.isabs(p):
        p = os.path.join(known_folder('desktop'), p)           # a bare name means "on the Desktop"
    return os.path.realpath(p)


# ── never-allowed places ──
SENSITIVE_DIRS = {'.ssh', '.gnupg', '.aws', '.azure', '.kube', '.gcloud'}
SENSITIVE_FILES = ['.env', '.env.*', '*.pem', '*.pfx', '*.p12', '*.key', '*.kdbx', 'id_rsa*', 'id_ed25519*', 'id_ecdsa*',
                   '.auth.json', 'login data*', 'cookies', 'web data', 'ntuser.dat*', '.npmrc', '.pypirc', '.netrc']
SENSITIVE_FRAGMENTS = ['\\google\\chrome\\user data', '\\microsoft\\edge\\user data', '\\mozilla\\firefox\\profiles',
                       '\\brave-browser\\user data', '\\microsoft\\credentials', '\\microsoft\\protect', '\\microsoft\\vault']
BLOCKED_NEW_EXT = {'.exe', '.dll', '.bat', '.cmd', '.ps1', '.msi', '.vbs', '.scr', '.com', '.lnk', '.reg', '.jar'}
EXEC_EXT = BLOCKED_NEW_EXT | {'.js', '.jse', '.wsf', '.hta', '.py', '.sh', '.appx', '.msix'}


def _system_roots():
    roots = [os.getenv('SystemRoot') or r'C:\Windows']
    for v in ('ProgramFiles', 'ProgramFiles(x86)', 'ProgramData'):
        if os.getenv(v):
            roots.append(os.getenv(v))
    return [os.path.realpath(r) for r in roots]


def _inside(path, root):
    try:
        return os.path.commonpath([os.path.normcase(path), os.path.normcase(root)]) == os.path.normcase(root)
    except ValueError:   # different drives
        return False


def blocked_reason(real, write):
    low = os.path.normcase(real)
    parts = set(low.replace('/', '\\').split('\\'))
    if parts & SENSITIVE_DIRS:
        return 'it is a secrets folder (keys or credentials)'
    base = os.path.basename(low)
    if any(fnmatch.fnmatch(base, pat) for pat in SENSITIVE_FILES):
        return 'it looks like a secret (key, password or token file)'
    if any(f in low for f in SENSITIVE_FRAGMENTS):
        return 'it holds browser or Windows credentials'
    sysroots = _system_roots()
    if _inside(real, sysroots[0]):
        return 'it is the Windows system folder'
    if write and any(_inside(real, r) for r in sysroots[1:]):
        return 'program files cannot be changed'
    if write and os.path.dirname(real) == real:
        return 'a drive root cannot be changed'
    return ''


# ── settings (per user, stored in the database) ──
def get_settings(owner):
    from models import PcSettingsDocument
    s = PcSettingsDocument.objects(owner=owner).first()
    if not s:
        s = PcSettingsDocument(owner=owner).save()
    return s


def allowed_roots(owner):
    s = get_settings(owner)
    return [known_folder('desktop')] + [os.path.realpath(f) for f in s.folders]


def grant_root(real):
    """The folder a permission prompt should ask about for this path."""
    for name in KNOWN:
        kf = known_folder(name)
        if _inside(real, kf):
            return kf
    h = home()
    if _inside(real, h):
        parts = os.path.relpath(real, h).split(os.sep)
        return os.path.join(h, parts[0])
    return real if os.path.isdir(real) else os.path.dirname(real)


def check_path(owner, path, write=False, granted=()):
    """Decide what to do about one path. status: allow | ask (needs the user's permission for `root`) | deny."""
    real = resolve(path)
    why = blocked_reason(real, write)
    if why:
        return {'status': 'deny', 'real': real, 'reason': f'Blocked: {why}.'}
    for root in list(allowed_roots(owner)) + [os.path.realpath(g) for g in granted]:
        if _inside(real, root):
            return {'status': 'allow', 'real': real, 'root': root}
    return {'status': 'ask', 'real': real, 'root': grant_root(real),
            'reason': f'{grant_root(real)} is outside the folders you allowed.'}
