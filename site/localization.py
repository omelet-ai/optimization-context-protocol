"""Static Korean counterparts: translate prose, preserve executable content.

URLs carry the language choice, so navigation works without scripts or storage.
Missing translations fail the public build instead of publishing mixed prose.
"""
from html import escape
from html.parser import HTMLParser
import json
import posixpath
import re
from urllib.parse import urljoin, urlsplit, urlunsplit


def language_switch(name):
    korean = name.startswith("ko/")
    english = name.removeprefix("ko/")
    prefix = posixpath.dirname(name) or "."
    links = []
    for lang, target, label, title in (
        ("en", english, "EN", "Read this page in English"),
        ("ko", "ko/" + english, "한국어", "이 페이지를 한국어로 보기"),
    ):
        active = ' aria-current="page"' if (lang == "ko") == korean else ""
        href = posixpath.relpath(target, prefix)
        links.append(f'<a href="{href}" lang="{lang}" hreflang="{lang}" data-language-link aria-label="{title}"{active}>{label}</a>')
    return '<div class="language-switch" role="group" aria-label="' + ("언어 선택" if korean else "Language") + '">' + ''.join(links) + '</div>'


class KoreanPage(HTMLParser):
    def __init__(self, name, routes, translations):
        super().__init__(convert_charrefs=True)
        self.name = name
        self.routes = set(routes)
        self.translations = translations
        self.parts = []
        self.literal = 0
        self.language_link = False
        self.example_data = False

    def translate(self, value):
        key = value.strip()
        if not key or not re.search('[A-Za-z]', key):
            return value
        if key in self.translations:
            result = self.translations[key]
        elif key.startswith('Copy '):
            result = self.translate(key[5:]) + ' 복사'
        elif key.endswith(' · OCP'):
            result = self.translate(key[:-6]) + ' · OCP'
        elif key.endswith(' · Optimization Context Protocol'):
            result = self.translate(key.removesuffix(' · Optimization Context Protocol')) + ' · Optimization Context Protocol'
        else:
            try:
                result = self.translations[key]
            except KeyError:
                raise ValueError(f'Missing Korean translation in {self.name}: {key}') from None
        return value[:len(value) - len(value.lstrip())] + result + value[len(value.rstrip()):]

    def local_url(self, value):
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return value
        resolved = urlsplit(urljoin('https://local.invalid/' + self.name, value))
        path = resolved.path.lstrip('/')
        if path in self.routes:
            path = 'ko/' + path
        relative = posixpath.relpath(path, posixpath.dirname('ko/' + self.name))
        return urlunsplit(('', '', relative, parsed.query, parsed.fragment))

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        switch = 'data-language-link' in values
        if tag in ('pre', 'code', 'script'):
            self.literal += 1
        if tag == 'script' and values.get('id') == 'example-data':
            self.example_data = True
        if switch:
            self.language_link = True
        out = []
        for key, value in attrs:
            if value is None:
                out.append(key)
                continue
            if key in ('href', 'src') and not switch:
                value = self.local_url(value)
            elif key in ('aria-label', 'title', 'alt') and not switch:
                value = self.translate(value)
            elif tag == 'html' and key == 'lang':
                value = 'ko'
            elif tag == 'meta' and key == 'content' and (values.get('name') == 'description' or values.get('property') in ('og:title', 'og:description')):
                value = self.translate(value)
            out.append(f'{key}="{escape(value, quote=True)}"')
        self.parts.append('<' + tag + (' ' + ' '.join(out) if out else '') + '>')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.parts[-1] = self.parts[-1][:-1] + '/>'

    def handle_endtag(self, tag):
        if tag in ('pre', 'code', 'script'):
            self.literal -= 1
        if tag == 'script':
            self.example_data = False
        if tag == 'a':
            self.language_link = False
        self.parts.append('</' + tag + '>')

    def handle_data(self, data):
        if self.example_data:
            payload = json.loads(data)
            for scenario in payload.values():
                if isinstance(scenario, dict) and 'summary' in scenario:
                    scenario['summary'] = self.translate(scenario['summary'])
            self.parts.append(json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c'))
        elif self.literal or self.language_link:
            # The example script is handled above; other literal blocks are code.
            self.parts.append(escape(data, quote=False))
        else:
            self.parts.append(escape(self.translate(data), quote=False))

    def handle_decl(self, decl):
        self.parts.append('<!' + decl + '>')

    def handle_comment(self, data):
        self.parts.append('<!--' + data + '-->')

    def render(self, html):
        self.feed(html)
        self.close()
        return ''.join(self.parts)
