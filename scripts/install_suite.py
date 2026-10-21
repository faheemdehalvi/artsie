#!/usr/bin/env python3
"""Fetch pinned official releases, verify assets, and install inside ARTsie."""
import concurrent.futures as futures
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
APPS = [
    ('photocraft', 'PhotoCraft', 'Image editing', 'Pc', '#9ba8ff'),
    ('vectorcraft', 'VectorCraft', 'Vector illustration', 'Vc', '#ffa780'),
    ('filmcraft', 'FilmCraft', 'Video editing', 'Fc', '#c9a1ff'),
    ('lightcraft', 'LightCraft', 'Photography & RAW', 'Lc', '#ffcf7c'),
    ('pdfcraft', 'PdfCraft', 'PDF workbench', 'Pd', '#ff8e9f'),
    ('effectcraft', 'EffectCraft', 'Motion & visual effects', 'Ec', '#d5a0fb'),
    ('designcraft', 'DesignCraft', 'Page layout & publishing', 'Dc', '#f6a9cf'),
    ('figcraft', 'FigCraft', 'Interface design', 'Fg', '#a1d9cb'),
    ('wordcraft', 'WordCraft', 'Documents', 'Wc', '#9fc9ff'),
    ('soundcraft', 'SoundCraft', 'Audio recording & mixing', 'Sc', '#aad58d'),
    ('deckcraft', 'DeckCraft', 'Presentations', 'Dc', '#f2bc8f'),
    ('cadcraft', 'CADCraft', 'CAD & drafting', 'Cc', '#8fd7e5'),
    ('gridcraft', 'GridCraft', 'Spreadsheets & data', 'Gc', '#a0d6aa'),
    ('craft-launcher', 'ArtCraft Launcher', 'Official release manager', 'Ac', '#e3e5ed'),
]

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'ARTsie-local-setup'})
    return urllib.request.urlopen(req, timeout=120)

def download(url, path):
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.part')
    with fetch(url) as src, temp.open('wb') as dst:
        shutil.copyfileobj(src, dst)
    temp.replace(path)
    return path

def prepare(app):
    slug, name, category, monogram, color = app
    meta = ROOT / 'downloads' / slug / 'release.json'
    if meta.exists():
        release = json.loads(meta.read_text())
    else:
        release = json.load(fetch(f'https://api.github.com/repos/storytold/{slug}/releases/latest'))
        meta.parent.mkdir(parents=True, exist_ok=True)
        meta.write_text(json.dumps(release, indent=2))
    assets = release['assets']
    sums_asset = next(x for x in assets if x['name'] == 'SHA256SUMS.txt')
    sums_path = download(sums_asset['browser_download_url'], meta.parent / sums_asset['name'])
    sums = {}
    for line in sums_path.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2:
            sums[parts[1].lstrip('*')] = parts[0]
    selected = [x for x in assets if 'macos-universal' in x['name'] and x['name'].endswith(('.zip', '.dmg'))]
    verified = []
    for asset in selected:
        path = download(asset['browser_download_url'], meta.parent / asset['name'])
        digest = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
        if digest != sums.get(asset['name']):
            raise RuntimeError(f'Checksum mismatch: {path}')
        verified.append({'name': asset['name'], 'sha256': digest, 'url': asset['browser_download_url']})
        if path.suffix == '.zip':
            dest = ROOT / 'tools' / slug
            dest.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    target = (dest / member.filename).resolve()
                    if not target.is_relative_to(dest.resolve()):
                        raise ValueError('Unsafe archive path')
                archive.extractall(dest)
            for binary in dest.rglob(slug + '-cli'):
                binary.chmod(0o755)
                link = ROOT / 'bin' / (slug + '-cli')
                link.parent.mkdir(exist_ok=True)
                if not link.exists():
                    link.symlink_to(binary.relative_to(ROOT / 'bin', walk_up=True))
    # Source snapshot matches the downloaded binary release, including licenses.
    source = ROOT / 'sources' / slug
    if not source.exists():
        archive_path = download(f'https://codeload.github.com/storytold/{slug}/tar.gz/refs/tags/{release["tag_name"]}', meta.parent / 'source.tar.gz')
        staging = ROOT / 'sources' / (slug + '.staging')
        staging.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path) as archive:
            archive.extractall(staging, filter='data')
        top = next(staging.iterdir())
        top.rename(source)
        staging.rmdir()
    print(f'Verified downloads + source: {name} {release["tag_name"]}', flush=True)
    return dict(id=slug, name=name, category=category, monogram=monogram, color=color,
                version=release['tag_name'], release=release['html_url'], assets=verified,
                source=str(source.relative_to(ROOT)))

def install(record):
    slug = record['id']
    dmg = next((ROOT / 'downloads' / slug).glob('*.dmg'))
    mount = ROOT / '.mounts' / slug
    mount.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(['hdiutil', 'attach', str(dmg), '-nobrowse', '-readonly', '-mountpoint', str(mount)], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    try:
        bundle = next(mount.glob('*.app'))
        dest = ROOT / 'Applications' / bundle.name
        if not dest.exists():
            subprocess.run(['ditto', str(bundle), str(dest)], check=True)
        # Finder/File Provider can add non-code metadata while copying onto Desktop.
        # Remove only that detritus, retaining the vendor signature and quarantine.
        for attr in ('com.apple.FinderInfo','com.apple.ResourceFork'):
            subprocess.run(['xattr','-dr',attr,str(dest)],capture_output=True)
        # Verify on a clean local staging volume: iCloud Desktop immediately adds
        # an empty FinderInfo attribute that --strict rejects, even after removal.
        with tempfile.TemporaryDirectory(prefix='artsie-verify-') as temporary:
            clean = Path(temporary) / dest.name
            subprocess.run(['ditto','--norsrc','--noextattr',str(dest),str(clean)],check=True)
            subprocess.run(['codesign','--verify','--deep','--strict',str(clean)],check=True,capture_output=True)
        info = plistlib.loads((dest / 'Contents/Info.plist').read_bytes())
        record['bundle'] = str(dest.relative_to(ROOT))
        record['executable'] = str((dest / 'Contents/MacOS' / info['CFBundleExecutable']).relative_to(ROOT))
    finally:
        subprocess.run(['hdiutil', 'detach', str(mount)], capture_output=True)
    print(f'Installed: {record["name"]}', flush=True)
    return record

def main():
    for directory in ['Applications', 'bin', 'config', 'data', 'logs', 'workspace/Inbox', 'workspace/Projects', 'workspace/Exports']:
        (ROOT / directory).mkdir(parents=True, exist_ok=True)
    records = []
    with futures.ThreadPoolExecutor(max_workers=4) as pool:
        for record in pool.map(prepare, APPS):
            records.append(record)
    for record in records:
        install(record)
    catalog = {'fetched_at': datetime.now(timezone.utc).isoformat(), 'source': 'https://getartcraft.com/apps', 'apps': records}
    (ROOT / 'config/catalog.json').write_text(json.dumps(catalog, indent=2))
    print('ARTsie suite installed.', flush=True)

if __name__ == '__main__':
    main()
