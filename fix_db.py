import sys
sys.path.insert(0, ".")
from backend.database import SessionLocal
from backend.models import Identity

db = SessionLocal()

# Remove the 3 synthetic seed identities - they have random embeddings not from real faces
fake_codes = ["EMP-1027", "EMP-1042", "VIS-2001"]
for code in fake_codes:
    i = db.query(Identity).filter(Identity.identity_code == code).first()
    if i:
        db.delete(i)
        print("Deleted fake identity:", code, i.name)

db.commit()

# Show remaining
remaining = db.query(Identity).filter(Identity.is_active == True).all()
print()
print("Remaining real identities:", len(remaining))
for r in remaining:
    print("  %s - %s (%s)" % (r.identity_code, r.name, r.identity_type))

db.close()
