"""Housekeeping for AutoTrader accounts.

Sign-in was removed on 2026-10-16: the app opens straight from its link and
every request runs as one workspace account (db.users.workspace_user -- the
owner account when there is one). So there is nothing here to log in WITH any
more -- no passwords, sessions, verification or OAuth links -- and the
commands that managed them are gone with them.

What is left is housekeeping over the accounts table, which still exists:
saved configurations, backtests and the paper session are keyed on it.

    py -3.12 scripts/manage_users.py list
    py -3.12 scripts/manage_users.py disable akash
    py -3.12 scripts/manage_users.py enable  akash
    py -3.12 scripts/manage_users.py delete  akash

Disabling the owner account moves the workspace to the next active account --
which does not hold the Schwab entitlement, so live data would stop.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import backtests      # noqa: E402
from db import users as repo  # noqa: E402



def cmd_list(a) -> int:
    rows = repo.list_users()
    if not rows:
        print("  no accounts yet -- one is created the first time the app is opened")
        return 0
    print(f"  {'id':>3}  {'username':<18} {'active':<7} {'created':<20} last login")
    print("  " + "-" * 74)
    for r in rows:
        print(f"  {r['id']:>3}  {r['username']:<18} "
              f"{'yes' if r['is_active'] else 'NO':<7} {r['created_at']:<20} "
              f"{r['last_login_at'] or '-'}")
    return 0


def cmd_disable(a) -> int:
    if not repo.set_active(a.username, False):
        print(f"  no such account: {a.username!r}")
        return 1
    print(f"  {a.username!r} disabled")
    return 0


def cmd_enable(a) -> int:
    if not repo.set_active(a.username, True):
        print(f"  no such account: {a.username!r}")
        return 1
    print(f"  {a.username!r} enabled")
    return 0


def cmd_delete(a) -> int:
    """Close an account. Its backtests go with it unless --keep-results says otherwise.

    This used to call repo.delete_user, which deletes the users row and nothing
    else -- and SQLite refused it outright for anyone who had ever run a
    backtest, because backtests.user_id references that row with no ON DELETE
    action. The command therefore worked only on accounts that had not used the
    product. It now goes through repo.delete_account, which deals with the
    dependents first.
    """
    user = repo.get_user(a.username)
    if not user:
        print(f"  no such account: {a.username!r}")
        return 1

    owned = len(backtests.list_ids(user.id))
    fate = ("kept, detached from the account" if a.keep_results
            else "DELETED along with their trades")
    print(f"  {a.username!r} owns {owned} backtest(s) -- they will be {fate}.")
    if input(f"  close {a.username!r}? [y/N] ").lower() != "y":
        print("  cancelled")
        return 1

    removed = repo.delete_account(user.id, keep_results=a.keep_results)
    if removed is None:
        print(f"  no such account: {a.username!r}")
        return 1

    backtests.purge_blobs(removed["backtest_ids"])
    print(f"  closed {a.username!r} "
          f"(backtests removed={removed['backtests']} "
          f"detached={removed['backtests_detached']} "
          f"trades={removed['trades']} sessions={removed['sessions']})")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list accounts").set_defaults(fn=cmd_list)

    for name, fn, helptext in [
        ("disable", cmd_disable, "disable an account"),
        ("enable", cmd_enable, "re-enable an account"),
    ]:
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("username")
        sp.set_defaults(fn=fn)

    dl = sub.add_parser("delete", help="close an account and remove its data")
    dl.add_argument("username")
    dl.add_argument("--keep-results", action="store_true",
                    help="detach the backtests instead of deleting them "
                         "(they become unreachable -- every read is scoped by "
                         "owner -- but the rows survive for the operator)")
    dl.set_defaults(fn=cmd_delete)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
