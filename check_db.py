import sys
sys.path.insert(0, ".")
from backend.database import SessionLocal
from backend.models import Identity
import json, numpy as np

db = SessionLocal()
rows = db.query(Identity).all()
print("All identities (including inactive):", len(rows))
for i in rows:
    has_emb = bool(i.face_embedding)
    emb_len = 0
    if has_emb:
        try:
            emb_len = len(json.loads(i.face_embedding))
        except:
            pass
    print("  id=%d code=%s name=%s type=%s active=%s emb_dims=%d photo=%s" % (
        i.id, i.identity_code, i.name, i.identity_type, i.is_active, emb_len, i.photo_path))
db.close()
