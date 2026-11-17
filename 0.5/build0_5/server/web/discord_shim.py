# -*- coding: utf-8 -*-
"""discord_shim: срез discord.py, который выводит не в Discord, а в браузер.
Неизвестные атрибуты не роняют игру, а попадают в GAPS и в журнал ошибок клиента."""
from __future__ import annotations
import asyncio, enum, itertools, logging, sys, types, time, inspect, datetime

log = logging.getLogger("web.shim")
GAPS = []
_seq = itertools.count(1)
def nid(p="i"): return f"{p}{next(_seq)}"

def _gap(where, name):
    key = f"{where}.{name}"
    if key not in GAPS:
        GAPS.append(key); log.warning("shim gap: %s", key)
    return key

class _Stub:
    def __init__(self, *a, **kw): pass
    def __call__(self, *a, **kw): return self
    def __getattr__(self, n): return _Stub()
    def __str__(self): return ""
    def __bool__(self): return False

_COLORS = {"blue":0x3498DB,"green":0x2ECC71,"red":0xE74C3C,"orange":0xE67E22,"gold":0xF1C40F,
           "teal":0x1ABC9C,"purple":0x9B59B6,"magenta":0xE91E63,"greyple":0x99AAB5,"dark_blue":0x206694,
           "dark_green":0x1F8B4C,"dark_red":0x992D22,"dark_gold":0xC27C0E,"dark_orange":0xA84300,
           "dark_purple":0x71368A,"dark_teal":0x11806A,"dark_magenta":0xAD1457,"dark_gray":0x607D8B,
           "dark_grey":0x607D8B,"dark_theme":0x313338,"light_grey":0x979C9F,"light_gray":0x979C9F,
           "lighter_grey":0x95A5A6,"blurple":0x5865F2,"fuchsia":0xEB459E,"aqua":0x1ABC9C,
           "dark_aqua":0x11806A,"yellow":0xFEE75C,"white":0xFFFFFE,"gray":0x95A5A6,"grey":0x95A5A6,
           "default":0,"random":0x8B949E,"luminous_vivid_red":0xE74C3C}
class _CM(type):
    def __getattr__(cls, n):
        k = n.lower()
        if k in _COLORS: return lambda: _COLORS[k]
        _gap("Color", n); return lambda: 0x8B949E
class Color(int, metaclass=_CM):
    def __new__(cls, value=0): return super().__new__(cls, int(value or 0))
    @classmethod
    def from_rgb(cls, r, g, b): return (r << 16) | (g << 8) | b
    @classmethod
    def random(cls):
        import random; return random.randint(0, 0xFFFFFF)
Colour = Color

class ButtonStyle(enum.IntEnum):
    primary=1; blurple=1; secondary=2; grey=2; gray=2; success=3; green=3; danger=4; red=4; link=5; url=5
class TextStyle(enum.IntEnum):
    short=1; single=1; paragraph=2; long=2

import re

_EMOJI_RE = re.compile(r"^<(a?):([A-Za-z0-9_~]{2,32}):(\d{5,25})>$")

def _twemoji_url(ch):
    if not ch: return None
    cps = [f"{ord(c):x}" for c in ch if c != "\ufe0f"]
    if not cps: return None
    return "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/" + "-".join(cps) + ".png"

class PartialEmoji:
    """Unicode-эмодзи и кастомные <:name:id> / <a:name:id> с рабочим .url."""
    def __init__(self, *, name=None, id=None, animated=False):
        self.name = name
        self.id = int(id) if id else None
        self.animated = bool(animated)

    @classmethod
    def from_str(cls, s):
        s = str(s or "").strip()
        m = _EMOJI_RE.match(s)
        if m: return cls(name=m.group(2), id=m.group(3), animated=bool(m.group(1)))
        return cls(name=s)

    @classmethod
    def from_dict(cls, d):
        return cls(name=d.get("name"), id=d.get("id"), animated=d.get("animated", False))

    def to_dict(self):
        return {"id": self.id, "name": self.name, "animated": self.animated}

    def is_custom(self): return self.id is not None
    def is_unicode_emoji(self): return self.id is None and bool(self.name)

    @property
    def url(self):
        if self.id:
            ext = "gif" if self.animated else "png"
            return f"https://cdn.discordapp.com/emojis/{self.id}.{ext}?size=64&quality=lossless"
        return _twemoji_url(self.name)

    @property
    def created_at(self):
        if not self.id: return None
        import datetime
        return datetime.datetime.fromtimestamp(((self.id >> 22) + 1420070400000) / 1000, datetime.timezone.utc)

    def __str__(self):
        if self.id: return f"<{'a' if self.animated else ''}:{self.name}:{self.id}>"
        return self.name or ""

    def __repr__(self): return f"<PartialEmoji {self}>"
    def __eq__(self, o): return isinstance(o, PartialEmoji) and str(self) == str(o)
    def __hash__(self): return hash(str(self))

Emoji = PartialEmoji

def _emoji_payload(e):
    """Для фронта: глиф, ссылка на кастомную картинку и имя-фолбэк."""
    if e is None: return {"emoji": None, "emoji_url": None, "emoji_name": None}
    p = e if isinstance(e, PartialEmoji) else PartialEmoji.from_str(str(e))
    if p.is_custom():
        return {"emoji": None, "emoji_url": p.url, "emoji_name": p.name}
    return {"emoji": p.name or None, "emoji_url": None, "emoji_name": p.name}

class DiscordException(Exception): pass
class HTTPException(DiscordException): pass
class NotFound(HTTPException): pass
class Forbidden(HTTPException): pass
class InteractionResponded(DiscordException): pass
class ClientException(DiscordException): pass

class _AttrDict(dict):
    """Прокси embed как в discord.py: доступ и по ключу, и через атрибут."""
    def __getattr__(self, k):
        if k.startswith("__"): raise AttributeError(k)
        return self.get(k)
    def __setattr__(self, k, v): self[k] = v
    def __bool__(self): return any(bool(v) for v in self.values())
    def __str__(self): return str(self.get("text") or self.get("name") or self.get("url") or "")

class _Field(_AttrDict):
    pass

class Embed:
    Empty = None

    def __init__(self, *, title=None, description=None, color=None, colour=None, url=None,
                 timestamp=None, type="rich", **kw):
        self.title=title; self.description=description; self.url=url; self.type=type
        self.timestamp=timestamp
        self.color=color if color is not None else colour
        self.fields=[]; self._footer={}; self._image=None; self._thumb=None; self._author={}

    # --- размер, как в discord.py: сумма всех видимых символов ---
    def __len__(self):
        total = len(self.title or "") + len(self.description or "")
        for f in self.fields:
            total += len(f.get("name") or "") + len(f.get("value") or "")
        total += len((self._footer or {}).get("text") or "")
        total += len((self._author or {}).get("name") or "")
        return total

    def __str__(self): return self.description or self.title or ""
    def __repr__(self): return f"<Embed title={self.title!r} len={len(self)}>"

    # --- поля ---
    def add_field(self, *, name, value, inline=True):
        self.fields.append(_Field(name=str(name), value=str(value), inline=bool(inline))); return self
    def insert_field_at(self, i, *, name, value, inline=True):
        self.fields.insert(i, _Field(name=str(name), value=str(value), inline=bool(inline))); return self
    def set_field_at(self, i, *, name, value, inline=True):
        if 0 <= i < len(self.fields):
            self.fields[i] = _Field(name=str(name), value=str(value), inline=bool(inline))
        return self
    def remove_field(self, i):
        if 0 <= i < len(self.fields): self.fields.pop(i)
        return self
    def clear_fields(self): self.fields=[]; return self

    # --- оформление ---
    def set_footer(self, *, text=None, icon_url=None):
        self._footer={"text":text,"icon_url":icon_url}; return self
    def remove_footer(self): self._footer={}; return self
    def set_image(self, *, url): self._image=url; return self
    def set_thumbnail(self, *, url): self._thumb=url; return self
    def set_author(self, *, name, url=None, icon_url=None):
        self._author={"name":name,"url":url,"icon_url":icon_url}; return self
    def remove_author(self): self._author={}; return self

    @property
    def footer(self): return _AttrDict(self._footer or {})
    @property
    def author(self): return _AttrDict(self._author or {})
    @property
    def image(self): return _AttrDict(url=self._image, proxy_url=self._image)
    @property
    def thumbnail(self): return _AttrDict(url=self._thumb, proxy_url=self._thumb)

    # --- копии и сериализация ---
    def copy(self):
        e=Embed(title=self.title, description=self.description, color=self.color,
                url=self.url, timestamp=self.timestamp)
        e.fields=[_Field(f) for f in self.fields]
        e._footer=dict(self._footer); e._image=self._image
        e._thumb=self._thumb; e._author=dict(self._author)
        return e

    def to_dict(self):
        ts=self.timestamp.isoformat() if isinstance(self.timestamp, datetime.datetime) else None
        return {"title":self.title,"description":self.description,
                "color":int(self.color) if self.color is not None else None,
                "fields":[dict(f) for f in self.fields],
                "footer":dict(self._footer or {}),"image":self._image,"thumbnail":self._thumb,
                "author":dict(self._author or {}),"timestamp":ts}

    @classmethod
    def from_dict(cls, d):
        e=cls(title=d.get("title"), description=d.get("description"), color=d.get("color"),
              url=d.get("url"))
        for f in (d.get("fields") or []):
            e.fields.append(_Field(name=f.get("name"), value=f.get("value"), inline=f.get("inline", True)))
        foot=d.get("footer") or {}
        e._footer={"text":foot.get("text"),"icon_url":foot.get("icon_url")}
        img=d.get("image"); e._image=img.get("url") if isinstance(img,dict) else img
        th=d.get("thumbnail"); e._thumb=th.get("url") if isinstance(th,dict) else th
        au=d.get("author") or {}
        e._author={"name":au.get("name"),"url":au.get("url"),"icon_url":au.get("icon_url")}
        return e

Embed.Empty = Embed()

class Item:
    def __init__(self, *, row=None, disabled=False, custom_id=None):
        self.row=row; self.disabled=disabled; self._explicit_id=custom_id
        self.custom_id=custom_id or nid("c"); self.view=None; self._decorated=None
    async def callback(self, interaction): pass

class Button(Item):
    def __init__(self, *, label=None, style=ButtonStyle.secondary, emoji=None, disabled=False, row=None,
                 url=None, custom_id=None):
        super().__init__(row=row,disabled=disabled,custom_id=custom_id)
        self.label=label
        try: self.style=ButtonStyle(style)
        except Exception: self.style=ButtonStyle.secondary
        self.emoji=emoji; self.url=url
    def to_dict(self):
        return {"type":"button","id":self.custom_id,"label":self.label or "","style":self.style.name,
                **_emoji_payload(self.emoji),"disabled":bool(self.disabled),
                "url":self.url,"row":self.row}
    def _clone(self):
        c=Button(label=self.label,style=self.style,emoji=self.emoji,disabled=self.disabled,
                 row=self.row,url=self.url,custom_id=self._explicit_id)
        c._decorated=self._decorated; return c

class SelectOption:
    def __init__(self, *, label, value=None, description=None, emoji=None, default=False):
        self.label=label; self.value=str(value if value is not None else label)
        self.description=description; self.emoji=emoji; self.default=default
    def to_dict(self):
        return {"label":self.label,"value":self.value,"description":self.description,
                **_emoji_payload(self.emoji),"default":self.default}

class Select(Item):
    def __init__(self, *, placeholder=None, options=None, min_values=1, max_values=1, disabled=False,
                 row=None, custom_id=None):
        super().__init__(row=row,disabled=disabled,custom_id=custom_id)
        self.placeholder=placeholder; self.min_values=min_values; self.max_values=max_values
        self.options=[o if isinstance(o,SelectOption) else SelectOption(**o) for o in (options or [])]
        self.values=[]
    def add_option(self, *, label, value=None, description=None, emoji=None, default=False):
        self.options.append(SelectOption(label=label,value=value,description=description,
                                         emoji=emoji,default=default)); return self
    def append_option(self, option): self.options.append(option); return self
    def to_dict(self):
        return {"type":"select","id":self.custom_id,"placeholder":self.placeholder,"min":self.min_values,
                "max":self.max_values,"disabled":bool(self.disabled),"values":list(self.values),
                "options":[o.to_dict() for o in self.options],"row":self.row}
    def _clone(self):
        c=Select(placeholder=self.placeholder,options=list(self.options),min_values=self.min_values,
                 max_values=self.max_values,disabled=self.disabled,row=self.row,custom_id=self._explicit_id)
        c._decorated=self._decorated; return c

def button(*, label=None, style=ButtonStyle.secondary, emoji=None, disabled=False, row=None, custom_id=None):
    def deco(f):
        b=Button(label=label,style=style,emoji=emoji,disabled=disabled,row=row,custom_id=custom_id)
        b._decorated=f; b.__name__=getattr(f,"__name__","btn"); return b
    return deco

def select(*, placeholder=None, options=None, min_values=1, max_values=1, disabled=False, row=None, custom_id=None):
    def deco(f):
        s=Select(placeholder=placeholder,options=options,min_values=min_values,max_values=max_values,
                 disabled=disabled,row=row,custom_id=custom_id)
        s._decorated=f; s.__name__=getattr(f,"__name__","sel"); return s
    return deco

class View:
    def __init_subclass__(cls, *, timeout=None, **kw):
        super().__init_subclass__(**kw); cls._class_timeout=timeout
    def __init__(self, *, timeout=180.0):
        ct=getattr(type(self),"_class_timeout",None)
        if ct is not None and timeout == 180.0: timeout=ct
        self.timeout=timeout; self.children=[]; self.message=None; self.id=nid("v")
        self._expires=time.time()+timeout if timeout else None
        self._event=asyncio.Event()
        for klass in reversed(type(self).__mro__):
            for name, val in list(vars(klass).items()):
                if isinstance(val, Item) and val._decorated is not None:
                    item=val._clone(); setattr(self,name,item); self.add_item(item)
    def add_item(self, item):
        item.view=self
        if item._decorated is not None:
            fn=item._decorated
            async def cb(interaction,_fn=fn,_it=item): return await _fn(self,interaction,_it)
            item.callback=cb
        self.children.append(item); return self
    def remove_item(self, item):
        if item in self.children: self.children.remove(item)
        return self
    def clear_items(self): self.children=[]; return self
    def stop(self):
        self._expires=None
        if not self._event.is_set(): self._event.set()
    def is_finished(self): return self._expires is not None and time.time() > self._expires
    async def wait(self):
        if self._expires is None:
            await self._event.wait(); return True
        left=max(0.0, self._expires-time.time())
        try:
            await asyncio.wait_for(self._event.wait(), timeout=left); return False
        except asyncio.TimeoutError:
            self._expires=time.time(); return True
    async def on_timeout(self): pass
    async def on_error(self, error, item, interaction): raise error
    async def interaction_check(self, interaction): return True
    def to_dict(self):
        rows={}
        for i,it in enumerate(self.children):
            r=it.row if it.row is not None else min(i//5,4)
            rows.setdefault(r,[]).append(it.to_dict())
        return {"id":self.id,"rows":[rows[r] for r in sorted(rows)],"expired":self.is_finished()}

class TextInput(Item):
    def __init__(self, *, label, style=TextStyle.short, placeholder=None, default=None, required=True,
                 min_length=None, max_length=None, custom_id=None, row=None):
        super().__init__(row=row,custom_id=custom_id or nid("t"))
        self.label=label
        try: self.style=TextStyle(style)
        except Exception: self.style=TextStyle.short
        self.placeholder=placeholder; self.default=default; self.required=required
        self.min_length=min_length; self.max_length=max_length; self._value=default or ""
    @property
    def value(self): return self._value
    @value.setter
    def value(self, v): self._value=v
    def to_dict(self):
        return {"type":"text","id":self.custom_id,"label":self.label,
                "multiline":self.style is TextStyle.paragraph,"placeholder":self.placeholder,
                "value":self._value,"required":self.required,"min":self.min_length,"max":self.max_length}

class Modal:
    def __init_subclass__(cls, *, title=None, timeout=None, custom_id=None, **kw):
        super().__init_subclass__(**kw)
        if title is not None: cls.title=title
        cls._class_timeout=timeout
    def __init__(self, *, title=None, timeout=None, custom_id=None):
        self.title=title or getattr(type(self),"title",None) or "Ввод"
        self.custom_id=custom_id or nid("m"); self.children=[]; self.id=self.custom_id
        for klass in reversed(type(self).__mro__):
            for name, val in list(vars(klass).items()):
                if isinstance(val, TextInput):
                    c=TextInput(label=val.label,style=val.style,placeholder=val.placeholder,default=val.default,
                                required=val.required,min_length=val.min_length,max_length=val.max_length,
                                custom_id=f"{self.custom_id}:{name}")
                    setattr(self,name,c); self.children.append(c)
    def add_item(self, item): self.children.append(item); return self
    async def on_submit(self, interaction): pass
    async def on_error(self, interaction, error): raise error
    async def interaction_check(self, interaction): return True
    def to_dict(self):
        return {"id":self.custom_id,"title":self.title,"fields":[c.to_dict() for c in self.children]}

class _Perms:
    def __init__(self, admin=False): self.administrator=admin; self.manage_guild=admin
class User:
    def __init__(self, id, name, admin=False):
        self.id=id; self.name=name; self.display_name=name; self.global_name=name; self.bot=False
        self.discriminator="0"; self.mention=f"<@{id}>"
        self.guild_permissions=_Perms(admin)
    def __str__(self): return self.name
Member = User

class Guild:
    def __init__(self, hub):
        self.id = 0
        self.name = "WEB"
        self._hub = hub
        self.me = User(0, "WEB", True)
        self.text_channels = []
        self.members = []
        self.member_count = 0

    def get_channel(self, cid):
        return self._hub.bot.get_channel(cid) if self._hub else None

    def get_member(self, uid):
        return None

    async def fetch_member(self, uid):
        return None

class Message:
    def __init__(self, session, mid):
        self._s=session; self.id=mid; self.author=User(0,"WEB")
        self.created_at=datetime.datetime.now(); self.attachments=[]; self.embeds=[]
        self.channel=getattr(session,"channel",None); self.jump_url=""
    async def edit(self, **kw):
        if self._s is None: return None
        return await self._s.op_edit(self.id, **kw)
    async def delete(self, *a, **kw):
        if self._s is not None: await self._s.op_delete(self.id)
    async def reply(self, *a, **kw): return await self._s.op_send(*a, **kw)
    async def add_reaction(self, *a, **kw): return None
    async def clear_reactions(self, *a, **kw): return None

class TextChannel:
    def __init__(self, hub, id=0, name="game"):
        self._hub=hub; self.id=id; self.name=name; self.mention=f"<#{id}>"
        self.guild=Guild(hub) if hub else None
    async def send(self, content=None, **kw): return await self._hub.broadcast(content, **kw)
    async def fetch_message(self, mid): return Message(self._hub, mid)
    def history(self, *a, **kw):
        async def gen():
            if False: yield
        return gen()
    async def purge(self, *a, **kw): return []

class InteractionResponse:
    def __init__(self, it): self._it=it
    def is_done(self): return self._it._done
    async def defer(self, *, ephemeral=False, thinking=False): self._it._done=True
    async def send_message(self, content=None, **kw):
        if self._it._done: raise InteractionResponded()
        self._it._done=True
        m=await self._it.session.op_send(content, **kw)
        self._it._original=m.id; self._it.message=m; return m
    async def edit_message(self, **kw):
        self._it._done=True
        t=self._it._original or self._it._component_msg or self._it.session.last_screen()
        if t: await self._it.session.op_edit(t, **kw)
        else: await self._it.session.op_send(kw.get("content"), embed=kw.get("embed"),
                                             embeds=kw.get("embeds"), view=kw.get("view"))
    async def send_modal(self, modal):
        if self._it._done: raise InteractionResponded()
        self._it._done=True; await self._it.session.op_modal(modal)

class Followup:
    def __init__(self, it): self._it=it
    async def send(self, content=None, **kw):
        self._it._done=True
        m=await self._it.session.op_send(content, **kw)
        if self._it._original is None: self._it._original=m.id
        return m
    async def edit_original_response(self, **kw):
        t=self._it._original or self._it._component_msg or self._it.session.last_screen()
        if t: await self._it.session.op_edit(t, **kw)
    async def edit_message(self, message_id=None, **kw):
        await self._it.session.op_edit(message_id or self._it._original or self._it.session.last_screen(), **kw)
    async def delete_original_response(self):
        t=self._it._original or self._it._component_msg
        if t: await self._it.session.op_delete(t)
    async def delete_message(self, message_id): await self._it.session.op_delete(message_id)
    async def fetch_message(self, message_id): return Message(self._it.session, message_id)

class Interaction:
    def __init__(self, session, *, message_id=None, data=None, client=None):
        self.session=session; self.user=session.user; self.client=client
        self.channel=session.channel; self.channel_id=session.channel.id
        self.guild=session.channel.guild; self.data=data or {}
        self.created_at=datetime.datetime.now(); self.id=int(time.time()*1000)
        self.locale="ru"; self.command=None; self.attachments=[]
        mid=message_id or session.last_screen()
        self.message=Message(session, mid) if mid else None
        self._component_msg=message_id; self._original=None; self._done=False
        self.response=InteractionResponse(self); self.followup=Followup(self)
    async def edit_original_response(self, **kw): await self.followup.edit_original_response(**kw)
    async def delete_original_response(self): await self.followup.delete_original_response()

class Choice:
    _is_choice=True
    def __init__(self, *, name, value): self.name=name; self.value=value
    def __class_getitem__(cls, item): return cls

COMMANDS={}
def register_command(name, f, description=""):
    ann=getattr(f,"__annotations__",{})
    params=[p for p in inspect.signature(f).parameters if p!="interaction"]
    COMMANDS[name]={"callback":f,"description":description,"params":params,
                    "choice_params":[p for p in params if getattr(ann.get(p),"_is_choice",False)]}
    return f

class Group:
    def __init__(self, *, name=None, description=None, **kw): self.name=name; self.description=description or ""
    def command(self, *, name=None, description=None, **kw):
        def deco(f): return register_command(f"{self.name} {name or f.__name__}", f, description or "")
        return deco
    def add_command(self, *a, **kw): pass

class CommandTree:
    def command(self, *, name=None, description=None, **kw):
        def deco(f): return register_command(name or f.__name__, f, description or "")
        return deco
    def add_command(self, *a, **kw): pass
    def remove_command(self, *a, **kw): pass
    async def sync(self, *a, **kw): return list(COMMANDS.values())
    def get_commands(self, *a, **kw): return list(COMMANDS.values())

class Intents:
    def __init__(self, *a, **kw): self.message_content=False; self.members=False; self.presences=False
    @classmethod
    def default(cls): return cls()
    @classmethod
    def all(cls): return cls()

class Client:
    def __init__(self, *a, **kw):
        self.user=User(0,"WEB"); self.guilds=[]; self._views=[]; self.tree=CommandTree()
        self._hub=None; self._channels={}; self.latency=0.0

        self.loop = None

    def _get_loop(self):
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    def event(self, f): return f
    def listen(self, name=None):
        def deco(f): return f
        return deco
    def add_view(self, v, **kw): self._views.append(v)
    def get_channel(self, cid):
        if cid not in self._channels: self._channels[cid]=TextChannel(self._hub, cid or 0)
        return self._channels[cid]
    async def fetch_channel(self, cid): return self.get_channel(cid)
    def get_guild(self, gid): return Guild(self._hub)
    async def wait_until_ready(self): return True
    def is_closed(self): return False
    async def close(self): return None
class Bot(Client):
    def __init__(self, *a, command_prefix=None, intents=None, **kw): super().__init__()
    def command(self, *a, **kw):
        def deco(f): return f
        return deco
    def group(self, *a, **kw):
        def deco(f): return f
        return deco
class File:
    def __init__(self, fp, filename=None, **kw): self.fp=fp; self.filename=filename
class Object:
    def __init__(self, id): self.id=id
class Attachment: pass
class AllowedMentions:
    def __init__(self, *a, **kw): pass
    @classmethod
    def none(cls): return cls()

def _modules():
    root=types.ModuleType("discord")
    for k,v in dict(Color=Color,Colour=Colour,ButtonStyle=ButtonStyle,TextStyle=TextStyle,Embed=Embed,
                    PartialEmoji=PartialEmoji,SelectOption=SelectOption,Interaction=Interaction,User=User,Member=Member,
                    Message=Message,TextChannel=TextChannel,Guild=Guild,Client=Client,Intents=Intents,File=File,
                    Object=Object,Attachment=Attachment,AllowedMentions=AllowedMentions,MISSING=None).items():
        setattr(root,k,v)
    ui=types.ModuleType("discord.ui")
    for k,v in dict(View=View,Button=Button,Select=Select,TextInput=TextInput,Modal=Modal,Item=Item,
                    button=button,select=select,SelectOption=SelectOption).items(): setattr(ui,k,v)
    er=types.ModuleType("discord.errors")
    for k,v in dict(DiscordException=DiscordException,HTTPException=HTTPException,NotFound=NotFound,
                    Forbidden=Forbidden,InteractionResponded=InteractionResponded,
                    ClientException=ClientException).items(): setattr(er,k,v)
    ut=types.ModuleType("discord.utils"); ut.MISSING=None
    ut.utcnow=lambda: datetime.datetime.now(datetime.timezone.utc)
    ut.get=lambda it,**kw: next((x for x in it if all(getattr(x,k,None)==v for k,v in kw.items())),None)
    ut.find=lambda pred,it: next((x for x in it if pred(x)),None)
    ut.escape_markdown=lambda t,**kw: str(t)
    ut.format_dt=lambda dt,style=None: str(dt)
    ap=types.ModuleType("discord.app_commands")
    for n in ("describe","choices","default_permissions","rename","guild_only","guilds",
              "check","autocomplete","allowed_contexts"):
        setattr(ap,n,lambda *a,**kw:(lambda f:f))
    ap.Choice=Choice; ap.CommandTree=CommandTree; ap.Group=Group
    ap.Range=lambda *a,**kw: str
    ap.command=lambda *a,**kw:(lambda f:f)
    ap.checks=types.SimpleNamespace(has_permissions=lambda **kw:(lambda f:f),
                                    has_role=lambda *a,**kw:(lambda f:f))
    ex=types.ModuleType("discord.ext"); cm=types.ModuleType("discord.ext.commands")
    cm.Bot=Bot; cm.Cog=type("Cog",(),{}); cm.Context=type("Context",(),{})
    cm.command=lambda *a,**kw:(lambda f:f); cm.group=lambda *a,**kw:(lambda f:f)
    cm.has_permissions=lambda **kw:(lambda f:f); cm.is_owner=lambda:(lambda f:f)
    cm.cooldown=lambda *a,**kw:(lambda f:f); cm.guild_only=lambda:(lambda f:f)
    tk=types.ModuleType("discord.ext.tasks")
    def _loop(**kw):
        def deco(f):
            def start(*a,**k):
                async def runner():
                    while True:
                        try: await f(*a,**k)
                        except asyncio.CancelledError: raise
                        except Exception: log.exception("task loop")
                        await asyncio.sleep(kw.get("seconds") or kw.get("minutes",1)*60)
                return asyncio.ensure_future(runner())
            f.start=start; f.cancel=lambda: None; return f
        return deco
    tk.loop=_loop; ex.commands=cm; ex.tasks=tk
    root.ui=ui; root.errors=er; root.utils=ut; root.app_commands=ap; root.ext=ex
    root.__version__="2.3.0-web"
    for mod,name in ((root,"discord"),(ui,"discord.ui"),(ut,"discord.utils"),
                     (ap,"discord.app_commands"),(er,"discord.errors"),(cm,"discord.ext.commands")):
        def make(nm):
            def getattr_fallback(attr):
                if attr.startswith("__"): raise AttributeError(attr)
                _gap(nm, attr); return _Stub()
            return getattr_fallback
        mod.__getattr__=make(name)
    return {"discord":root,"discord.ui":ui,"discord.errors":er,"discord.utils":ut,
            "discord.app_commands":ap,"discord.ext":ex,"discord.ext.commands":cm,"discord.ext.tasks":tk}

def install():
    cur=sys.modules.get("discord")
    if getattr(cur,"__version__","") == "2.3.0-web": return cur
    m=_modules(); sys.modules.update(m); return m["discord"]