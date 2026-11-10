"""Check the links, asset hrefs and provider URLs of every collection in the live STAC API.

Exits 1 only for links that look dead (404, 410, other errors, DNS failures, timeouts).
Sites that block automated requests (401, 403, 405, 429) or send an incomplete
certificate chain still work in a browser, so they are listed as warnings instead.

Usage: python3 scripts/check_links.py  (set STAC_API_URL to check another API)
"""

import json
import os
import ssl
import sys
import urllib.error
import urllib.request

API_URL = os.environ.get("STAC_API_URL", "https://stac.cal-adapt.org")

# Auto-generated API links that point back to the API itself
SKIP_RELS = {"self", "root", "items", "collection", "parent"}

# Statuses from sites that refuse scripted requests but serve browsers
BLOCKED_STATUSES = {401, 403, 405, 429}


def check_url(url):
    """Return ("ok" | "warning" | "failure", detail)."""
    request = urllib.request.Request(url, headers={"User-Agent": "caladapt-link-checker/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return "ok", str(response.status)
    except urllib.error.HTTPError as e:
        if e.code in BLOCKED_STATUSES:
            return "warning", f"{e.code}, blocks automated requests"
        return "failure", str(e.code)
    except urllib.error.URLError as e:
        if isinstance(e.reason, ssl.SSLCertVerificationError):
            return "warning", "certificate chain not verifiable outside a browser"
        return "failure", f"ERROR {e.reason}"
    except Exception as e:
        return "failure", f"ERROR {e}"


def collection_urls(collection):
    """Yield (url, label) for every link, asset and provider URL to check."""
    col_id = collection["id"]
    for link in collection.get("links", []):
        if link.get("rel") not in SKIP_RELS:
            yield link["href"], f"{col_id} link[rel={link.get('rel')}]"
    for key, asset in collection.get("assets", {}).items():
        yield asset["href"], f"{col_id} asset[{key}]"
    for provider in collection.get("providers", []):
        if url := provider.get("url"):
            yield url, f"{col_id} provider[{provider.get('name')}]"


def main():
    with urllib.request.urlopen(f"{API_URL}/collections?limit=100") as response:
        collections = json.load(response)["collections"]

    results = {"ok": [], "warning": [], "failure": []}
    for collection in collections:
        for url, label in collection_urls(collection):
            level, detail = check_url(url)
            results[level].append(f"  {detail}  {url}  ({label})")
            if level == "ok":
                print(f"  ✓ {detail} {url}")

    if results["warning"]:
        print(f"\n⚠️  {len(results['warning'])} link(s) could not be checked automatically (check in a browser):")
        print("\n".join(results["warning"]))

    if results["failure"]:
        print(f"\n❌ {len(results['failure'])} broken link(s) found:")
        print("\n".join(results["failure"]))
        sys.exit(1)

    checked = sum(len(v) for v in results.values())
    print(f"\n✅ No broken links among {checked} checked")


if __name__ == "__main__":
    main()
