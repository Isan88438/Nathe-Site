#!/usr/bin/env python3
"""Build Nathe's periodically refreshed, static public-web research index."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
import urllib.robotparser

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / "research-index.json"
DEFAULT_SEEDS = ROOT / "research-seeds.txt"
USER_AGENT = "NatheResearchBot/1.0"
MAX_BODY_BYTES = 1_200_000
MAX_TEXT_CHARS = 1_500
MAX_PAGES_PER_RUN = 24
MAX_INDEX_PAGES = 500
MAX_FRONTIER = 5_000
MAX_CRAWLED = 6_000
REQUEST_TIMEOUT = 8
REDIRECT_LIMIT = 5
TOKEN_RE = re.compile(r"[a-z0-9]{2,}", re.I)
HIDDEN_TAGS = {
    "script", "style", "noscript", "svg", "canvas", "iframe", "form",
    "nav", "footer", "aside", "template", "button", "select", "textarea"
}
BOUNDARY_TAGS = {
    "p", "div", "article", "section", "main", "h1", "h2", "h3", "h4",
    "h5", "li", "br", "tr", "blockquote"
}
SKIP_EXTENSIONS = (
    ".pdf", ".zip", ".gz", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".svg", ".mp3", ".mp4", ".mov", ".avi", ".exe", ".dmg", ".apk",
    ".woff", ".woff2", ".css", ".js"
)


class ResearchError(Exception):
    """Expected failure while retrieving a public source."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def words(value: str) -> list[str]:
    return list(dict.fromkeys(TOKEN_RE.findall((value or "").lower())))


def is_public_ip(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


def normalise_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise ResearchError("URL is missing or too long.")
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ResearchError("Only public HTTPS pages can be indexed.")
    if parsed.username or parsed.password:
        raise ResearchError("URLs containing credentials are blocked.")
    try:
        port = parsed.port
    except ValueError as error:
        raise ResearchError("The URL port is invalid.") from error
    if port not in (None, 443):
        raise ResearchError("Only standard HTTPS websites are supported.")
    host = parsed.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ResearchError("Local and private network hosts are blocked.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ResearchError("Private or reserved IP addresses are blocked.")
    return urlunsplit(("https", host, parsed.path or "/", parsed.query, ""))


def fetch_public_page(value: str) -> dict:
    """Fetch one public HTTPS page while validating DNS results and redirects."""
    current = normalise_url(value)
    context = ssl.create_default_context()
    for _ in range(REDIRECT_LIMIT + 1):
        parsed = urlsplit(current)
        host, port = parsed.hostname, parsed.port or 443
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        try:
            addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as error:
            raise ResearchError("DNS lookup failed.") from error
        public_addresses = []
        for item in addresses:
            address = item[4][0]
            if not is_public_ip(address):
                raise ResearchError("The host resolved to a private or reserved IP address.")
            if address not in public_addresses:
                public_addresses.append(address)
        if not public_addresses:
            raise ResearchError("No public IP address was found.")

        raw_socket = None
        tls_socket = None
        try:
            raw_socket = socket.create_connection(
                (public_addresses[0], port), timeout=REQUEST_TIMEOUT
            )
            if not is_public_ip(raw_socket.getpeername()[0]):
                raise ResearchError("The connection reached a non-public IP address.")
            tls_socket = context.wrap_socket(raw_socket, server_hostname=host)
            raw_socket = None
            request = (
                f"GET {target} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"User-Agent: {USER_AGENT}\r\n"
                "Accept: text/html, application/xhtml+xml;q=0.9, text/plain;q=0.7\r\n"
                "Accept-Encoding: identity\r\n"
                "Connection: close\r\n\r\n"
            )
            tls_socket.sendall(request.encode("ascii", errors="strict"))
            response = http.client.HTTPResponse(tls_socket)
            response.begin()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                response.close()
                tls_socket.close()
                tls_socket = None
                if not location:
                    raise ResearchError("The website returned an invalid redirect.")
                current = normalise_url(urljoin(current, location))
                continue
            if response.status != 200:
                status = response.status
                response.close()
                tls_socket.close()
                tls_socket = None
                raise ResearchError(f"HTTP {status}")
            content_type = response.getheader("Content-Type", "").lower()
            if not any(kind in content_type for kind in (
                "text/html", "application/xhtml+xml", "text/plain"
            )):
                response.close()
                tls_socket.close()
                tls_socket = None
                raise ResearchError("The response is not HTML or plain text.")
            body = response.read(MAX_BODY_BYTES + 1)
            modified = response.getheader("Last-Modified", "")
            response.close()
            tls_socket.close()
            tls_socket = None
            if len(body) > MAX_BODY_BYTES:
                raise ResearchError("The page exceeds the crawl size limit.")
            charset = re.search(r"charset\s*=\s*['\"]?([^;'\"\s]+)", content_type)
            try:
                text = body.decode(charset.group(1) if charset else "utf-8", errors="replace")
            except LookupError:
                text = body.decode("utf-8", errors="replace")
            return {
                "url": current, "content_type": content_type,
                "text": text, "last_modified": modified
            }
        except (OSError, ssl.SSLError, http.client.HTTPException) as error:
            raise ResearchError("The public page could not be retrieved securely.") from error
        finally:
            for connection in (tls_socket, raw_socket):
                if connection is not None:
                    try:
                        connection.close()
                    except OSError:
                        pass
    raise ResearchError("The website redirected too many times.")


class PageExtractor(HTMLParser):
    """Extract visible text and links; page code and executable content are ignored."""
    def __init__(self, page_url: str):
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.title_parts = []
        self.meta_title = ""
        self.published_at = ""
        self.paragraph_parts = []
        self.paragraphs = []
        self.links = []
        self.hidden_depth = 0
        self.in_title = False
        self.active_link = None

    def flush_paragraph(self):
        value = " ".join(" ".join(self.paragraph_parts).split()).strip()
        if len(value) >= 30 and (not self.paragraphs or value != self.paragraphs[-1]):
            self.paragraphs.append(value)
        self.paragraph_parts.clear()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag in HIDDEN_TAGS:
            self.hidden_depth += 1
        if tag in BOUNDARY_TAGS:
            self.flush_paragraph()
        if tag == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            value = (values.get("content") or "").strip()
            if key in ("og:title", "twitter:title") and value:
                self.meta_title = value[:240]
            if key in ("article:published_time", "date", "datepublished",
                       "dc.date", "pubdate") and value and not self.published_at:
                self.published_at = value[:100]
        if tag == "a" and values.get("href") and len(self.links) < 60:
            try:
                target = normalise_url(urljoin(self.page_url, values["href"]))
            except (ResearchError, ValueError):
                self.active_link = None
            else:
                if not urlsplit(target).path.lower().endswith(SKIP_EXTENSIONS):
                    self.links.append({"url": target, "text": ""})
                    self.active_link = len(self.links) - 1
                else:
                    self.active_link = None

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in HIDDEN_TAGS:
            self.hidden_depth = max(0, self.hidden_depth - 1)
        if tag == "a":
            self.active_link = None
        if tag in BOUNDARY_TAGS:
            self.flush_paragraph()

    def handle_data(self, data):
        value = " ".join(data.split())
        if not value:
            return
        if self.in_title:
            self.title_parts.append(value)
            return
        if self.hidden_depth:
            return
        self.paragraph_parts.append(value)
        if self.active_link is not None:
            link = self.links[self.active_link]
            link["text"] = (link["text"] + " " + value).strip()[:180]

    def finish(self):
        self.flush_paragraph()
        title = " ".join(" ".join(self.title_parts).split()).strip()
        title = title or self.meta_title or (urlsplit(self.page_url).hostname or "Web page")
        content = "\n\n".join(self.paragraphs)
        return {
            "title": title[:240],
            "text": content[:MAX_TEXT_CHARS],
            "snippet": self.paragraphs[0][:360] if self.paragraphs else "",
            "published_at": self.published_at,
            "links": self.links,
        }


class RobotsCache:
    def __init__(self):
        self.parsers = {}

    def allowed(self, url):
        parsed = urlsplit(url)
        origin = f"https://{parsed.netloc}"
        if origin not in self.parsers:
            try:
                result = fetch_public_page(origin + "/robots.txt")
                parser = urllib.robotparser.RobotFileParser()
                parser.set_url(origin + "/robots.txt")
                parser.parse(result["text"].splitlines())
                self.parsers[origin] = parser
            except ResearchError as error:
                # A 404 means no published robots file; other failures fail closed.
                self.parsers[origin] = None if "HTTP 404" in str(error) else False
        parser = self.parsers[origin]
        return parser is None or (parser is not False and parser.can_fetch(USER_AGENT, url))


def empty_state():
    return {"version": 1, "generated_at": None, "pages": [], "frontier": [], "crawled": {}}


def load_state(path: Path):
    if not path.exists():
        return empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_state()
    if not isinstance(data, dict) or data.get("version") != 1:
        return empty_state()
    if not isinstance(data.get("pages"), list):
        data["pages"] = []
    if not isinstance(data.get("frontier"), list):
        data["frontier"] = []
    if not isinstance(data.get("crawled"), dict):
        data["crawled"] = {}
    return data


def topic_score(topic, link_text, url):
    topic_words = set(words(topic))
    link_words = set(words(link_text + " " + url))
    return float(sum(2 for term in topic_words if term in link_words))


class ResearchIndexer:
    def __init__(self, state):
        self.state = state
        self.pages = {
            page.get("url"): page for page in state["pages"]
            if isinstance(page, dict) and page.get("url")
        }
        self.frontier = state["frontier"]
        self.crawled = state["crawled"]
        self.robots = RobotsCache()
        self.last_host_fetch = {}

    def add_frontier(self, url, topic, depth, priority):
        try:
            url = normalise_url(url)
        except ResearchError:
            return
        if url in self.pages or url in self.crawled:
            return
        if any(item.get("url") == url for item in self.frontier):
            return
        self.frontier.append({
            "url": url, "topic": str(topic)[:100], "depth": int(depth),
            "priority": float(priority), "added": time.time()
        })

    def load_seeds(self, path: Path):
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "|" not in line:
                continue
            topic, url = line.split("|", 1)
            self.add_frontier(url.strip(), topic.strip(), 0, -1.0)

    def fetch_and_index(self, item):
        url = normalise_url(item["url"])
        host = urlsplit(url).hostname or ""
        delay = 0.5 - (time.monotonic() - self.last_host_fetch.get(host, 0.0))
        if delay > 0:
            time.sleep(delay)
        self.last_host_fetch[host] = time.monotonic()
        if not self.robots.allowed(url):
            raise ResearchError("robots.txt does not allow this crawl.")

        response = fetch_public_page(url)
        if "text/plain" in response["content_type"]:
            text = " ".join(response["text"].split())[:MAX_TEXT_CHARS]
            page = {
                "title": host, "text": text, "snippet": text[:360],
                "published_at": response["last_modified"], "links": []
            }
        else:
            parser = PageExtractor(response["url"])
            parser.feed(response["text"])
            page = parser.finish()
            if not page["published_at"]:
                page["published_at"] = response["last_modified"]

        if len(page["text"]) < 40:
            raise ResearchError("The page did not contain enough readable text.")

        record = {
            "url": response["url"],
            "host": urlsplit(response["url"]).hostname or "",
            "title": page["title"],
            "text": page["text"][:MAX_TEXT_CHARS],
            "snippet": page["snippet"][:360],
            "published_at": page["published_at"][:100],
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "topic": item.get("topic", "")[:100],
        }
        self.pages[record["url"]] = record
        for link in page.get("links", []):
            self.add_frontier(
                link["url"], item.get("topic", ""),
                int(item.get("depth", 0)) + 1,
                topic_score(item.get("topic", ""), link.get("text", ""), link["url"])
            )

    def run(self, max_pages):
        processed = 0
        host_counts = {}
        while self.frontier and processed < max(1, min(max_pages, MAX_PAGES_PER_RUN)):
            self.frontier.sort(
                key=lambda item: (float(item.get("priority", 0)), -float(item.get("added", 0))),
                reverse=True,
            )
            item = self.frontier.pop(0)
            try:
                url = normalise_url(item.get("url", ""))
            except ResearchError:
                continue
            if url in self.crawled:
                continue
            if int(item.get("depth", 0)) > 4:
                self.crawled[url] = utc_now()
                continue
            host = urlsplit(url).hostname or ""
            if host_counts.get(host, 0) >= 3:
                self.crawled[url] = utc_now()
                continue
            self.crawled[url] = utc_now()
            try:
                self.fetch_and_index(item)
            except ResearchError:
                continue
            processed += 1
            host_counts[host] = host_counts.get(host, 0) + 1

        self.state["pages"] = sorted(
            self.pages.values(), key=lambda page: page.get("fetched_at", ""), reverse=True
        )[:MAX_INDEX_PAGES]
        self.state["frontier"] = self.frontier[:MAX_FRONTIER]
        self.state["crawled"] = dict(
            sorted(self.crawled.items(), key=lambda item: item[1], reverse=True)[:MAX_CRAWLED]
        )
        self.state["generated_at"] = utc_now()
        self.state["page_count"] = len(self.state["pages"])
        return processed


def build_index(state_path: Path, seeds_path: Path, max_pages: int) -> int:
    state = load_state(state_path)
    indexer = ResearchIndexer(state)
    indexer.load_seeds(seeds_path)
    processed = indexer.run(max_pages)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return processed


def main():
    parser = argparse.ArgumentParser(description="Refresh Nathe's static web research index.")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--seeds", type=Path, default=DEFAULT_SEEDS)
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES_PER_RUN)
    args = parser.parse_args()
    count = build_index(args.state, args.seeds, args.max_pages)
    state = load_state(args.state)
    print(
        f"Nathe index updated: {count} new pages this run; "
        f"{len(state['pages'])} searchable pages; {len(state['frontier'])} queued links."
    )


if __name__ == "__main__":
    main()
