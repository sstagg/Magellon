"""Print short-lived login tokens for the screenshot scripts, as JSON.

Runs inside the core container, which holds the JWT secret:

    docker exec -i -w /app/CoreService magellon-core-container \
        python - pm22p super < shoot/mint_tokens.py > shoot/.tokens.json

The arguments are the member and the administrator account to log in as.
The tokens last two hours; shoot/.tokens.json is git-ignored.
"""
import json
import sys
from datetime import timedelta

from database import session_local
from dependencies.auth import create_access_token
from models.sqlalchemy_models import SysSecUser

member, admin = sys.argv[1], sys.argv[2]
out = {}
with session_local() as db:
    for role, username in (("member", member), ("admin", admin)):
        user = db.query(SysSecUser).filter(SysSecUser.USERNAME == username).first()
        if user is None:
            sys.exit("no user %r" % username)
        token = create_access_token({"sub": str(user.oid), "username": user.USERNAME},
                                    expires_delta=timedelta(hours=2))
        out[role] = {"id": str(user.oid), "username": user.USERNAME, "token": token}
print(json.dumps(out))
