"""Create and manage AutoTrader accounts.

Registration is OPEN. This script is the operator's door, not the only one:
people sign themselves up through /api/auth/register, and an OAuth sign-in from
an address nobody holds yet creates an account on the spot.

    (This paragraph used to say the opposite -- "the ONLY way an account comes
    into existence ... /api/auth/register answers 403 by design". That stopped
    being true when signup was opened, and a --help that describes the security
    model backwards is worse than one that describes nothing: it is read by
    someone deciding whether a thing is safe.)

What is still true, and is the part worth knowing:

    An account grants the ANALYSIS app. It does not grant the broker. There is
    one Schwab connection and it is the operator's own, so `users.is_owner`
    defaults to 0, `create_user` has no parameter for it, and no route can set
    it. Nothing a stranger can reach touches the brokerage.

    py -3.12 scripts/manage_users.py add    akash --name "Akash Yadav" --email a@b.c
    py -3.12 scripts/manage_users.py list
    py -3.12 scripts/manage_users.py passwd akash
    py -3.12 scripts/manage_users.py disable akash
    py -3.12 scripts/manage_users.py enable  akash
    py -3.12 scripts/manage_users.py delete  akash
    py -3.12 scripts/manage_users.py logout-all akash

OAuth sign-in (Google / LinkedIn / GitHub / Twitter-X):

    py -3.12 scripts/manage_users.py oauth-status
    py -3.12 scripts/manage_users.py links
    py -3.12 scripts/manage_users.py link   akash --provider twitter --subject 1234567890
    py -3.12 scripts/manage_users.py unlink akash --provider twitter

Google, LinkedIn and GitHub all report a VERIFIED email. On sign-in that
address either matches an existing account -- which then gets the provider's
permanent subject pinned to it, and is matched on that forever after -- or it
matches nobody and an account is created, metered against the SIGNUP budget
rather than the login throttle.

Twitter/X reports no email at any scope, so it has nothing to match on. It no
longer needs the `link` command: an unrecognised X identity is parked and the
person is asked to choose a username, which completes the sign-up. `link` stays
for the case the command was written for -- binding an X identity to an account
that already exists.

Two rules the resolution never bends:

    * An UNVERIFIED address is only a claim by whoever is signing in, and is
      refused. Matching on one would let anyone with a throwaway provider
      account walk into an existing account by typing its address.
    * A DISABLED account is refused, never re-provisioned. Creating a fresh
      one would hand back exactly the access that was withdrawn.

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
from api import oauth         # noqa: E402
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


# ── OAuth links ──────────────────────────────────────────────────────────────
# Google and LinkedIn link themselves on first sign-in, by matching a verified
# email to an existing account. Twitter/X cannot: it reports no email at any
# scope, so there is nothing to match on and it must be linked here by hand.

def cmd_link(a) -> int:
    if a.provider not in oauth.PROVIDERS:
        print(f"  unknown provider {a.provider!r}; "
              f"one of: {', '.join(sorted(oauth.PROVIDERS))}")
        return 1
    user = repo.get_user(a.username)
    if not user:
        print(f"  no such account: {a.username!r}")
        return 1
    subject = a.subject.strip()
    if not subject:
        print("  --subject is required: the provider's own id for that account")
        return 1

    existing = repo.identity_user(a.provider, subject)
    if existing:
        # Never silently re-point a link: whoever holds that provider account
        # would gain whichever local account was named last.
        print(f"  that {a.provider} account is already linked to "
              f"{existing.username!r}. Unlink it first.")
        return 1

    if not repo.link_identity(user.id, a.provider, subject, email=a.email or ""):
        print("  could not link (already linked?)")
        return 1
    print(f"  linked {a.provider}:{subject} -> {a.username!r}")
    return 0


def cmd_unlink(a) -> int:
    user = repo.get_user(a.username)
    if not user:
        print(f"  no such account: {a.username!r}")
        return 1
    n = repo.unlink_identity(user.id, a.provider)
    print(f"  removed {n} {a.provider} link(s) from {a.username!r}")
    return 0


def cmd_links(a) -> int:
    user = None
    if a.username:
        user = repo.get_user(a.username)
        if not user:
            print(f"  no such account: {a.username!r}")
            return 1
    rows = repo.list_identities(user.id if user else None)
    if not rows:
        print("  no OAuth accounts linked")
        return 0
    by_id = {u["id"]: u["username"] for u in repo.list_users()}
    print(f"  {'user':<18} {'provider':<10} {'subject':<28} last used")
    print("  " + "-" * 74)
    for r in rows:
        print(f"  {by_id.get(r.user_id, '?'):<18} {r.provider:<10} "
              f"{r.subject[:28]:<28} {r.last_used_at or '-'}")
    return 0


def cmd_oauth_status(a) -> int:
    """Which providers the server can actually use, and where to point them."""
    base = oauth.base_url()
    print(f"  public base URL: {base or '(unset -- set AUTOTRADER_PUBLIC_BASE_URL)'}")
    print()
    for key, p in oauth.PROVIDERS.items():
        cid, secret = oauth.credentials(key)
        state = "ready" if oauth.is_configured(key) else "NOT configured"
        missing = [n for n, v in (("CLIENT_ID", cid), ("CLIENT_SECRET", secret)) if not v]
        print(f"  {p.label:<10} {state}")
        if missing:
            for m in missing:
                print(f"             missing AUTOTRADER_{key.upper()}_{m}")
        print(f"             redirect URI: {oauth.redirect_uri(key)}")
        if not p.provides_email:
            print("             reports no email -- accounts must be linked with "
                  "`manage_users.py link`")
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

    lk = sub.add_parser("link", help="link a provider account to a local account")
    lk.add_argument("username")
    lk.add_argument("--provider", required=True,
                    choices=sorted(oauth.PROVIDERS), help="google, linkedin or twitter")
    lk.add_argument("--subject", required=True,
                    help="the provider's own id for that account")
    lk.add_argument("--email", default="", help="recorded for your reference only")
    lk.set_defaults(fn=cmd_link)

    ul = sub.add_parser("unlink", help="remove a provider link")
    ul.add_argument("username")
    ul.add_argument("--provider", required=True, choices=sorted(oauth.PROVIDERS))
    ul.set_defaults(fn=cmd_unlink)

    ls = sub.add_parser("links", help="show linked provider accounts")
    ls.add_argument("username", nargs="?", default="")
    ls.set_defaults(fn=cmd_links)

    sub.add_parser("oauth-status",
                   help="which providers are configured, and their redirect URIs"
                   ).set_defaults(fn=cmd_oauth_status)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
