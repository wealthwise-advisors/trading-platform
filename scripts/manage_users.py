"""Create and manage AutoTrader accounts.

This is the ONLY way an account comes into existence. There is no registration
endpoint -- /api/auth/register answers 403 by design -- because this is a
private instance and a self-serve endpoint would let anyone who reaches the URL
provision themselves an account.

    py -3.12 scripts/manage_users.py add    akash --name "Akash Yadav" --email a@b.c
    py -3.12 scripts/manage_users.py list
    py -3.12 scripts/manage_users.py passwd akash
    py -3.12 scripts/manage_users.py disable akash
    py -3.12 scripts/manage_users.py enable  akash
    py -3.12 scripts/manage_users.py delete  akash
    py -3.12 scripts/manage_users.py logout-all akash

The password is never taken as an argument: it would land in the shell history
and in the process list. It is prompted for, twice, with no echo.
"""

import argparse
import getpass
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api import auth          # noqa: E402
from db import users as repo  # noqa: E402

USERNAME_RE = re.compile(r"^[a-zA-Z0-9._-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def _ask_password() -> str:
    while True:
        pw = getpass.getpass("Password: ")
        problem = auth.password_problem(pw)
        if problem:
            print(f"  {problem}")
            continue
        if pw != getpass.getpass("Confirm : "):
            print("  Passwords do not match.")
            continue
        return pw


def cmd_add(a) -> int:
    if not USERNAME_RE.match(a.username):
        print("  Username must be 3-32 chars: letters, digits, . _ -")
        return 1
    if a.email and not EMAIL_RE.match(a.email):
        print("  That does not look like an email address.")
        return 1
    if repo.get_user(a.username):
        print(f"  {a.username!r} already exists.")
        return 1
    pw = _ask_password()
    try:
        uid = repo.create_user(
            a.username, auth.hash_password(pw), full_name=a.name or "",
            email=a.email or "", country=a.country or "", phone=a.phone or "")
    except sqlite3.IntegrityError:
        print(f"  {a.username!r} already exists.")
        return 1
    print(f"  created {a.username!r} (id {uid})")
    return 0


def cmd_list(a) -> int:
    rows = repo.list_users()
    if not rows:
        print("  no accounts yet -- create one with: manage_users.py add <username>")
        return 0
    print(f"  {'id':>3}  {'username':<18} {'active':<7} {'created':<20} last login")
    print("  " + "-" * 74)
    for r in rows:
        print(f"  {r['id']:>3}  {r['username']:<18} "
              f"{'yes' if r['is_active'] else 'NO':<7} {r['created_at']:<20} "
              f"{r['last_login_at'] or '-'}")
    return 0


def cmd_passwd(a) -> int:
    if not repo.get_user(a.username):
        print(f"  no such account: {a.username!r}")
        return 1
    pw = _ask_password()
    repo.set_password(a.username, auth.hash_password(pw))
    user = repo.get_user(a.username)
    n = repo.revoke_all(user.id)     # a password change ends existing sessions
    print(f"  password updated; {n} session(s) signed out")
    return 0


def cmd_disable(a) -> int:
    if not repo.set_active(a.username, False):
        print(f"  no such account: {a.username!r}")
        return 1
    print(f"  {a.username!r} disabled and signed out everywhere")
    return 0


def cmd_enable(a) -> int:
    if not repo.set_active(a.username, True):
        print(f"  no such account: {a.username!r}")
        return 1
    print(f"  {a.username!r} enabled")
    return 0


def cmd_delete(a) -> int:
    if input(f"  delete {a.username!r} and all its sessions? [y/N] ").lower() != "y":
        print("  cancelled")
        return 1
    if not repo.delete_user(a.username):
        print(f"  no such account: {a.username!r}")
        return 1
    print(f"  deleted {a.username!r}")
    return 0


def cmd_logout_all(a) -> int:
    user = repo.get_user(a.username)
    if not user:
        print(f"  no such account: {a.username!r}")
        return 1
    print(f"  {repo.revoke_all(user.id)} session(s) signed out")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="create an account")
    a.add_argument("username")
    a.add_argument("--name", default="")
    a.add_argument("--email", default="")
    a.add_argument("--country", default="")
    a.add_argument("--phone", default="")
    a.set_defaults(fn=cmd_add)

    sub.add_parser("list", help="list accounts").set_defaults(fn=cmd_list)

    for name, fn, helptext in [
        ("passwd", cmd_passwd, "change a password"),
        ("disable", cmd_disable, "disable an account and sign it out"),
        ("enable", cmd_enable, "re-enable an account"),
        ("delete", cmd_delete, "delete an account"),
        ("logout-all", cmd_logout_all, "sign an account out everywhere"),
    ]:
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("username")
        sp.set_defaults(fn=fn)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
