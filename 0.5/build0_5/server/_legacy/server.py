import http.server
import socketserver
import json
import os

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
DB_FILE = os.path.join(BASE_DIR, "database.json")

# Инициализация базы (если нет)
if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump({"users": {"xun": {"password": "2O$44", "isAdmin": True}}, "players": {}, "chats": {}, "mailbox": {}}, f, ensure_ascii=False)

class GameServer(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        if path.startswith('/api/'): return super().translate_path(path)
        filename = path.split('?')[0].split('#')[0].lstrip('/')
        server_path = os.path.join(BASE_DIR, filename)
        if os.path.exists(server_path): return server_path
        root_path = os.path.join(ROOT_DIR, filename)
        if os.path.exists(root_path): return root_path
        return server_path

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        super().end_headers()

    def do_GET(self):
        if self.path == '/api/data':
            with open(DB_FILE, "r", encoding="utf-8") as f: data = f.read()
            self.send_response(200); self.send_header('Content-Type', 'application/json; charset=utf-8'); self.end_headers()
            self.wfile.write(data.encode('utf-8'))
        else: super().do_GET()

    def do_POST(self):
        length = int(self.headers['Content-Length'])
        data = json.loads(self.rfile.read(length).decode('utf-8')) if length else {}

        try:
            res = {"status": "error", "message": "Unknown endpoint"}
            if self.path == '/api/update':
                with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
                res = {"status": "ok"}
            elif self.path == '/api/create_character':
                from api import api_create_character
                res = api_create_character(data.get('player', {}), data.get('name'), data.get('backstory'), data.get('origin'), data.get('skills', {}))
            elif self.path == '/api/main_menu':
                from api import api_get_main_menu
                res = api_get_main_menu(data.get('player', {}))
            elif self.path == '/api/move/connections':
                from api import api_get_connections
                res = api_get_connections(data.get('player', {}))
            elif self.path == '/api/move/action':
                from api import api_move_player
                res = api_move_player(data.get('player', {}), data.get('destination'))
            elif self.path == '/api/npcs':
                from api import api_get_npcs
                res = api_get_npcs(data.get('player', {}))
            elif self.path == '/api/dialog':
                from api import api_get_dialog
                res = api_get_dialog(data.get('player', {}), data.get('npc_id'), data.get('node_id'))
            elif self.path == '/api/combat/start':
                from api import api_start_combat
                res = api_start_combat(data.get('player', {}), data.get('enemy_id', 'упырь'))
            elif self.path == '/api/combat/action':
                from api import api_combat_action
                res = api_combat_action(data.get('player', {}), data.get('action'), data.get('part'))

            self.send_response(200); self.send_header('Content-Type', 'application/json; charset=utf-8'); self.end_headers()
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode('utf-8'))
        except Exception as e:
            self.send_response(500); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer): daemon_threads = True

os.chdir(BASE_DIR)
with ThreadedTCPServer(("", PORT), GameServer) as httpd:
    print(f"СЕРВЕР ЗАПУЩЕН НА ПОРТУ {PORT}")
    httpd.serve_forever()