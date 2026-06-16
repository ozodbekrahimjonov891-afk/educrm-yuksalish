"""
EduCRM — Railway Cloud Server
Hech qanday kutubxona kerak emas, pure Python!
"""
 
import http.server
import json
import sqlite3
import os
import re
from datetime import datetime
from urllib.parse import urlparse
 
PORT = int(os.environ.get("PORT", 8000))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "educrm.db")
 
# ─── DATABASE ───────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject TEXT,
            phone TEXT,
            salary INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (date('now'))
        );
        CREATE TABLE IF NOT EXISTS groups_ (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject TEXT,
            teacher_id INTEGER,
            teacher_name TEXT,
            days TEXT,
            start_time TEXT,
            end_time TEXT,
            created_at TEXT DEFAULT (date('now'))
        );
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            group_id INTEGER,
            group_name TEXT,
            pay_status TEXT DEFAULT 'pending',
            amount INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (date('now'))
        );
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            student_name TEXT,
            group_name TEXT,
            amount INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            note TEXT,
            created_at TEXT DEFAULT (date('now'))
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            student_name TEXT,
            group_id INTEGER,
            present INTEGER DEFAULT 1,
            date TEXT DEFAULT (date('now')),
            note TEXT
        );
    """)
    conn.commit()
    conn.close()
 
def db_q(sql, params=(), one=False):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(sql, params)
    r = c.fetchone() if one else c.fetchall()
    conn.close()
    if one: return dict(r) if r else None
    return [dict(x) for x in r]
 
def db_x(sql, params=()):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(sql, params)
    lid = c.lastrowid
    conn.commit()
    conn.close()
    return lid
 
# ─── FRONTEND HTML ──────────────────────────────────────
FRONTEND_HTML = open(os.path.join(BASE_DIR, "index.html"), encoding="utf-8").read()
 
# ─── HANDLER ────────────────────────────────────────────
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {fmt%a}")
 
    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)
 
    def body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}
 
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
 
    def do_GET(self):
        p = urlparse(self.path).path.rstrip("/")
 
        if p in ("", "/"):
            body = FRONTEND_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
            return
 
        if p == "/api/stats":
            self.send_json({
                "students": db_q("SELECT COUNT(*) c FROM students", one=True)["c"],
                "teachers": db_q("SELECT COUNT(*) c FROM teachers", one=True)["c"],
                "groups":   db_q("SELECT COUNT(*) c FROM groups_", one=True)["c"],
                "income":   db_q("SELECT COALESCE(SUM(amount),0) s FROM payments WHERE status='paid'", one=True)["s"],
                "debts":    db_q("SELECT COUNT(*) c FROM students WHERE pay_status='debt'", one=True)["c"],
                "debt_amount": db_q("SELECT COALESCE(SUM(amount),0) s FROM payments WHERE status='debt'", one=True)["s"],
            }); return
 
        if p == "/api/students":
            self.send_json(db_q("SELECT * FROM students ORDER BY id DESC")); return
        if p == "/api/teachers":
            self.send_json(db_q("SELECT * FROM teachers ORDER BY id DESC")); return
        if p == "/api/groups":
            self.send_json(db_q("""
                SELECT g.*, (SELECT COUNT(*) FROM students s WHERE s.group_id=g.id) student_count
                FROM groups_ g ORDER BY g.id DESC""")); return
        if p == "/api/payments":
            self.send_json(db_q("SELECT * FROM payments ORDER BY id DESC")); return
        if p == "/api/attendance":
            self.send_json(db_q("""
                SELECT s.id student_id, s.name student_name, s.group_name,
                       a.present, a.note, a.date
                FROM students s
                LEFT JOIN attendance a ON a.student_id=s.id AND a.date=date('now')
                ORDER BY s.id""")); return
 
        self.send_json({"error": "Not found"}, 404)
 
    def do_POST(self):
        p = urlparse(self.path).path.rstrip("/")
        d = self.body()
 
        if p == "/api/students":
            if not d.get("name"): self.send_json({"error":"Ism kerak"},400); return
            nid = db_x("INSERT INTO students(name,phone,group_id,group_name,pay_status,amount) VALUES(?,?,?,?,?,?)",
                (d["name"],d.get("phone",""),d.get("group_id"),d.get("group_name",""),d.get("pay_status","pending"),int(d.get("amount",0))))
            if int(d.get("amount",0))>0:
                db_x("INSERT INTO payments(student_id,student_name,group_name,amount,status) VALUES(?,?,?,?,?)",
                    (nid,d["name"],d.get("group_name",""),int(d["amount"]),d.get("pay_status","pending")))
            self.send_json(db_q("SELECT * FROM students WHERE id=?", (nid,), one=True), 201); return
 
        if p == "/api/teachers":
            if not d.get("name"): self.send_json({"error":"Ism kerak"},400); return
            nid = db_x("INSERT INTO teachers(name,subject,phone,salary) VALUES(?,?,?,?)",
                (d["name"],d.get("subject",""),d.get("phone",""),int(d.get("salary",0))))
            self.send_json(db_q("SELECT * FROM teachers WHERE id=?", (nid,), one=True), 201); return
 
        if p == "/api/groups":
            if not d.get("name"): self.send_json({"error":"Nom kerak"},400); return
            t = db_q("SELECT * FROM teachers WHERE id=?", (d.get("teacher_id"),), one=True) if d.get("teacher_id") else None
            nid = db_x("INSERT INTO groups_(name,subject,teacher_id,teacher_name,days,start_time,end_time) VALUES(?,?,?,?,?,?,?)",
                (d["name"],d.get("subject",""),d.get("teacher_id"),t["name"] if t else d.get("teacher_name",""),
                 d.get("days",""),d.get("start_time",""),d.get("end_time","")))
            self.send_json(db_q("SELECT * FROM groups_ WHERE id=?", (nid,), one=True), 201); return
 
        if p == "/api/payments":
            nid = db_x("INSERT INTO payments(student_id,student_name,group_name,amount,status,note) VALUES(?,?,?,?,?,?)",
                (d.get("student_id"),d.get("student_name",""),d.get("group_name",""),
                 int(d.get("amount",0)),d.get("status","pending"),d.get("note","")))
            self.send_json(db_q("SELECT * FROM payments WHERE id=?", (nid,), one=True), 201); return
 
        if p == "/api/attendance":
            ex = db_q("SELECT id FROM attendance WHERE student_id=? AND date=date('now')", (d["student_id"],), one=True)
            if ex:
                db_x("UPDATE attendance SET present=?,note=? WHERE id=?",
                    (1 if d.get("present") else 0, d.get("note",""), ex["id"]))
            else:
                db_x("INSERT INTO attendance(student_id,student_name,group_id,present,note) VALUES(?,?,?,?,?)",
                    (d["student_id"],d.get("student_name",""),d.get("group_id"),1 if d.get("present") else 0,d.get("note","")))
            self.send_json({"ok":True}); return
 
        self.send_json({"error":"Not found"},404)
 
    def do_PUT(self):
        p = urlparse(self.path).path.rstrip("/")
        d = self.body()
        m = re.match(r"^/api/payments/(\d+)/pay$", p)
        if m:
            pay = db_q("SELECT * FROM payments WHERE id=?", (m.group(1),), one=True)
            if pay:
                db_x("UPDATE payments SET status='paid' WHERE id=?", (m.group(1),))
                db_x("UPDATE students SET pay_status='paid' WHERE id=?", (pay["student_id"],))
            self.send_json({"ok":True}); return
        m = re.match(r"^/api/students/(\d+)$", p)
        if m:
            db_x("UPDATE students SET name=?,phone=?,pay_status=?,amount=? WHERE id=?",
                (d["name"],d.get("phone",""),d.get("pay_status","pending"),int(d.get("amount",0)),m.group(1)))
            self.send_json({"ok":True}); return
        self.send_json({"error":"Not found"},404)
 
    def do_DELETE(self):
        p = urlparse(self.path).path.rstrip("/")
        for res in ["students","teachers","groups","payments"]:
            m = re.match(rf"^/api/{res}/(\d+)$", p)
            if m:
                tbl = "groups_" if res=="groups" else res
                db_x(f"DELETE FROM {tbl} WHERE id=?", (m.group(1),))
                self.send_json({"ok":True}); return
        self.send_json({"error":"Not found"},404)
 
if __name__ == "__main__":
    init_db()
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"✅ EduCRM ishga tushdi → port {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
 
