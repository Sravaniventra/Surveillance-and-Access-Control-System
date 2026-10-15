import sys, json
sys.path.insert(0, ".")
import numpy as np
from backend.database import SessionLocal
from backend.models import Identity
from backend.config import settings

print("Match threshold:", settings.FACE_MATCH_THRESHOLD)
print()

db = SessionLocal()
rows = db.query(Identity).filter(Identity.is_active == True).all()

# Show cosine similarity between every pair to understand spread
embeddings = []
for i in rows:
    if i.face_embedding:
        v = np.array(json.loads(i.face_embedding), dtype=np.float32)
        n = np.linalg.norm(v)
        if n > 1e-6:
            v = v / n
        embeddings.append((i.identity_code, i.name, v))

print("Pairwise cosine similarities:")
for a in range(len(embeddings)):
    for b in range(a+1, len(embeddings)):
        sim = float(np.dot(embeddings[a][2], embeddings[b][2]))
        print("  %s(%s) vs %s(%s) = %.4f %s" % (
            embeddings[a][0], embeddings[a][1],
            embeddings[b][0], embeddings[b][1],
            sim,
            "<-- WOULD MATCH" if sim >= settings.FACE_MATCH_THRESHOLD else ""
        ))

db.close()
