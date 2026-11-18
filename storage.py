import sqlite3, json
class Store:
 def __init__(self,path):
  self.path=path
  with self.conn() as c:
   c.execute('''CREATE TABLE IF NOT EXISTS applications(id INTEGER PRIMARY KEY AUTOINCREMENT,payload TEXT NOT NULL,status TEXT DEFAULT 'pending',contract TEXT)''')
   c.execute('''CREATE TABLE IF NOT EXISTS manager_modes(user_id INTEGER PRIMARY KEY,app_id INTEGER)''')
 def conn(self): return sqlite3.connect(self.path)
 def create(self,d):
  with self.conn() as c:
   cur=c.execute('INSERT INTO applications(payload,status) VALUES(?,?)',(json.dumps(d,ensure_ascii=False),'pending')); return cur.lastrowid
 def get(self,i):
  with self.conn() as c:
   r=c.execute('SELECT payload FROM applications WHERE id=?',(i,)).fetchone(); return json.loads(r[0]) if r else None
 def set_status(self,i,s):
  with self.conn() as c:c.execute('UPDATE applications SET status=? WHERE id=?',(s,i))
 def set_contract(self,i,p):
  with self.conn() as c:c.execute('UPDATE applications SET contract=? WHERE id=?',(p,i))
 def get_contract(self,i):
  with self.conn() as c:
   r=c.execute('SELECT contract FROM applications WHERE id=?',(i,)).fetchone(); return r[0] if r else None
 def set_manager_mode(self,u,a):
  with self.conn() as c:c.execute('INSERT OR REPLACE INTO manager_modes VALUES(?,?)',(u,a))
 def get_manager_mode(self,u):
  with self.conn() as c:
   r=c.execute('SELECT app_id FROM manager_modes WHERE user_id=?',(u,)).fetchone(); return r[0] if r else None
 def clear_manager_mode(self,u):
  with self.conn() as c:c.execute('DELETE FROM manager_modes WHERE user_id=?',(u,))
