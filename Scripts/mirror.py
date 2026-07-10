import os

MIRROR_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".mirror")

MIRRORS = {
    "None": "",
    "ghfast.top": "https://ghfast.top/",
    "gh-proxy.com": "https://gh-proxy.com/",
    "ghproxy.link": "https://ghproxy.link/",
    "wget.la": "https://wget.la/",
    "gh.llkk.cc": "https://gh.llkk.cc/",
    "gitclone.com": "https://gitclone.com/",
}

_current_mirror = None

def _load_saved_mirror():
    if os.path.exists(MIRROR_FILE):
        try:
            with open(MIRROR_FILE, "r") as f:
                name = f.read().strip()
                if name in MIRRORS:
                    return name
        except:
            pass
    return "None"

def _save_mirror(name):
    try:
        with open(MIRROR_FILE, "w") as f:
            f.write(name)
    except:
        pass

def get_mirror_name():
    global _current_mirror
    if _current_mirror is None:
        _current_mirror = _load_saved_mirror()
    return _current_mirror

def get_mirror_url():
    name = get_mirror_name()
    return MIRRORS.get(name, "")

def set_mirror(name):
    global _current_mirror
    if name in MIRRORS:
        _current_mirror = name
        _save_mirror(name)

def get_available_mirrors():
    return dict(MIRRORS)

def apply_mirror(url):
    mirror_url = get_mirror_url()
    if mirror_url:
        if "github.com" in url or "raw.githubusercontent.com" in url:
            return mirror_url + url
    return url
