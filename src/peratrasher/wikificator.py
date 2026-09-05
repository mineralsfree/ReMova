"""
Belarusian typography cleanup, ported from be.wikipedia Wikificator.
Source: https://be.wikipedia.org/wiki/MediaWiki:Gadget-wikificator.js

For plaintext (e.g. parallel corpora). Wiki-specific transformations
(templates, links, headings, tables, refs) are intentionally excluded.

Order matters. Apply via apply_rules(text).
"""

import re
from collections import Counter
from importlib.resources import files as _resource_files

from peratrasher.base import Stage

NBSP = " "

# ---- Always-on: invisibles, apostrophes, entities, whitespace -----------

CORE: list[tuple[re.Pattern, str]] = [
    # Soft hyphen + LTR/RTL direction marks
    (re.compile(r"[­‎‏]+"), ""),
    # Apostrophe: ' (U+0027) and ʼ (U+02BC) between letters -> ’ (U+2019)
    (re.compile(r"([\wа-яА-ЯёЁўЎіІ])['ʼ]([\wа-яА-ЯёЁўЎіІ])"), "\\1’\\2"),
    # HTML entities -> Unicode
    (re.compile(r"&copy;", re.I), "©"),
    (re.compile(r"&reg;", re.I), "®"),
    (re.compile(r"&sect;", re.I), "§"),
    (re.compile(r"&euro;", re.I), "€"),
    (re.compile(r"&yen;", re.I), "¥"),
    (re.compile(r"&pound;", re.I), "£"),
    (re.compile(r"&deg;"), "°"),
    (re.compile(r"\(tm\)|&trade;", re.I), "™"),
    (re.compile(r"\.\.\.|&hellip;"), "…"),
    (re.compile(r"\+-(?!\+|-)|&plusmn;"), "±"),
    (re.compile(r"~="), "≈"),
    (re.compile(r"&((la|ra|bd|ld)quo|quot);"), '"'),
    # Superscripts
    (re.compile(r"<sup>2</sup>|&sup2;", re.I), "²"),
    (re.compile(r"<sup>3</sup>|&sup3;", re.I), "³"),
    (re.compile(r"\^2(\D)"), r"²\1"),
    (re.compile(r"\^3(\D)"), r"³\1"),
    # ASCII guillemets <<X>> -> "X"
    (re.compile(r"<<(\S.+?\S)>>"), r'"\1"'),
    # №№ -> №
    (re.compile(r"№№"), "№"),
    # Trailing whitespace at EOL
    (re.compile(r"[ \t]+(\r?\n)"), r"\1"),
]

# ---- Typo / spelling fixes (ported from tmp/wikifix.js) -----------------
# Wikipedia AutoWikiBrowser Typos for Belarusian; each rule matches a whole
# word and rewrites it. The `((?:^|\s)[xX])` prefix is the JS gadget's way
# of asserting a left word-boundary; preserved verbatim.

TYPOS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"((?:^|\s)[аА])б'я([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)"), r'\1б’я\2'),
    (re.compile(r'((?:^|\s)[аА])днім(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1дным'),
    (re.compile(r'((?:^|\s)[аА])пэр([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1пер\2'),
    (re.compile(r'((?:^|\s)[аА])собаў(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1соб'),
    (re.compile(r'((?:^|\s)[аА])сьц([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1сц\2'),
    (re.compile(r'((?:^|\s)[аА])кторк([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ктрыс\2'),
    (re.compile(r'((?:^|\s)[аА])ктор(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1кцёр'),
    (re.compile(r'((?:^|\s)[аА])льгарытм([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1лгарытм\2'),
    (re.compile(r'((?:^|\s)[аА])мэрык([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1мерык\2'),
    (re.compile(r'((?:^|\s)[аА])нгельшчына(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1нглія'),
    (re.compile(r'((?:^|\s)[аА])нгельшчыне(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1нгліі'),
    (re.compile(r'((?:^|\s)[аА])нгельшчыны(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1нгліі'),
    (re.compile(r'((?:^|\s)[аА])нгельск([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1нглійск\2'),
    (re.compile(r'((?:^|\s)[аА])нтв[эе]рп[эе]н([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1нтверпен\2'),
    (re.compile(r'((?:^|\s)[аА])ргентын([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ргенцін\2'),
    (re.compile(r'((?:^|\s)[бБ])азэл([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1азел\2'),
    (re.compile(r'((?:^|\s)[бБ])азэл([А-ЯЁІЎа-яёіў]*)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1азел\2'),
    (re.compile(r'((?:^|\s)[бБ])ізнэсмэ([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ізнесме\2'),
    (re.compile(r'((?:^|\s)[бБ])ляк([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1лак\2'),
    (re.compile(r'((?:^|\s)[бБ])этон([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1етон\2'),
    (re.compile(r'((?:^|\s)[бБ])этон(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1етон'),
    (re.compile(r'((?:^|\s)[бБ])олш(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ольш'),
    (re.compile(r'((?:^|\s)[бБ])русэл([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1русел\2'),
    (re.compile(r'((?:^|\s)[бБ])эрг([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ерг\2'),
    (re.compile(r'((?:^|\s)[вВ])аеначальні([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1оеначальні\2'),
    (re.compile(r'((?:^|\s)[вВ])аяводз([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1аяводс\2'),
    (re.compile(r'((?:^|\s)[вВ])елікагалов([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ялікагалов\2'),
    (re.compile(r'((?:^|\s)[вВ])елікадзяржаўн([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ялікадзяржаўн\2'),
    (re.compile(r'((?:^|\s)[вВ])ерасьн(я|ем|ю)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ерасн\2'),
    (re.compile(r'((?:^|\s)[вВ])обласьц([ьію])(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1обласц\2'),
    (re.compile(r'((?:^|\s)[вВ])одарасцяў(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1одарасцей'),
    (re.compile(r'((?:^|\s)[Вв])ыстав(амі|а[юй]?|у)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ыстаўк\2'),
    (re.compile(r'((?:^|\s)[вВ])[эе]н[эе]р([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1енер\2'),
    (re.compile(r'((?:^|\s)[вВ])эрф([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ерф\2'),
    (re.compile(r'((?:^|\s)[вВ])ялікадушн([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1елікадушн\2'),
    (re.compile(r'((?:^|\s)[вВ])ялікакняжацк([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1елікакняжацк\2'),
    (re.compile(r'((?:^|\s)[вВ])ялікалуцк([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1елікалуцк\2'),
    (re.compile(r'((?:^|\s)[вВ])ялікамучанік([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1елікамучанік\2'),
    (re.compile(r'((?:^|\s)[вВ])ялікаруск([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1елікаруск\2'),
    (re.compile(r'((?:^|\s)[вВ])ялікасвецк([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1елікасвецк\2'),
    (re.compile(r'((?:^|\s)[гГ])адзінаў(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1адзін'),
    (re.compile(r'((?:^|\s)[гГ])адох(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1адах'),
    (re.compile(r'((?:^|\s)[гГ])азэт([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1азет\2'),
    (re.compile(r'((?:^|\s)[гГ])лябал([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1лабал\2'),
    (re.compile(r'((?:^|\s)(?:студзеня|лютага|сакавіка|красавіка|мая|чэрвеня|ліпеня|жніўня|верасня|кастрычніка|лістапада|снежня))\]\] \[\[(\d+)\]\] году(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1]] [[\2]] года'),
    (re.compile(r'((?:^|\s)[гГ])рамадзт([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1рамадст\2'),
    (re.compile(r'((?:^|\s)[дД])амэнік([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1аменік\2'),
    (re.compile(r'((?:^|\s)[дД])ачцы(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ачцэ'),
    (re.compile(r'((?:^|\s)[дД])зевяты([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1зявяты\2'),
    (re.compile(r'((?:^|\s)[дД])зесяты([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1зясяты\2'),
    (re.compile(r'((?:^|\s)[дД])зеячк([А-ЯЁІЎа-яёіў]*)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1зяячк\2'),
    (re.compile(r'((?:^|\s)[дД])зьвюх([А-ЯЁІЎа-яёіў]*)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1звюх\2'),
    (re.compile(r'((?:^|\s)[дД])зяяч([А-ЯЁІЎа-яёіў]*)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1зеяч\2'),
    (re.compile(r'((?:^|\s)[дД])ыплям([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ыплам\2'),
    (re.compile(r'((?:^|\s)[дД])ыплём([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ыплом\2'),
    (re.compile(r"((?:^|\s)[дД])'я([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)"), r'\1’я\2'),
    (re.compile(r'((?:^|\s)[жЖ])анаты на(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1анаты з'),
    (re.compile(r'((?:^|\s)[зЗ])аля(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ала'),
    (re.compile(r'((?:^|\s)[зЗ])аляў(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1алаў'),
    (re.compile(r'((?:^|\s)[уУ]) залі(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1 зале'),
    (re.compile(r'((?:^|\s)[зЗ]) дапамогаю(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1 дапамогай'),
    (re.compile(r'((?:^|\s)[зЗ]) мэтаю(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1 мэтай'),
    (re.compile(r'((?:^|\s)[зЗ])ьвязн([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1вязн\2'),
    (re.compile(r'((?:^|\s)[зЗ])ьвян(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1вян'),
    (re.compile(r'((?:^|\s)[зЗ])зьн([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1зн\2'),
    (re.compile(r'((?:^|\s)[зЗ])зьл([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1зл\2'),
    (re.compile(r'((?:^|\s)[зЗ])ья([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1’я\2'),
    (re.compile(r"((?:^|\s)[зЗ])'я([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)"), r'\1’я\2'),
    (re.compile(r'((?:^|\s)[іІ])мём(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1мем'),
    (re.compile(r'((?:^|\s)[іІ])нвэст([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1нвест\2'),
    (re.compile(r'((?:^|\s)[іІ])нтэрне([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1нтэрнэ\2'),
    (re.compile(r'((?:^|\s)[іІ])нтэрвію(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1нтэрв’ю'),
    (re.compile(r'((?:^|\s)[іІ])мпэр([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1мпер\2'),
    (re.compile(r'((?:^|\s)[кК])азімер([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1азімір\2'),
    (re.compile(r'((?:^|\s)[кК])алюмб([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1алумб\2'),
    (re.compile(r'((?:^|\s)[кК])ампут[эа]р([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1амп’ютар\2'),
    (re.compile(r"((?:^|\s)[кК])амп'ютэр([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)"), r'\1амп’ютар\2'),
    (re.compile(r'((?:^|\s)[кК])анстанты([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1анстанці\2'),
    (re.compile(r'((?:^|\s)[кК])аўкаскі(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1аўказскі'),
    (re.compile(r'((?:^|\s)[кК])апел(ай?|[уеы])(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1апэл\2'),
    (re.compile(r'((?:^|\s)[кК])ілямэтр([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1іламетр\2'),
    (re.compile(r'((?:^|\s)[кК])ілямэтар(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1іламетр'),
    (re.compile(r'((?:^|\s)[кК])люб([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1луб\2'),
    (re.compile(r'((?:^|\s)[кК])люб(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1луб'),
    (re.compile(r'((?:^|\s)[кК])лясыфік([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ласіфік\2'),
    (re.compile(r'((?:^|\s)[лЛ])етув([аеу])(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ітв\2'),
    (re.compile(r'((?:^|\s)[лЛ])ёндан([аеу])(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ондан\2'),
    (re.compile(r'((?:^|\s)[лЛ])ідэр(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ідар'),
    (re.compile(r'((?:^|\s)[лЛ])ідэр([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ідар\2'),
    (re.compile(r'((?:^|\s)[лЛ])яўрэа([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1аўрэа\2'),
    (re.compile(r'((?:^|\s)[лЛ])ягенд([А-ЯЁІЎа-яёіў]+|)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1егенд\2'),
    (re.compile(r'((?:^|\s)[мМ])аянез([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1аянэз\2'),
    (re.compile(r'((?:^|\s)[мМ])арсэл([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1арсел\2'),
    (re.compile(r'((?:^|\s)[мМ])ачапала([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1очапала\2'),
    (re.compile(r'((?:^|\s)[мМ])еньш(ы|ага|ым|аму|ыя|асць|асцей|асці|асцю|)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1енш\2'),
    (re.compile(r'((?:^|\s)[нН])айменьш(ы|ага|ым|аму|ыя|)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1айменш\2'),
    (re.compile(r'((?:^|\s)[мМ])ейсц(а?|ам|[eы])(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1есц\2'),
    (re.compile(r'((?:^|\s)[мМ])ескі(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1арадскі'),
    (re.compile(r'((?:^|\s)[мМ])еншасцяў(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1еншасцей'),
    (re.compile(r'((?:^|\s)[мМ])іністар(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1іністр'),
    (re.compile(r'((?:^|\s)[мМ])італёг([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1іфалог\2'),
    (re.compile(r'((?:^|\s)[мМ])італяг([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1іфалаг\2'),
    (re.compile(r'((?:^|\s)[мМ])оваў(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1оў'),
    (re.compile(r'((?:^|\s)[мМ])узэ([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1узе\2'),
    (re.compile(r'((?:^|\s)[мМ])этад([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1етад\2'),
    (re.compile(r'((?:^|\s)[мМ])этар(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1етр'),
    (re.compile(r'((?:^|\s)[мМ])этра(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1етра'),
    (re.compile(r'((?:^|\s)[мМ])этраў(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1етраў'),
    (re.compile(r'((?:^|\s)[мМ])этры(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1етры'),
    (re.compile(r'((?:^|\s)[мМ])[еэ]н[еэ]джм[еэ]н([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1енеджмен\2'),
    (re.compile(r'((?:^|\s)[мМ])юнхэн([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1юнхен\2'),
    (re.compile(r'((?:^|\s)[зЗнН])алежы(ў|л[аі])(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1алежа\2'),
    (re.compile(r'((?:^|\s)[нН])ідэрлянд([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ідэрланд\2'),
    (re.compile(r'((?:^|\s)[нН])эакласіц([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1еакласіц\2'),
    (re.compile(r'((?:^|\s)[нН])эалі([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1еалі\2'),
    (re.compile(r'((?:^|\s)[нН])эапал([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1еапал\2'),
    (re.compile(r'((?:^|\s)[оО])пэр([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1пер\2'),
    (re.compile(r'((?:^|\s)[пП])авал(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1авел'),
    (re.compile(r'((?:^|\s)[пП])а крайняй меры(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1рынамсі'),
    (re.compile(r'((?:^|\s)[пП])арлямэн([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1арламен\2'),
    (re.compile(r'((?:^|\s)[пП])асьля(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1асля'),
    (re.compile(r'((?:^|\s)[пП])ектын(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1екцін'),
    (re.compile(r'((?:^|\s)[пП])ётар(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ётр'),
    (re.compile(r'((?:^|\s)[пП])лян([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1лан\2'),
    (re.compile(r'((?:^|\s)[пП])лян(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1лан'),
    (re.compile(r'((?:^|\s)[пП])радусар([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1радзюсар\2'),
    (re.compile(r'((?:^|\s)[пП])рафэсар([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1рафесар\2'),
    (re.compile(r'((?:^|\s)[пП])розьвішч([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1розвішч\2'),
    (re.compile(r'((?:^|\s)[пП])расталінейн([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1росталінейн\2'),
    (re.compile(r'((?:^|\s)[пП])рэзыдэн([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1рэзідэн\2'),
    (re.compile(r"((?:^|\s)[пП])'я([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)"), r'\1’я\2'),
    (re.compile(r'((?:^|\s)[пП])эйзаж([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ейзаж\2'),
    (re.compile(r'((?:^|\s)[пП])эрыяд([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ерыяд\2'),
    (re.compile(r'((?:^|\s)[рР])асейск([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1асійск\2'),
    (re.compile(r'((?:^|\s)[рР])асейская мова(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1уская мова'),
    (re.compile(r'((?:^|\s)[рР])аслаўл([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ослаўл\2'),
    (re.compile(r'((?:^|\s)[рР])эзэрв(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1эзерв'),
    (re.compile(r'((?:^|\s)[рР])айн([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1эйн\2'),
    (re.compile(r'((?:^|\s)[рР])айн(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1эйн'),
    (re.compile(r"((?:^|\s)[рР])'я([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)"), r'\1’я\2'),
    (re.compile(r'((?:^|\s)[сС])ардын([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ардзін\2'),
    (re.compile(r'((?:^|\s)[сС])адавінай(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1адавіной'),
    (re.compile(r'((?:^|\s)[сС])езон (\d+) году(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1езон \2 года'),
    (re.compile(r'((?:^|\s)[сС])екрэцы([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1акрэцы\2'),
    (re.compile(r'((?:^|\s)[сС])партов([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1партыўн\2'),
    (re.compile(r'((?:^|\s)[сС])тагодзьдз([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1тагоддз\2'),
    (re.compile(r'((?:^|\s)[сС])таршынём(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1таршынёй'),
    (re.compile(r'((?:^|\s)[сС])урвет([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1урвэт\2'),
    (re.compile(r'((?:^|\s)[сС])ляваччына(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1лавакія'),
    (re.compile(r'((?:^|\s)[сС])ляваччыне(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1лавакіі'),
    (re.compile(r'((?:^|\s)[сС])ляваччыны(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1лавакіі'),
    (re.compile(r'((?:^|\s)[сС])ьне([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1не\2'),
    (re.compile(r'((?:^|\s)[нН])амесьн([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1амесн\2'),
    (re.compile(r'((?:^|\s)[сС])ьмех(у?|ам)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1мех\2'),
    (re.compile(r'((?:^|\s)[сС])ьв([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1в\2'),
    (re.compile(r'((?:^|\s)[сС])ымбаль(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1імвал'),
    (re.compile(r'((?:^|\s)[сС])ымбалем(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1імвалам'),
    (re.compile(r'((?:^|\s)[сС])экс([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1екс\2'),
    (re.compile(r'((?:^|\s)[сС])эрвер([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ервер\2'),
    (re.compile(r'((?:^|\s)[сС])эры([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1еры\2'),
    (re.compile(r'((?:^|\s)[сС])фэр([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1фер\2'),
    (re.compile(r'((?:^|\s)[сС])ымэтр([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1іметр\2'),
    (re.compile(r'((?:^|\s)[сС])юрэалізм([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1юррэалізм\2'),
    (re.compile(r'((?:^|\s)[тТ])окіо(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'Токіа'),
    (re.compile(r'((?:^|\s)[тТ])окіё(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'Токіа'),
    (re.compile(r'((?:^|\s)[тТ])унел([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1унэл\2'),
    (re.compile(r'((?:^|\s)[тТ])ок-шоў([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ок-шоу\2'),
    (re.compile(r'((?:^|\s)[тТ])экста(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1эксту'),
    (re.compile(r'((?:^|\s)[уУў])ладзіме([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ладзімі\2'),
    (re.compile(r'((?:^|\s)[уУў])нів[эе]рс[іы]тэ([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ніверсітэ\2'),
    (re.compile(r'((?:^|\s)[фФ])альсыф([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1альсіф\2'),
    (re.compile(r'((?:^|\s)[фФ])аун(а?|ай|[eуы])(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1аўн\2'),
    (re.compile(r'((?:^|\s)[фФ])ізы([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ізі\2'),
    (re.compile(r'((?:^|\s)[фФ])ляндры(я?|[юі]|яй)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ландры\2'),
    (re.compile(r'((?:^|\s)[фФ])эномэн(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1еномен'),
    (re.compile(r'((?:^|\s)[фФ])[эе]нам[эе]н([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1енамен\2'),
    (re.compile(r'((?:^|\s)[хХ])аас([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1аос\2'),
    (re.compile(r'((?:^|\s)[хХ])вілінаў(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1вілін'),
    (re.compile(r'((?:^|\s)[цЦ])энтар(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1энтр'),
    (re.compile(r'((?:^|\s)[чЧ])алец(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1лен'),
    (re.compile(r'((?:^|\s)[чЧ])альцом(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ленам'),
    (re.compile(r'((?:^|\s)[чЧ])альцы(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1лены'),
    (re.compile(r'((?:^|\s)[шШ])атлянды([яію])(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1атланды\2'),
    (re.compile(r'((?:^|\s)[шШ])вайцар([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1вейцар\2'),
    (re.compile(r'((?:^|\s)[эЭ])кземпляр([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1кзэмпляр\2'),
    (re.compile(r'((?:^|\s)[эЭ])ксп[эе]рым[эе]н([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1ксперымен\2'),
    (re.compile(r'((?:^|\s)[эЭ])ўра (?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'Еўра '),
    (re.compile(r'((?:^|\s)[эЭ])ўрапейск([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'Еўрапейск\2'),
    (re.compile(r'((?:^|\s)[эЭ])ўроп([уа]|[ые]|ай)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'Еўроп\2'),
    (re.compile(r'((?:^|\s)[эЭ]|[еЕ])ўразвяз([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'Еўрасаюз\2'),
    (re.compile(r'((?:^|\s)[эЭ])фэкт([А-ЯЁІЎа-яёіў]+)(?=[^A-ZА-ЯЁІЎa-zа-яёіў́]|$)'), r'\1фект\2'),
]

# ---- Dash / hyphen / minus normalization --------------------------------

DASHES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"–"), "-"),  # en-dash -> hyphen (intermediate)
    (re.compile(r"(\s)-{1,3} "), r"\1— "),  # " -- " -> " — "
    (re.compile(r"(\d)--(\d)"), r"\1—\2"),  # "1--2" -> "1—2"
    (re.compile(r"(\s)-(\d)"), r"\1−\2"),  # " -5" -> " −5" (proper minus)
    (re.compile(r"(sup>|sub>|\s)-(\d)"), r"\1−\2"),
]

# ---- NBSP insertion rules -----------------------------------------------

NBSP_RULES: list[tuple[re.Pattern, str]] = [
    # Year ranges & "гг."
    (
        re.compile(r"([(\s])([12]?\d{3})[  ]?(?:-{1,3}|—) ?([12]?\d{3})(?![\w-])"),
        r"\1\2—\3",
    ),
    (re.compile(r"([12]?\d{3}) ?(гг?\.)"), r"\1" + NBSP + r"\2"),
    # Century ranges & "стст."
    (
        re.compile(r"([(\s])([IVX]{1,5})[  ]?(?:-{1,3}|—) ?([IVX]{1,5})(?![\w-])"),
        r"\1\2—\3",
    ),
    (re.compile(r"([IVX]{1,5}) ?(стст?\.)"), r"\1" + NBSP + r"\2"),
    # Number + unit (млн, млрд, трлн, мм/см/дм/км, мг/кг, м, г)
    (
        re.compile(
            r'(\d)[  ]?(млн|млрд|трлн|(?:м|с|д|к)?м|[км]г)\.?(?=[,;.]| "?[а-яёўі-])'
        ),
        r"\1" + NBSP + r"\2",
    ),
    (re.compile(r"(\d)[  ](тыс)([^\.А-Яа-яЁёЎўІі])"), r"\1" + NBSP + r"\2.\3"),
    # ISBN
    (re.compile(r"ISBN:\s?(?=[\d\-]{8,17})"), "ISBN "),
    # Initials: А.С.Пушкін -> А. С. Пушкін (with NBSPs)
    (
        re.compile(r"([А-ЯЁЎІ]\.) ?([А-ЯЁЎІ]\.) ?([А-ЯЁЎІ][а-яёўі])"),
        r"\1" + NBSP + r"\2" + NBSP + r"\3",
    ),
    (re.compile(r"([А-ЯЁЎІ]\.)([А-ЯЁЎІ]\.)"), r"\1 \2"),
    # Sentence boundary missing space: "слова.Слова" -> "слова. Слова"
    (re.compile(r"([а-яёўі]\.)([А-ЯA-ZЁЎІ])"), r"\1 \2"),
    # Comma / semicolon: "word ,word" / "word , word" -> "word, word"
    (re.compile(r'([)"а-яa-zёўі\]])\s*,([\[("а-яa-zёўі])'), r"\1, \2"),
    (re.compile(r'([)"а-яa-zёўі\]])\s([,;])\s([\[("а-яa-zёўі])'), r"\1\2 \3"),
    # Percent / permille
    (
        re.compile(r"([^%/\w]\d+?(?:[.,]\d+?)?) ?([%‰])(?!-[А-Яа-яЁёЎўІі])"),
        r"\1" + NBSP + r"\2",
    ),
    (re.compile(r"(\d) ([%‰])(?=-[А-Яа-яЁёЎўІі])"), r"\1\2"),  # "5%-й"
    # № and §
    (re.compile(r"([№§])\s*(\d)"), r"\1" + NBSP + r"\2"),
    # Bracket whitespace
    (re.compile(r"\( +"), "("),
    (re.compile(r" +\)"), ")"),
    # Temperature: "20 °C" -> "20 °C"
    (
        re.compile(
            r'([\s\d=≈≠≤≥<>—("\'|])([+±−-]?\d+?(?:[.,]\d+?)?)'
            r'(?:[ °^*]| [°^*])[CС](?=[\s"\').,;!?|])'
        ),
        r"\1\2" + NBSP + "°C",
    ),
    (
        re.compile(
            r'([\s\d=≈≠≤≥<>—("\'|])([+±−-]?\d+?(?:[.,]\d+?)?)'
            r'(?:[ °^*]| [°^*])F(?=[\s"\').,;|!?])'
        ),
        r"\1\2" + NBSP + "°F",
    ),
    # Decimal: dot -> comma before %/‰/°
    (re.compile(r"(\s\d+)\.(\d+[  ]*[%‰°])"), r"\1,\2"),
]

# ---- Whitespace collapse (run last) -------------------------------------

COLLAPSE: list[tuple[re.Pattern, str]] = [
    (re.compile(r"[ \t ]{2,}"), " "),
]

# ---- Bulk tarashkievica → narkamaŭka word replacements ------------------
# Source of truth: `src/peratrasher/data/fix.txt`, format `key=value`,
# one per line, `#` for comments. Loaded once at module import. Applied with
# case-insensitive whole-word matching (Python `\b` is Unicode-aware so it
# works on Cyrillic). Case is preserved on the replacement: input "Пасьля"
# at sentence start becomes "Пасля"; explicitly-capitalized targets like
# "лукашэнка"→"Лукашэнка" fix de-capitalized proper nouns.
#
# Some entries are also matched by more general patterns in TYPOS above
# (e.g. `((?:^|\s)[пП])асьля` → `пасля` makes `пасьля=пасля` redundant in
# the common case). They are kept anyway because TYPOS only fires after
# whitespace/start-of-text, whereas `\b` also fires after punctuation /
# brackets / quotes — so this lookup catches `(пасьля)`, `«сьвет»`, etc.
# that TYPOS misses.

_FIX_TXT = _resource_files("peratrasher") / "data" / "fix.txt"


def _load_replacements(source=_FIX_TXT) -> dict[str, str]:
    """Parse `key=value` pairs from the packaged `data/fix.txt`.

    Skips comments / blank lines / no-ops (key == value). A missing file is
    a hard error: the table is required data, and quietly running without it
    would leave tarashkievica in the output with no signal.
    """
    out: dict[str, str] = {}
    with source.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if k and v and k != v:
                out[k] = v
    return out


REPLACEMENTS: dict[str, str] = _load_replacements()
if not REPLACEMENTS:
    # An empty table would build the alternation `\b(?:)\b`, which matches the
    # empty string at every word boundary and then KeyErrors on `""`.
    raise RuntimeError(f"no replacements parsed from {_FIX_TXT}")

# Build one big alternation; sort by length desc so longer keys take priority
# (e.g. "грамадзкага" before "грамадзкі") — Python's regex engine is leftmost,
# so order matters when prefixes overlap.
_REPLACEMENTS_RE = re.compile(
    r"\b(?:"
    + "|".join(re.escape(k) for k in sorted(REPLACEMENTS, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)


def _apply_replacements(text: str, fires: Counter) -> str:
    """Whole-word tarashkievica→narkamaŭka substitution. Tracks per-key
    firings in `fires` so stats output shows which entries actually hit."""

    def sub(m: re.Match) -> str:
        word = m.group(0)
        key = word.lower()
        repl = REPLACEMENTS[key]
        # If the input was capitalized but the replacement is lowercase
        # (e.g. sentence-initial "Пасьля" → "пасля"), uppercase the first
        # letter of the replacement. Targets that are already capitalized
        # (proper-noun fixes like "лукашэнка"→"Лукашэнка") pass through.
        if word[0].isupper() and repl[0].islower():
            repl = repl[0].upper() + repl[1:]
        fires[f"replacements[{key}]"] += 1
        return repl

    return _REPLACEMENTS_RE.sub(sub, text)


# ---- Latin → Belarusian Cyrillic homoglyph fix --------------------------
# Only applied to word-tokens that already contain Belarusian Cyrillic letters,
# so pure-Latin tokens (URLs, English proper nouns, code) are left alone.

LATIN_TO_BEL: dict[str, str] = {
    "a": "а", "c": "с", "e": "е", "i": "і", "o": "о", "p": "р", "x": "х", "y": "у",
    "A": "А", "B": "В", "C": "С", "E": "Е", "H": "Н", "I": "І", "K": "К",
    "M": "М", "O": "О", "P": "Р", "T": "Т", "X": "Х", "Y": "У",
}

_BEL_CYR_RE = re.compile(r"[а-яА-ЯёЁўЎіІ]")
_WORD_TOKEN_RE = re.compile(r"[\w'’ʼ]+")


def _fix_latin_homoglyphs(word: str, text_has_cyr: bool) -> str:
    # Word already mixes scripts → Cyrillicize the Latin homoglyphs in it.
    if _BEL_CYR_RE.search(word):
        return "".join(LATIN_TO_BEL.get(ch, ch) for ch in word)
    # Standalone single-letter homoglyph in otherwise-Cyrillic text (e.g. "І",
    # "У", "В" typed as Latin I/Y/B between Belarusian words).
    if text_has_cyr and len(word) == 1 and word in LATIN_TO_BEL:
        return LATIN_TO_BEL[word]
    return word


# ---- Quote pairing (multi-pass) -----------------------------------------
# Strategy: unify all quote glyphs to ASCII " then re-pair into «…» / „…“.

_QUOTE_UNIFY = re.compile(r"[«»“”„]")
_QUOTE_PAIR = re.compile(
    r'([\xa0\s\x02!|#\'"/(;+\-])"([^"]*)([^\s"(|])"'
    r"([^a-zA-Zа-яА-ЯёіўЁІ0-9])"
)
_QUOTE_NEST_RE = re.compile(r"«[^»]*«")
_QUOTE_NEST = re.compile(r"«([^»]*)«([^»]*)»")


def normalize_quotes(text: str) -> str:
    text = _QUOTE_UNIFY.sub('"', text)
    for _ in range(2):
        text = _QUOTE_PAIR.sub(r"\1«\2\3»\4", text)
    while _QUOTE_NEST_RE.search(text):
        text = _QUOTE_NEST.sub("«\\1„\\2“", text)
    return text


def _apply_group(
    text: str,
    rules: list[tuple[re.Pattern, str]],
    group: str,
    fires: Counter,
) -> str:
    for i, (pat, rep) in enumerate(rules):
        new = pat.sub(rep, text)
        if new != text:
            fires[f"{group}[{i}]"] += 1
            text = new
    return text


def apply_rules(
    text: str,
    *,
    apply_typos: bool = True,
    apply_replacements: bool = True,
    apply_dashes: bool = True,
    apply_nbsp: bool = True,
    apply_quotes: bool = True,
) -> tuple[str, dict[str, int]]:
    """Apply Belarusian typography fixes; return (cleaned, per-rule fire counts)."""
    fires: Counter[str] = Counter()
    text_has_cyr = bool(_BEL_CYR_RE.search(text))
    new = _WORD_TOKEN_RE.sub(
        lambda m: _fix_latin_homoglyphs(m.group(0), text_has_cyr), text
    )
    if new != text:
        fires["homoglyph"] += 1
        text = new
    if apply_typos:
        text = _apply_group(text, TYPOS, "typos", fires)
    if apply_replacements:
        text = _apply_replacements(text, fires)
    text = _apply_group(text, CORE, "core", fires)
    if apply_dashes:
        text = _apply_group(text, DASHES, "dashes", fires)
    if apply_nbsp:
        text = _apply_group(text, NBSP_RULES, "nbsp", fires)
    if apply_quotes:
        new = normalize_quotes(text)
        if new != text:
            fires["quotes"] += 1
            text = new
    text = _apply_group(text, COLLAPSE, "collapse", fires)
    return text, dict(fires)


class WikificatorStage(Stage):
    name = "wikificator"

    def __init__(
        self,
        input_field: str = "text",
        output_field: str | None = None,
        apply_typos: bool = True,
        apply_replacements: bool = True,
        apply_dashes: bool = True,
        apply_nbsp: bool = True,
        apply_quotes: bool = True,
    ) -> None:
        self.input_field = input_field
        self.output_field = output_field if output_field is not None else input_field
        if input_field != "text":
            self.name = f"wikificator_{input_field}"
        self.apply_typos = apply_typos
        self.apply_replacements = apply_replacements
        self.apply_dashes = apply_dashes
        self.apply_nbsp = apply_nbsp
        self.apply_quotes = apply_quotes
        self._rows_total = 0
        self._rows_changed = 0
        self._rule_fire_counts: Counter[str] = Counter()

    def process(self, row: dict) -> None:
        self._rows_total += 1
        original = row[self.input_field]
        cleaned, fires = apply_rules(
            original,
            apply_typos=self.apply_typos,
            apply_replacements=self.apply_replacements,
            apply_dashes=self.apply_dashes,
            apply_nbsp=self.apply_nbsp,
            apply_quotes=self.apply_quotes,
        )
        if cleaned != original:
            self._rows_changed += 1
            row[self.output_field] = cleaned
        for name, n in fires.items():
            self._rule_fire_counts[name] += n

    def stats(self) -> dict:
        return {
            "rows_total": self._rows_total,
            "rows_changed": self._rows_changed,
            "rule_fire_counts": dict(self._rule_fire_counts),
        }
