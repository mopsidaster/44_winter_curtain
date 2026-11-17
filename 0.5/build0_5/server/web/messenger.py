# -*- coding: utf-8 -*-
"""Мессенджер: контакты, личные сообщения, почта. Хранение — server/web/messenger.db."""
from __future__ import annotations
import json, os, sqlite3, time, logging

log = logging.getLogger("web.msg")
SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts(
  owner INTEGER NOT NULL, peer INTEGER NOT NULL, alias TEXT, state TEXT NOT NULL,
  ts INTEGER NOT NULL, PRIMARY KEY(owner,peer));
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT, sender INTEGER NOT NULL, recipient INTEGER NOT NULL,
  body TEXT NOT NULL, subject TEXT, kind TEXT NOT NULL DEFAULT 'dm',
  ts INTEGER NOT NULL, read INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_msg_pair ON messages(sender,recipient,ts);
CREATE INDEX IF NOT EXISTS ix_msg_box ON messages(recipient,kind,read);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
"""

class Messenger:
    def __init__(self, path, accounts, on_message=None):
        self.path = path; self.accounts = accounts; self.on_message = on_message

    def _con(self):
        c = sqlite3.connect(self.path, timeout=10); c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL"); return c

    def init(self):
        with self._con() as c: c.executescript(SCHEMA)

    # ---------- контакты ----------
    def request(self, owner, login):
        acc = self.accounts.by_login(login)
        if not acc: return {"error": "Игрок с таким позывным не найден"}
        peer = acc["user_id"]
        if peer == owner: return {"error": "Нельзя добавить самого себя"}
        with self._con() as c:
            row = c.execute("SELECT state FROM contacts WHERE owner=? AND peer=?", (owner, peer)).fetchone()
            if row and row["state"] == "ok": return {"error": "Уже в контактах"}
            if row and row["state"] == "blocked": return {"error": "Контакт заблокирован"}
            back = c.execute("SELECT state FROM contacts WHERE owner=? AND peer=?", (peer, owner)).fetchone()
            now = int(time.time())
            if back and back["state"] == "out":      # встречная заявка -> сразу дружба
                c.execute("INSERT OR REPLACE INTO contacts VALUES(?,?,?,?,?)", (owner, peer, None, "ok", now))
                c.execute("INSERT OR REPLACE INTO contacts VALUES(?,?,?,?,?)", (peer, owner, None, "ok", now))
                self.system(peer, "Заявка принята: теперь вы в контактах.", "Контакты")
                return {"ok": True, "accepted": True, "peer": peer}
            c.execute("INSERT OR REPLACE INTO contacts VALUES(?,?,?,?,?)", (owner, peer, None, "out", now))
            c.execute("INSERT OR REPLACE INTO contacts VALUES(?,?,?,?,?)", (peer, owner, None, "in", now))
        self.system(peer, "Входящая заявка в контакты.", "Контакты")
        return {"ok": True, "peer": peer}

    def accept(self, owner, peer):
        with self._con() as c:
            c.execute("UPDATE contacts SET state='ok' WHERE owner=? AND peer=?", (owner, peer))
            c.execute("UPDATE contacts SET state='ok' WHERE owner=? AND peer=?", (peer, owner))
        self.system(peer, "Ваша заявка в контакты принята.", "Контакты")
        return {"ok": True}

    def decline(self, owner, peer):
        with self._con() as c:
            c.execute("DELETE FROM contacts WHERE owner=? AND peer=?", (owner, peer))
            c.execute("DELETE FROM contacts WHERE owner=? AND peer=?", (peer, owner))
        return {"ok": True}

    def block(self, owner, peer):
        with self._con() as c:
            now = int(time.time())
            c.execute("INSERT OR REPLACE INTO contacts VALUES(?,?,?,?,?)", (owner, peer, None, "blocked", now))
            c.execute("DELETE FROM contacts WHERE owner=? AND peer=?", (peer, owner))
        return {"ok": True}

    def rename(self, owner, peer, alias):
        with self._con() as c:
            c.execute("UPDATE contacts SET alias=? WHERE owner=? AND peer=?", (alias[:40], owner, peer))
        return {"ok": True}

    def _state(self, c, owner, peer):
        r = c.execute("SELECT state FROM contacts WHERE owner=? AND peer=?", (owner, peer)).fetchone()
        return r["state"] if r else None

    def contacts(self, owner, online=None):
        online = online or {}
        out = []; requests = []
        with self._con() as c:
            for r in c.execute("SELECT * FROM contacts WHERE owner=? ORDER BY ts DESC", (owner,)):
                acc = self.accounts.by_id(r["peer"])
                login = acc["login"] if acc else str(r["peer"])
                if r["state"] == "in":
                    requests.append({"id": r["peer"], "login": login, "ts": r["ts"]}); continue
                last = c.execute("""SELECT body,ts,kind,sender FROM messages
                                    WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?)
                                    ORDER BY ts DESC, id DESC LIMIT 1""",
                                 (owner, r["peer"], r["peer"], owner)).fetchone()
                unread = c.execute("""SELECT COUNT(*) n FROM messages WHERE sender=? AND recipient=?
                                      AND kind='dm' AND read=0""", (r["peer"], owner)).fetchone()["n"]
                info = online.get(r["peer"], {})
                out.append({"id": r["peer"], "login": login, "alias": r["alias"], "state": r["state"],
                            "online": bool(info), "location": info.get("location"),
                            "alive": info.get("alive", True), "unread": unread,
                            "last": dict(last) if last else None})
        out.sort(key=lambda x: (-(x["last"]["ts"] if x["last"] else 0), x["login"]))
        return {"contacts": out, "requests": requests}

    # ---------- сообщения ----------
    def send(self, sender, recipient, body, subject=None, kind="dm"):
        body = (body or "").strip()
        if not body: return {"error": "Пустое сообщение"}
        if len(body) > 2000: return {"error": "Максимум 2000 символов"}
        acc = self.accounts.by_id(recipient)
        if not acc: return {"error": "Получатель не найден"}
        if recipient == sender and kind != "system": return {"error": "Нельзя писать самому себе"}
        with self._con() as c:
            if kind == "dm":
                st = self._state(c, sender, recipient)
                if st == "blocked": return {"error": "Контакт заблокирован"}
                if self._state(c, recipient, sender) == "blocked": return {"error": "Получатель не принимает сообщения"}
                if st != "ok": return {"error": "Сначала добавьте игрока в контакты"}
            now = int(time.time())
            cur = c.execute("INSERT INTO messages(sender,recipient,body,subject,kind,ts,read) VALUES(?,?,?,?,?,?,0)",
                            (sender, recipient, body, (subject or "")[:120] or None, kind, now))
            mid = cur.lastrowid
        msg = {"id": mid, "sender": sender, "recipient": recipient, "body": body,
               "subject": (subject or "")[:120] or None, "kind": kind, "ts": now, "read": 0,
               "sender_login": (self.accounts.by_id(sender) or {}).get("login", "система"),
               "recipient_login": acc["login"]}
        if self.on_message:
            try: self.on_message(msg)
            except Exception: log.exception("on_message")
        return {"ok": True, "message": msg}

    def system(self, to, text, subject="Система"):
        return self.send(0, to, text, subject, "system")

    def thread(self, owner, peer, limit=120):
        with self._con() as c:
            rows = c.execute("""SELECT * FROM messages WHERE
                                ((sender=? AND recipient=?) OR (sender=? AND recipient=?))
                                AND kind IN ('dm','system') ORDER BY ts DESC, id DESC LIMIT ?""",
                             (owner, peer, peer, owner, limit)).fetchall()
            c.execute("UPDATE messages SET read=1 WHERE sender=? AND recipient=? AND read=0", (peer, owner))
        msgs = [dict(r) for r in reversed(rows)]
        for m in msgs:
            m["sender_login"] = (self.accounts.by_id(m["sender"]) or {}).get("login", "система")
        acc = self.accounts.by_id(peer) or {}
        return {"peer": {"id": peer, "login": acc.get("login", str(peer))}, "messages": msgs}

    def mail(self, owner, limit=80):
        with self._con() as c:
            rows = c.execute("""SELECT * FROM messages WHERE recipient=? AND kind IN ('mail','system')
                                ORDER BY ts DESC, id DESC LIMIT ?""", (owner, limit)).fetchall()
        out = [dict(r) for r in rows]
        for m in out:
            m["sender_login"] = (self.accounts.by_id(m["sender"]) or {}).get("login", "система")
        return {"letters": out}

    def mark_read(self, owner, ids=None, peer=None, kind=None):
        with self._con() as c:
            if ids:
                c.executemany("UPDATE messages SET read=1 WHERE id=? AND recipient=?", [(i, owner) for i in ids])
            elif peer is not None:
                c.execute("UPDATE messages SET read=1 WHERE recipient=? AND sender=? AND read=0", (owner, peer))
            elif kind:
                c.execute("UPDATE messages SET read=1 WHERE recipient=? AND kind=? AND read=0", (owner, kind))
        return {"ok": True}

    def unread(self, owner):
        with self._con() as c:
            dm = c.execute("SELECT COUNT(*) n FROM messages WHERE recipient=? AND kind='dm' AND read=0", (owner,)).fetchone()["n"]
            mail = c.execute("SELECT COUNT(*) n FROM messages WHERE recipient=? AND kind IN ('mail','system') AND read=0", (owner,)).fetchone()["n"]
            req = c.execute("SELECT COUNT(*) n FROM contacts WHERE owner=? AND state='in'", (owner,)).fetchone()["n"]
        return {"dm": dm, "mail": mail, "requests": req}

    # ---------- перенос старой базы ----------
    def import_legacy(self, path):
        if not os.path.exists(path): return {"skipped": "файл не найден"}
        with self._con() as c:
            if c.execute("SELECT v FROM meta WHERE k='legacy_import'").fetchone():
                return {"skipped": "уже импортировано"}
        try:
            data = json.load(open(path, encoding="utf-8"))
        except Exception as e:
            return {"error": str(e)}
        if not isinstance(data, dict): return {"error": "неизвестный формат"}
        by_login = {a["login"].lower(): a["user_id"] for a in self.accounts.all()}
        imported = 0; now = int(time.time())

        def uid_of(name):
            return by_login.get(str(name).strip().lower())

        def put(sender, recipient, body, subject, kind, ts):
            nonlocal imported
            if not recipient or not body: return
            with self._con() as c:
                c.execute("INSERT INTO messages(sender,recipient,body,subject,kind,ts,read) VALUES(?,?,?,?,?,?,1)",
                          (sender or 0, recipient, str(body)[:2000], subject, kind, ts or now))
            imported += 1

        for key, val in data.items():
            k = key.lower()
            if "mail" in k or "letter" in k or "inbox" in k or "почт" in k:
                items = val.values() if isinstance(val, dict) else (val if isinstance(val, list) else [])
                for it in items:
                    if not isinstance(it, dict): continue
                    to = uid_of(it.get("to") or it.get("recipient") or it.get("user") or it.get("owner") or "")
                    frm = uid_of(it.get("from") or it.get("sender") or it.get("author") or "")
                    put(frm, to, it.get("text") or it.get("body") or it.get("message"),
                        it.get("subject") or it.get("title") or "Почта (архив)", "mail",
                        int(it.get("ts") or it.get("time") or now))
            elif "chat" in k or "message" in k or "dialog" in k or "чат" in k:
                buckets = val.items() if isinstance(val, dict) else [(None, val)]
                for _, bucket in buckets:
                    msgs = bucket.get("messages") if isinstance(bucket, dict) else bucket
                    if not isinstance(msgs, list): continue
                    for it in msgs:
                        if not isinstance(it, dict): continue
                        to = uid_of(it.get("to") or it.get("recipient") or "")
                        frm = uid_of(it.get("from") or it.get("sender") or it.get("author") or "")
                        if to and frm:
                            put(frm, to, it.get("text") or it.get("body"), None, "dm",
                                int(it.get("ts") or it.get("time") or now))
        # контакты из старых пользователей не восстанавливаем автоматически — только пары из переписки
        with self._con() as c:
            pairs = c.execute("SELECT DISTINCT sender,recipient FROM messages WHERE kind='dm' AND sender>0").fetchall()
            for p in pairs:
                c.execute("INSERT OR IGNORE INTO contacts VALUES(?,?,?,?,?)", (p["sender"], p["recipient"], None, "ok", now))
                c.execute("INSERT OR IGNORE INTO contacts VALUES(?,?,?,?,?)", (p["recipient"], p["sender"], None, "ok", now))
            c.execute("INSERT OR REPLACE INTO meta VALUES('legacy_import',?)", (str(now),))
        return {"imported": imported, "contacts": len(pairs)}