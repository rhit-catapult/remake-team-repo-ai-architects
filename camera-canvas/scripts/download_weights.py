"""Fetch + cache pretrained weights into weights/. Usage: python scripts/download_weights.py"""

import os
import sys
import zipfile
import tempfile
import urllib.request

WEIGHTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "weights")

FAST_STYLE_FILES = ["candy.pth", "mosaic.pth", "rain_princess.pth", "udnie.pth"]

FAST_STYLE_ZIP_URLS = [
    "https://www.dropbox.com/s/lrvwfehqdcxoza8/saved_models.zip?dl=1",
    "https://github.com/pytorch/examples/releases/download/v1.0.0/fast_neural_style_saved_models.zip",
]

ADAIN_URLS = {
    "vgg_normalised.pth": [
        "https://github.com/naoto0804/pytorch-AdaIN/releases/download/v0.0.0/vgg_normalised.pth",
    ],
    "decoder.pth": [
        "https://github.com/naoto0804/pytorch-AdaIN/releases/download/v0.0.0/decoder.pth",
    ],
}


def _download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        f.write(r.read())


def _have_all_fast():
    return all(os.path.isfile(os.path.join(WEIGHTS_DIR, f)) for f in FAST_STYLE_FILES)


def fetch_fast_styles():
    if _have_all_fast():
        print("[weights] fast-neural-style: already present")
        return True
    for url in FAST_STYLE_ZIP_URLS:
        try:
            print(f"[weights] fast-neural-style: downloading {url}")
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                tmp_path = tmp.name
            _download(url, tmp_path)
            with zipfile.ZipFile(tmp_path) as z:
                for member in z.namelist():
                    base = os.path.basename(member)
                    if base in FAST_STYLE_FILES:
                        with z.open(member) as src, open(os.path.join(WEIGHTS_DIR, base), "wb") as dst:
                            dst.write(src.read())
            os.remove(tmp_path)
            if _have_all_fast():
                print("[weights] fast-neural-style: OK")
                return True
        except Exception as exc:
            print(f"[weights] fast-neural-style source failed: {exc}")
    print("[weights] fast-neural-style: could not fetch automatically.")
    print("           Get them from the pytorch/examples fast_neural_style repo "
          "and drop candy/mosaic/rain_princess/udnie .pth into weights/.")
    return False


def fetch_adain():
    ok = True
    for fname, urls in ADAIN_URLS.items():
        dest = os.path.join(WEIGHTS_DIR, fname)
        if os.path.isfile(dest):
            print(f"[weights] {fname}: already present")
            continue
        got = False
        for url in urls:
            try:
                print(f"[weights] {fname}: downloading {url}")
                _download(url, dest)
                got = True
                break
            except Exception as exc:
                print(f"[weights] {fname} source failed: {exc}")
        if not got:
            ok = False
            print(f"[weights] {fname}: could not fetch automatically.")
    if not ok:
        print("[weights] AdaIN weights missing. Download vgg_normalised.pth and "
              "decoder.pth from the naoto0804/pytorch-AdaIN project and place them "
              "in weights/. The app still runs (CV + fast styles) without them.")
    return ok


def main():
    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    fast_ok = fetch_fast_styles()
    adain_ok = fetch_adain()
    print(f"\n[weights] summary: fast-style={'ok' if fast_ok else 'missing'} "
          f"adain={'ok' if adain_ok else 'missing'}")
    return 0 if (fast_ok or adain_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
