# reset_bot_state.py

from app import app, db, Bot   # adjust if Bot is in a different module

def reset_bots():
    with app.app_context():
        # Reset all bots to safe defaults
        db.session.query(Bot).update(
            {
                Bot.live_trading: False,                 # Live Trading -> No
                Bot.current_trade_status: "NONE",        # Current Trade
                Bot.current_bot_trade_status: "NONE",    # Current Bot Trade Status
                Bot.status: "STOPPED",                   # Status
            }
        )
        db.session.commit()
        print("✅ All bots reset to default safe state")

if __name__ == "__main__":
    reset_bots()
