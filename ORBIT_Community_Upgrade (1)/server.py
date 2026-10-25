"""ORBIT local event platform: Flask + SQLite + CesiumJS/OpenStreetMap (no Google billing)."""
from __future__ import annotations
import json, os, re, sqlite3, uuid, mimetypes
from datetime import datetime, timezone
from pathlib import Path
from functools import wraps
from contextlib import contextmanager
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import Flask, jsonify, request, send_from_directory, send_file, session, abort

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'orbit.db'
UPLOADS = ROOT / 'uploads'
UPLOADS.mkdir(exist_ok=True)
MAX_UPLOAD = 12 * 1024 * 1024
ALLOWED = {'.png','.jpg','.jpeg','.webp','.gif','.pdf','.txt','.doc','.docx','.ppt','.pptx','.xls','.xlsx','.csv','.odt','.ods','.odp'}
IMAGE_EXT = {'.png','.jpg','.jpeg','.webp','.gif'}
CITIES = {'Mumbai','Delhi','Bengaluru','Chennai'}
CATEGORIES = {'Tech','Music','Art','Food','Sports','Business'}
def load_env_file():
    env_path = ROOT / '.env'
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line=line.strip()
            if line and not line.startswith('#') and '=' in line:
                key,value=line.split('=',1)
                os.environ.setdefault(key.strip(),value.strip().strip('\"').strip("'"))
load_env_file()
app = Flask(__name__)
_secret_file = ROOT / '.orbit_secret'
if os.environ.get('ORBIT_SECRET_KEY'):
    app.secret_key = os.environ['ORBIT_SECRET_KEY']
else:
    if not _secret_file.exists():
        _secret_file.write_text(uuid.uuid4().hex + uuid.uuid4().hex, encoding='utf-8')
    app.secret_key = _secret_file.read_text(encoding='utf-8').strip()
app.config.update(MAX_CONTENT_LENGTH=MAX_UPLOAD, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')


@contextmanager
def db():
    c = sqlite3.connect(DB, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def rowdict(r): return dict(r) if r else None

def init_db():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, owner_id TEXT REFERENCES users(id), city TEXT NOT NULL, title TEXT NOT NULL, category TEXT NOT NULL, mode TEXT NOT NULL, venue TEXT DEFAULT '', address TEXT DEFAULT '', lat REAL, lng REAL, start_at TEXT DEFAULT '', end_at TEXT DEFAULT '', timezone TEXT DEFAULT 'Asia/Kolkata', description TEXT DEFAULT '', requirements TEXT DEFAULT '', entry_type TEXT DEFAULT 'free', entry_fee TEXT DEFAULT '', currency TEXT DEFAULT 'INR', capacity INTEGER, registration_deadline TEXT DEFAULT '', banner TEXT DEFAULT '', status TEXT DEFAULT 'published', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS contacts(id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE, name TEXT NOT NULL, role TEXT DEFAULT '', email TEXT DEFAULT '', phone TEXT DEFAULT '', link TEXT DEFAULT '', public_email INTEGER DEFAULT 0, public_phone INTEGER DEFAULT 0, public_link INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS channels(id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE, name TEXT NOT NULL, description TEXT DEFAULT '', kind TEXT DEFAULT 'public', announcement_only INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS memberships(id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, payment_status TEXT DEFAULT 'not_required', joined_at TEXT NOT NULL, UNIQUE(event_id,user_id));
        CREATE TABLE IF NOT EXISTS channel_members(id TEXT PRIMARY KEY, channel_id TEXT NOT NULL REFERENCES channels(id) ON DELETE CASCADE, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, granted_by TEXT REFERENCES users(id), granted_at TEXT NOT NULL, revoked_at TEXT, UNIQUE(channel_id,user_id));
        CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY, channel_id TEXT NOT NULL REFERENCES channels(id) ON DELETE CASCADE, user_id TEXT NOT NULL REFERENCES users(id), body TEXT NOT NULL, created_at TEXT NOT NULL, deleted INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE, filename TEXT NOT NULL, stored_name TEXT NOT NULL, ext TEXT NOT NULL, size INTEGER NOT NULL, description TEXT DEFAULT '', access TEXT DEFAULT 'participants', uploaded_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE, actor_id TEXT NOT NULL REFERENCES users(id), action TEXT NOT NULL, target_id TEXT DEFAULT '', created_at TEXT NOT NULL);
        ''')
    migrate_json_events()

def migrate_json_events():
    legacy = ROOT / 'events.json'
    if not legacy.exists():
        with db() as c:
            if c.execute('SELECT COUNT(*) n FROM events').fetchone()['n'] == 0:
                demo = [
                    ('demo-mum-1','Mumbai','AI Hackathon','Tech','in-person','Jio World Centre','Jio World Centre, Mumbai',19.0646,72.8686,'2026-11-14T10:00','A 24-hour build sprint.'),
                    ('demo-mum-2','Mumbai','Harbour Sunset Sessions','Music','in-person','Gateway of India','Gateway of India, Mumbai',18.9220,72.8347,'2026-11-08T17:30','Live acoustic sets by the water.'),
                    ('demo-del-1','Delhi','Data Science Summit','Tech','in-person','Bharat Mandapam','Bharat Mandapam, New Delhi',28.6180,77.2437,'2026-11-18T09:30','Talks on applied analytics.'),
                    ('demo-blr-1','Bengaluru','Cubbon Park Startup Picnic','Business','in-person','Cubbon Park','Cubbon Park, Bengaluru',12.9763,77.5929,'2026-11-09T11:00','A casual founder and student mixer.'),
                    ('demo-che-1','Chennai','Marina Beach Cleanup Run','Sports','in-person','Marina Beach','Marina Beach, Chennai',13.0500,80.2824,'2026-11-08T06:00','Run and clean the shoreline.')]
                for eid,city,title,cat,mode,venue,address,lat,lng,start,desc in demo:
                    c.execute('INSERT INTO events(id,owner_id,city,title,category,mode,venue,address,lat,lng,start_at,description,created_at,updated_at) VALUES(?,NULL,?,?,?,?,?,?,?,?,?,?,?,?)',(eid,city,title,cat,mode,venue,address,lat,lng,start,desc,now(),now()))
                    for name,kind,ann,order in [('Announcements','public',1,0),('General','public',0,1)]:
                        c.execute('INSERT INTO channels(id,event_id,name,description,kind,announcement_only,sort_order,created_at) VALUES(?,?,?,?,?,?,?,?)',(uuid.uuid4().hex,eid,name,'Official event updates' if ann else '',kind,ann,order,now()))
        return
    try: events = json.loads(legacy.read_text(encoding='utf-8'))
    except Exception: return
    with db() as c:
        for e in events if isinstance(events, list) else []:
            if not isinstance(e, dict) or not e.get('id') or not e.get('title'): continue
            if c.execute('SELECT 1 FROM events WHERE id=?',(str(e['id']),)).fetchone(): continue
            city = e.get('city') if e.get('city') in CITIES else 'Mumbai'
            mode = e.get('mode') if e.get('mode') in ('in-person','online','hybrid') else 'in-person'
            category = e.get('category') if e.get('category') in CATEGORIES else 'Tech'
            c.execute('''INSERT INTO events(id,owner_id,city,title,category,mode,venue,address,lat,lng,start_at,description,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(str(e['id']),None,city,str(e['title'])[:120],category,mode,str(e.get('venue',''))[:180],str(e.get('address',''))[:300],e.get('lat'),e.get('lng'),str(e.get('when',''))[:40],str(e.get('description',''))[:2000],now(),now()))
            eid=str(e['id'])
            for name,kind,ann,order in [('Announcements','public',1,0),('General','public',0,1)]:
                c.execute('INSERT INTO channels(id,event_id,name,kind,announcement_only,sort_order,created_at) VALUES(?,?,?,?,?,?,?)',(uuid.uuid4().hex,eid,name,kind,ann,order,now()))

def current_user():
    uid=session.get('uid')
    if not uid: return None
    with db() as c: return rowdict(c.execute('SELECT id,username,email,created_at FROM users WHERE id=?',(uid,)).fetchone())
def login_required(fn):
    @wraps(fn)
    def wrap(*a,**kw):
        if not current_user(): return jsonify(error='Sign in to continue.'),401
        return fn(*a,**kw)
    return wrap
def event_row(c,eid): return c.execute('SELECT * FROM events WHERE id=?',(eid,)).fetchone()
def is_owner(c,eid,uid):
    r=event_row(c,eid)
    return bool(r and r['owner_id'] and r['owner_id']==uid)
def is_member(c,eid,uid): return bool(c.execute('SELECT 1 FROM memberships WHERE event_id=? AND user_id=?',(eid,uid)).fetchone())
def can_channel(c,ch,uid):
    if not uid: return False
    chrow=c.execute('SELECT * FROM channels WHERE id=?',(ch,)).fetchone()
    if not chrow:return False
    if is_owner(c,chrow['event_id'],uid): return True
    if chrow['kind']=='host': return False
    if chrow['kind']=='restricted':
        return bool(c.execute('SELECT 1 FROM channel_members WHERE channel_id=? AND user_id=? AND revoked_at IS NULL',(ch,uid)).fetchone())
    return is_member(c,chrow['event_id'],uid)
def event_json(c,r,viewer=None):
    e=dict(r)
    e['is_owner']=bool(viewer and e.get('owner_id')==viewer)
    e['banner_url']=('/media/'+e['banner']) if e.get('banner') else ''
    channel_sql='SELECT id,name,description,kind,announcement_only,sort_order FROM channels WHERE event_id=?' + ('' if e['is_owner'] else " AND kind!='host'") + ' ORDER BY sort_order,name'
    e['channels']=[dict(x) for x in c.execute(channel_sql,(e['id'],))]
    if e['is_owner']:
        doc_rows=c.execute('SELECT * FROM documents WHERE event_id=? ORDER BY created_at DESC',(e['id'],)).fetchall()
    elif viewer and is_member(c,e['id'],viewer):
        doc_rows=c.execute("SELECT * FROM documents WHERE event_id=? AND access IN ('public','participants') ORDER BY created_at DESC",(e['id'],)).fetchall()
    else:
        doc_rows=c.execute("SELECT * FROM documents WHERE event_id=? AND access='public' ORDER BY created_at DESC",(e['id'],)).fetchall()
    e['documents']=[dict(id=x['id'],filename=x['filename'],ext=x['ext'],size=x['size'],description=x['description'],access=x['access'],created_at=x['created_at'],download_url='/api/documents/'+x['id']+'/download') for x in doc_rows]
    e['contacts']=[dict(x) for x in c.execute('SELECT id,name,role,email,phone,link,public_email,public_phone,public_link,sort_order FROM contacts WHERE event_id=? ORDER BY sort_order',(e['id'],)) if e['is_owner'] or x['public_email'] or x['public_phone'] or x['public_link']]
    for x in e['contacts']:
        if not e['is_owner']:
            if not x['public_email']: x['email']=''
            if not x['public_phone']: x['phone']=''
            if not x['public_link']: x['link']=''
    e.pop('owner_id',None)
    return e

def audit(c,eid,uid,action,target=''):
    c.execute('INSERT INTO audit(id,event_id,actor_id,action,target_id,created_at) VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,eid,uid,action,target,now()))

@app.get('/')
def index(): return send_from_directory(ROOT,'index.html')
@app.get('/api/health')
def health(): return jsonify(ok=True,storage='sqlite',mapping='CesiumJS + OpenStreetMap; no Google API key required')
@app.get('/api/me')
def me(): return jsonify(user=current_user())
@app.post('/api/register')
def register():
    d=request.get_json(silent=True) or {}; username=str(d.get('username','')).strip(); email=str(d.get('email','')).strip().lower(); pw=str(d.get('password',''))
    if not re.fullmatch(r'[A-Za-z0-9_.-]{3,32}',username): return jsonify(error='Username must be 3–32 characters: letters, numbers, dot, underscore or hyphen.'),400
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): return jsonify(error='Enter a valid email address.'),400
    if len(pw)<10: return jsonify(error='Password must be at least 10 characters.'),400
    uid=uuid.uuid4().hex
    try:
        with db() as c:
            first_user = c.execute('SELECT COUNT(*) n FROM users').fetchone()['n'] == 0
            c.execute('INSERT INTO users(id,username,email,password_hash,created_at) VALUES(?,?,?,?,?)',(uid,username,email,generate_password_hash(pw),now()))
            # Local migration: the first account claims legacy events created before accounts existed.
            if first_user:
                c.execute("UPDATE events SET owner_id=? WHERE owner_id IS NULL AND id NOT LIKE 'demo-%'",(uid,))
    except sqlite3.IntegrityError:return jsonify(error='That username or email is already registered.'),409
    session.clear();session['uid']=uid
    return jsonify(user=current_user()),201
@app.post('/api/login')
def login():
    d=request.get_json(silent=True) or {}; ident=str(d.get('identity','')).strip().lower(); pw=str(d.get('password',''))
    with db() as c:r=c.execute('SELECT * FROM users WHERE lower(username)=? OR lower(email)=?',(ident,ident)).fetchone()
    if not r or not check_password_hash(r['password_hash'],pw): return jsonify(error='Incorrect username/email or password.'),401
    session.clear();session['uid']=r['id'];return jsonify(user=current_user())
@app.post('/api/logout')
def logout():session.clear();return jsonify(ok=True)

@app.get('/api/events')
def list_events():
    viewer=current_user(); city=request.args.get('city')
    with db() as c:
        rows=c.execute("SELECT * FROM events WHERE status IN ('published','cancelled') ORDER BY start_at").fetchall()
        return jsonify([event_json(c,r,viewer['id'] if viewer else None) for r in rows if not city or r['city']==city])
@app.get('/api/events/<eid>')
def get_event(eid):
    viewer=current_user()
    with db() as c:
        r=event_row(c,eid)
        if not r:return jsonify(error='Event not found.'),404
        if r['status'] not in ('published','cancelled') and not (viewer and is_owner(c,eid,viewer['id'])):return jsonify(error='Event not found.'),404
        return jsonify(event_json(c,r,viewer['id'] if viewer else None))
@app.post('/api/events')
@login_required
def create_event():
    u=current_user();d=request.get_json(silent=True) or {};title=str(d.get('title','')).strip();mode=d.get('mode');city=d.get('city');cat=d.get('category')
    if not title:return jsonify(error='Title is required.'),400
    if city not in CITIES:return jsonify(error='Choose a supported city.'),400
    if cat not in CATEGORIES:return jsonify(error='Choose a valid category.'),400
    if mode not in ('in-person','online','hybrid'):return jsonify(error='Choose a valid event type.'),400
    lat=lng=None
    if mode!='online':
        try:lat=float(d.get('lat'));lng=float(d.get('lng'))
        except (ValueError,TypeError):return jsonify(error='Physical and hybrid events need venue coordinates.'),400
        if not(-90<=lat<=90 and -180<=lng<=180):return jsonify(error='Coordinates are out of range.'),400
    fee=str(d.get('entry_fee',''))[:60];entry=d.get('entry_type','free')
    if entry not in ('free','paid'):entry='free'
    cap=None
    if str(d.get('capacity','')).strip():
        try:cap=int(d['capacity']);assert 1<=cap<=10000000
        except Exception:return jsonify(error='Capacity must be a positive whole number.'),400
    eid=uuid.uuid4().hex
    fields=(eid,u['id'],city,title[:120],cat,mode,str(d.get('venue',''))[:180],str(d.get('address',''))[:300],lat,lng,str(d.get('start_at',d.get('when','')))[:40],str(d.get('end_at',''))[:40],str(d.get('timezone','Asia/Kolkata'))[:80],str(d.get('description',''))[:4000],str(d.get('requirements',''))[:4000],entry,fee,str(d.get('currency','INR'))[:8],cap,str(d.get('registration_deadline',''))[:40],str(d.get('status','published')) if d.get('status')=='draft' else 'published',now(),now())
    with db() as c:
        c.execute('''INSERT INTO events(id,owner_id,city,title,category,mode,venue,address,lat,lng,start_at,end_at,timezone,description,requirements,entry_type,entry_fee,currency,capacity,registration_deadline,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',fields)
        for name,kind,ann,order in [('Announcements','public',1,0),('General','public',0,1),('Organizers','host',0,2)]:
            c.execute('INSERT INTO channels(id,event_id,name,description,kind,announcement_only,sort_order,created_at) VALUES(?,?,?,?,?,?,?,?)',(uuid.uuid4().hex,eid,name,'Official event updates' if ann else '',kind,ann,order,now()))
        audit(c,eid,u['id'],'event_created')
        return jsonify(event_json(c,event_row(c,eid),u['id'])),201
@app.patch('/api/events/<eid>')
@login_required
def update_event(eid):
    u=current_user();d=request.get_json(silent=True) or {}
    allowed={'title','category','mode','venue','address','lat','lng','start_at','end_at','timezone','description','requirements','entry_type','entry_fee','currency','capacity','registration_deadline','status','city'}
    with db() as c:
        if not is_owner(c,eid,u['id']):return jsonify(error='Only this event’s organizer can edit it.'),403
        r=event_row(c,eid);vals=dict(r)
        for k in allowed:
            if k in d:vals[k]=d[k]
        if not str(vals['title']).strip() or vals['city'] not in CITIES or vals['category'] not in CATEGORIES or vals['mode'] not in ('in-person','online','hybrid'):return jsonify(error='Please check the title, city, category and event type.'),400
        if vals['mode']!='online':
            try:vals['lat']=float(vals['lat']);vals['lng']=float(vals['lng'])
            except (ValueError,TypeError):return jsonify(error='Valid coordinates are required.'),400
            if not(-90<=vals['lat']<=90 and -180<=vals['lng']<=180):return jsonify(error='Coordinates are out of range.'),400
        if vals['status'] not in ('draft','published','cancelled','archived'):return jsonify(error='Invalid event status.'),400
        keys=list(allowed); vals['updated_at']=now(); keys.append('updated_at')
        c.execute('UPDATE events SET '+','.join(k+'=?' for k in keys)+' WHERE id=?',[vals[k] for k in keys]+[eid]);audit(c,eid,u['id'],'event_updated')
        return jsonify(event_json(c,event_row(c,eid),u['id']))

@app.post('/api/events/<eid>/join')
@login_required
def join_event(eid):
    u=current_user()
    with db() as c:
        e=event_row(c,eid)
        if not e or e['status']!='published':return jsonify(error='Event is not available.'),404
        if is_owner(c,eid,u['id']):return jsonify(ok=True,owner=True)
        if e['capacity']:
            n=c.execute('SELECT count(*) n FROM memberships WHERE event_id=?',(eid,)).fetchone()['n']
            if n>=e['capacity'] and not is_member(c,eid,u['id']):return jsonify(error='This event has reached capacity.'),409
        c.execute("INSERT OR IGNORE INTO memberships(id,event_id,user_id,payment_status,joined_at) VALUES(?,?,?, ?,?)",(uuid.uuid4().hex,eid,u['id'],'pending' if e['entry_type']=='paid' else 'not_required',now()))
        return jsonify(ok=True,joined=True,payment_status=('pending' if e['entry_type']=='paid' else 'not_required'))
@app.get('/api/events/<eid>/participants')
@login_required
def participants(eid):
    u=current_user()
    with db() as c:
        if not is_owner(c,eid,u['id']):return jsonify(error='Organizer access required.'),403
        rows=c.execute('''SELECT m.user_id,m.payment_status,m.joined_at,u.username,u.email FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.event_id=? ORDER BY m.joined_at''',(eid,)).fetchall()
        for x in rows:
            x=dict(x);x['channels']=[dict(y) for y in c.execute('SELECT cm.channel_id,ch.name FROM channel_members cm JOIN channels ch ON ch.id=cm.channel_id WHERE cm.user_id=? AND ch.event_id=? AND cm.revoked_at IS NULL',(x['user_id'],eid))]
        return jsonify(rows)
@app.patch('/api/events/<eid>/participants/<uid>')
@login_required
def participant_update(eid,uid):
    u=current_user();d=request.get_json(silent=True) or {}
    with db() as c:
        if not is_owner(c,eid,u['id']):return jsonify(error='Organizer access required.'),403
        m=c.execute('SELECT * FROM memberships WHERE event_id=? AND user_id=?',(eid,uid)).fetchone()
        if not m:return jsonify(error='Participant has not joined this event.'),404
        status=d.get('payment_status')
        if status not in ('pending','verified','rejected','not_required'):return jsonify(error='Invalid payment status.'),400
        c.execute('UPDATE memberships SET payment_status=? WHERE event_id=? AND user_id=?',(status,eid,uid));audit(c,eid,u['id'],'payment_'+status,uid)
        return jsonify(ok=True,payment_status=status)

@app.post('/api/events/<eid>/channels')
@login_required
def create_channel(eid):
    u=current_user();d=request.get_json(silent=True) or {};name=str(d.get('name','')).strip()
    if not name or len(name)>60:return jsonify(error='Channel name must be 1–60 characters.'),400
    kind=d.get('kind','public')
    if kind not in ('public','host','restricted'):return jsonify(error='Invalid channel access.'),400
    with db() as c:
        if not is_owner(c,eid,u['id']):return jsonify(error='Organizer access required.'),403
        order=c.execute('SELECT COALESCE(MAX(sort_order),-1)+1 n FROM channels WHERE event_id=?',(eid,)).fetchone()['n'];cid=uuid.uuid4().hex
        c.execute('INSERT INTO channels(id,event_id,name,description,kind,announcement_only,sort_order,created_at) VALUES(?,?,?,?,?,?,?,?)',(cid,eid,name,str(d.get('description',''))[:300],kind,1 if d.get('announcement_only') else 0,order,now()))
        audit(c,eid,u['id'],'channel_created',cid);return jsonify(dict(id=cid,event_id=eid,name=name,description=str(d.get('description',''))[:300],kind=kind,announcement_only=1 if d.get('announcement_only') else 0,sort_order=order)),201
@app.patch('/api/channels/<cid>')
@login_required
def update_channel(cid):
    u=current_user();d=request.get_json(silent=True) or {}
    with db() as c:
        ch=c.execute('SELECT * FROM channels WHERE id=?',(cid,)).fetchone()
        if not ch:return jsonify(error='Channel not found.'),404
        if not is_owner(c,ch['event_id'],u['id']):return jsonify(error='Organizer access required.'),403
        name=str(d.get('name',ch['name'])).strip();kind=d.get('kind',ch['kind']);ann=1 if d.get('announcement_only',ch['announcement_only']) else 0
        if not name or len(name)>60 or kind not in ('public','host','restricted'):return jsonify(error='Invalid channel settings.'),400
        order=d.get('sort_order',ch['sort_order'])
        try:order=int(order)
        except:order=ch['sort_order']
        c.execute('UPDATE channels SET name=?,description=?,kind=?,announcement_only=?,sort_order=? WHERE id=?',(name,str(d.get('description',ch['description']))[:300],kind,ann,order,cid));audit(c,ch['event_id'],u['id'],'channel_updated',cid)
        return jsonify(dict(id=cid,name=name,description=str(d.get('description',ch['description']))[:300],kind=kind,announcement_only=ann,sort_order=order))
@app.delete('/api/channels/<cid>')
@login_required
def delete_channel(cid):
    u=current_user()
    with db() as c:
        ch=c.execute('SELECT * FROM channels WHERE id=?',(cid,)).fetchone()
        if not ch:return jsonify(error='Channel not found.'),404
        if not is_owner(c,ch['event_id'],u['id']):return jsonify(error='Organizer access required.'),403
        c.execute('DELETE FROM channels WHERE id=?',(cid,));audit(c,ch['event_id'],u['id'],'channel_deleted',cid);return jsonify(ok=True)
@app.post('/api/channels/<cid>/members/<uid>')
@login_required
def grant_channel(cid,uid):
    u=current_user()
    with db() as c:
        ch=c.execute('SELECT * FROM channels WHERE id=?',(cid,)).fetchone()
        if not ch:return jsonify(error='Channel not found.'),404
        if not is_owner(c,ch['event_id'],u['id']):return jsonify(error='Organizer access required.'),403
        m=c.execute('SELECT payment_status FROM memberships WHERE event_id=? AND user_id=?',(ch['event_id'],uid)).fetchone()
        if not m:return jsonify(error='User must join the event before channel assignment.'),400
        e=event_row(c,ch['event_id'])
        if ch['kind']=='restricted' and e['entry_type']=='paid' and m['payment_status']!='verified':return jsonify(error='Verify payment before assigning this participant to a restricted paid-event channel.'),403
        c.execute('''INSERT INTO channel_members(id,channel_id,user_id,granted_by,granted_at,revoked_at) VALUES(?,?,?,?,?,NULL) ON CONFLICT(channel_id,user_id) DO UPDATE SET granted_by=excluded.granted_by,granted_at=excluded.granted_at,revoked_at=NULL''',(uuid.uuid4().hex,cid,uid,u['id'],now()))
        audit(c,ch['event_id'],u['id'],'channel_access_granted',uid+':'+cid);return jsonify(ok=True)
@app.delete('/api/channels/<cid>/members/<uid>')
@login_required
def revoke_channel(cid,uid):
    u=current_user()
    with db() as c:
        ch=c.execute('SELECT * FROM channels WHERE id=?',(cid,)).fetchone()
        if not ch:return jsonify(error='Channel not found.'),404
        if not is_owner(c,ch['event_id'],u['id']):return jsonify(error='Organizer access required.'),403
        c.execute('UPDATE channel_members SET revoked_at=? WHERE channel_id=? AND user_id=?',(now(),cid,uid));audit(c,ch['event_id'],u['id'],'channel_access_revoked',uid+':'+cid);return jsonify(ok=True)
@app.get('/api/channels/<cid>/messages')
@login_required
def messages(cid):
    u=current_user()
    with db() as c:
        ch=c.execute('SELECT * FROM channels WHERE id=?',(cid,)).fetchone()
        if not ch:return jsonify(error='Channel not found.'),404
        if not can_channel(c,cid,u['id']):return jsonify(error='You do not have access to this channel.'),403
        rows=c.execute('SELECT m.id,m.body,m.created_at,m.user_id,u.username,m.deleted FROM messages m JOIN users u ON u.id=m.user_id WHERE m.channel_id=? ORDER BY m.created_at DESC LIMIT 100',(cid,)).fetchall()
        return jsonify([dict(x) for x in reversed(rows)])
@app.post('/api/channels/<cid>/messages')
@login_required
def send_message(cid):
    u=current_user();d=request.get_json(silent=True) or {};body=str(d.get('body','')).strip()
    if not body or len(body)>4000:return jsonify(error='Message must be 1–4000 characters.'),400
    with db() as c:
        ch=c.execute('SELECT * FROM channels WHERE id=?',(cid,)).fetchone()
        if not ch:return jsonify(error='Channel not found.'),404
        if not can_channel(c,cid,u['id']):return jsonify(error='You do not have access to this channel.'),403
        if ch['announcement_only'] and not is_owner(c,ch['event_id'],u['id']):return jsonify(error='Only organizers can post in this announcement channel.'),403
        mid=uuid.uuid4().hex;c.execute('INSERT INTO messages(id,channel_id,user_id,body,created_at) VALUES(?,?,?,?,?)',(mid,cid,u['id'],body,now()))
        return jsonify(dict(id=mid,channel_id=cid,user_id=u['id'],username=u['username'],body=body,created_at=now(),deleted=0)),201
@app.delete('/api/messages/<mid>')
@login_required
def delete_message(mid):
    u=current_user()
    with db() as c:
        m=c.execute('SELECT m.*,ch.event_id FROM messages m JOIN channels ch ON ch.id=m.channel_id WHERE m.id=?',(mid,)).fetchone()
        if not m:return jsonify(error='Message not found.'),404
        if m['user_id']!=u['id'] and not is_owner(c,m['event_id'],u['id']):return jsonify(error='Not authorized.'),403
        c.execute('UPDATE messages SET deleted=1,body="[message removed]" WHERE id=?',(mid,));return jsonify(ok=True)

@app.post('/api/events/<eid>/contacts')
@login_required
def add_contact(eid):
    u=current_user();d=request.get_json(silent=True) or {};name=str(d.get('name','')).strip()
    if not name:return jsonify(error='Contact name is required.'),400
    with db() as c:
        if not is_owner(c,eid,u['id']):return jsonify(error='Organizer access required.'),403
        cid=uuid.uuid4().hex;order=c.execute('SELECT COALESCE(MAX(sort_order),-1)+1 n FROM contacts WHERE event_id=?',(eid,)).fetchone()['n']
        c.execute('INSERT INTO contacts(id,event_id,name,role,email,phone,link,public_email,public_phone,public_link,sort_order) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(cid,eid,name[:100],str(d.get('role',''))[:100],str(d.get('email',''))[:254],str(d.get('phone',''))[:50],str(d.get('link',''))[:500],int(bool(d.get('public_email'))),int(bool(d.get('public_phone'))),int(bool(d.get('public_link'))),order))
        return jsonify(id=cid,name=name,role=d.get('role',''),email=d.get('email',''),phone=d.get('phone',''),link=d.get('link',''),public_email=bool(d.get('public_email')),public_phone=bool(d.get('public_phone')),public_link=bool(d.get('public_link')),sort_order=order),201
@app.patch('/api/contacts/<cid>')
@login_required
def update_contact(cid):
    u=current_user();d=request.get_json(silent=True) or {}
    with db() as c:
        x=c.execute('SELECT * FROM contacts WHERE id=?',(cid,)).fetchone()
        if not x:return jsonify(error='Contact not found.'),404
        if not is_owner(c,x['event_id'],u['id']):return jsonify(error='Organizer access required.'),403
        fields=['name','role','email','phone','link','public_email','public_phone','public_link','sort_order'];vals=dict(x)
        for k in fields:
            if k in d: vals[k]=int(bool(d[k])) if k.startswith('public_') else d[k]
        if not str(vals['name']).strip():return jsonify(error='Contact name is required.'),400
        c.execute('UPDATE contacts SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',[vals[k] for k in fields]+[cid]);return jsonify(ok=True)
@app.delete('/api/contacts/<cid>')
@login_required
def delete_contact(cid):
    u=current_user()
    with db() as c:
        x=c.execute('SELECT * FROM contacts WHERE id=?',(cid,)).fetchone()
        if not x:return jsonify(error='Contact not found.'),404
        if not is_owner(c,x['event_id'],u['id']):return jsonify(error='Organizer access required.'),403
        c.execute('DELETE FROM contacts WHERE id=?',(cid,));return jsonify(ok=True)

@app.post('/api/events/<eid>/banner')
@login_required
def upload_banner(eid):
    u=current_user()
    with db() as c:
        if not is_owner(c,eid,u['id']):return jsonify(error='Organizer access required.'),403
        f=request.files.get('file')
        if not f:return jsonify(error='Choose an image.'),400
        ext=Path(secure_filename(f.filename)).suffix.lower()
        if ext not in IMAGE_EXT:return jsonify(error='Banner must be PNG, JPG, WEBP or GIF.'),400
        data=f.read(MAX_UPLOAD+1)
        if not data or len(data)>MAX_UPLOAD:return jsonify(error='Image is empty or exceeds 12 MB.'),400
        if not image_signature_ok(data,ext):return jsonify(error='File contents do not match a supported image type.'),400
        name=uuid.uuid4().hex+ext;(UPLOADS/name).write_bytes(data)
        old=event_row(c,eid)['banner'];c.execute('UPDATE events SET banner=?,updated_at=? WHERE id=?',(name,now(),eid))
        if old:
            try:(UPLOADS/old).unlink(missing_ok=True)
            except OSError:pass
        return jsonify(banner_url='/media/'+name)
def image_signature_ok(data,ext):
    if ext in ('.jpg','.jpeg'):return data.startswith(b'\xff\xd8\xff')
    if ext=='.png':return data.startswith(b'\x89PNG\r\n\x1a\n')
    if ext=='.gif':return data.startswith((b'GIF87a',b'GIF89a'))
    if ext=='.webp':return len(data)>12 and data[:4]==b'RIFF' and data[8:12]==b'WEBP'
    return False
@app.delete('/api/events/<eid>/banner')
@login_required
def remove_banner(eid):
    u=current_user()
    with db() as c:
        if not is_owner(c,eid,u['id']):return jsonify(error='Organizer access required.'),403
        old=event_row(c,eid)['banner']
        c.execute('UPDATE events SET banner='',updated_at=? WHERE id=?',(now(),eid))
        if old:
            try:(UPLOADS/old).unlink(missing_ok=True)
            except OSError:pass
        return jsonify(ok=True)

@app.post('/api/events/<eid>/documents')
@login_required
def upload_document(eid):
    u=current_user();f=request.files.get('file');desc=str(request.form.get('description',''))[:500];access=request.form.get('access','participants')
    if access not in ('public','participants','restricted'):access='participants'
    with db() as c:
        if not is_owner(c,eid,u['id']):return jsonify(error='Organizer access required.'),403
        if not f:return jsonify(error='Choose a file.'),400
        original=secure_filename(f.filename or '');ext=Path(original).suffix.lower()
        if not original or ext not in ALLOWED:return jsonify(error='Unsupported file type.'),400
        data=f.read(MAX_UPLOAD+1)
        if not data or len(data)>MAX_UPLOAD:return jsonify(error='File is empty or exceeds 12 MB.'),400
        # Reject common executable/script signatures even if renamed.
        if data.startswith((b'MZ',b'\x7fELF',b'#!')) or ext in {'.html','.htm','.js','.exe','.bat','.cmd','.ps1','.sh','.py'}:return jsonify(error='This file type is not permitted.'),400
        stored=uuid.uuid4().hex+ext;(UPLOADS/stored).write_bytes(data);did=uuid.uuid4().hex
        c.execute('INSERT INTO documents(id,event_id,filename,stored_name,ext,size,description,access,uploaded_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(did,eid,original[:200],stored,ext,len(data),desc,access,u['id'],now()))
        return jsonify(id=did,filename=original,ext=ext,size=len(data),description=desc,access=access,created_at=now(),download_url='/api/documents/'+did+'/download'),201
@app.delete('/api/documents/<did>')
@login_required
def delete_document(did):
    u=current_user()
    with db() as c:
        d=c.execute('SELECT * FROM documents WHERE id=?',(did,)).fetchone()
        if not d:return jsonify(error='Document not found.'),404
        if not is_owner(c,d['event_id'],u['id']):return jsonify(error='Organizer access required.'),403
        c.execute('DELETE FROM documents WHERE id=?',(did,))
        try:(UPLOADS/d['stored_name']).unlink(missing_ok=True)
        except OSError:pass
        return jsonify(ok=True)
@app.get('/api/documents/<did>/download')
def download_document(did):
    u=current_user()
    with db() as c:
        d=c.execute('SELECT * FROM documents WHERE id=?',(did,)).fetchone()
        if not d:return jsonify(error='Document not found.'),404
        allowed=d['access']=='public' or (u and is_owner(c,d['event_id'],u['id']))
        if not allowed and u:
            allowed=is_member(c,d['event_id'],u['id'])
            if d['access']=='restricted':allowed=bool(c.execute('SELECT 1 FROM channel_members cm JOIN channels ch ON ch.id=cm.channel_id WHERE ch.event_id=? AND cm.user_id=? AND ch.kind="restricted" AND cm.revoked_at IS NULL',(d['event_id'],u['id'])).fetchone())
        if not allowed:return jsonify(error='Sign in with an eligible event account to access this file.'),403
        path=UPLOADS/d['stored_name']
        if not path.is_file():return jsonify(error='File is missing from storage.'),404
        return send_file(path,as_attachment=True,download_name=d['filename'],mimetype='application/octet-stream',conditional=True)
@app.get('/media/<name>')
def media(name):
    # Only banner files are public; stored names are random and must match a database reference.
    with db() as c:
        if not c.execute('SELECT 1 FROM events WHERE banner=?',(name,)).fetchone():abort(404)
    path=UPLOADS/name
    if not path.is_file():abort(404)
    return send_file(path,mimetype=mimetypes.guess_type(name)[0] or 'application/octet-stream',conditional=True)

@app.get('/api/my-events')
@login_required
def my_events():
    u=current_user()
    with db() as c:
        rows=c.execute('SELECT * FROM events WHERE owner_id=? ORDER BY updated_at DESC',(u['id'],)).fetchall()
        return jsonify([event_json(c,r,u['id']) for r in rows])

@app.get('/api/events/<eid>/owned')
@login_required
def owned_events(eid):
    u=current_user()
    with db() as c:
        if not is_owner(c,eid,u['id']):return jsonify(error='Organizer access required.'),403
        e=event_row(c,eid)
        if not e:return jsonify(error='Event not found.'),404
        ev=event_json(c,e,u['id'])
        ev['documents']=[dict(id=x['id'],filename=x['filename'],ext=x['ext'],size=x['size'],description=x['description'],access=x['access'],created_at=x['created_at'],download_url='/api/documents/'+x['id']+'/download') for x in c.execute('SELECT * FROM documents WHERE event_id=? ORDER BY created_at DESC',(eid,))]
        ev['contacts']=[dict(x) for x in c.execute('SELECT * FROM contacts WHERE event_id=? ORDER BY sort_order',(eid,))]
        return jsonify(ev)

@app.errorhandler(413)
def too_large(_):return jsonify(error='Upload exceeds the 12 MB limit.'),413

init_db()
if __name__=='__main__':
    # Local development only. Do not expose Flask's built-in server directly to the public internet.
    app.run(host='127.0.0.1',port=5000,debug=False)
