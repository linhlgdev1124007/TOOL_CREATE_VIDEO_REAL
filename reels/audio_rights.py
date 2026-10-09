"""Supported recording licenses; a provider name alone never grants rights."""
from urllib.parse import urlparse

CC = {"CC0-1.0", "CC-BY-3.0", "CC-BY-4.0"}
SUPPORTED = CC | {"Mixkit-SFX-Free", "Pixabay-Content"}


def host_is(url, domain):
    u = urlparse(url)
    return u.scheme == "https" and (u.hostname == domain or (u.hostname or "").endswith("."+domain))


def validate_rights(item):
    license = item.get("license")
    if license not in SUPPORTED:
        raise ValueError("Unsupported/unverified recording license; no automatic download")
    if license.startswith("CC-BY-") and not item.get("attribution"):
        raise ValueError("CC-BY requires attribution")
    if license == "Mixkit-SFX-Free":
        if item.get("kind") != "sfx" or not host_is(item.get("source_url", ""), "mixkit.co"):
            raise ValueError("Mixkit SFX license cannot be applied to other sources or music")
        if item.get("license_url") != "https://mixkit.co/license/modal/sfxFree/":
            raise ValueError("Use the exact Mixkit SFX license")
        if not host_is(item.get("download_url", ""), "assets.mixkit.co"):
            raise ValueError("Mixkit download must come from the official asset host")
    if license == "Pixabay-Content":
        if not all(host_is(item.get(key, ""), "pixabay.com") for key in ("source_url", "download_url", "license_url")):
            raise ValueError("Pixabay license needs official provenance and download hosts")
        if urlparse(item["license_url"]).path not in ("/service/license-summary/", "/service/terms/"):
            raise ValueError("Missing Pixabay license/terms page")
    if license not in CC and item.get("usage") != "facebook-commercial-video":
        raise ValueError("Provider license must be reviewed for the target commercial video use")
