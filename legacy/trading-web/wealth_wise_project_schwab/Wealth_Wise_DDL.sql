-- Drop existing tables if needed
DROP TABLE IF EXISTS trades;
DROP TABLE IF EXISTS bots;
DROP TABLE IF EXISTS customer_details;

-- 1. Customer Details Table
CREATE TABLE customer_details (
    customer_id SERIAL PRIMARY KEY,
    customer_name VARCHAR(255) UNIQUE NOT NULL,
    street VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    country VARCHAR(100) NOT NULL,
    postal_code VARCHAR(20) NOT NULL,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    api_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2. Bots Table (Updated)
CREATE TABLE bots (
    bot_id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customer_details(customer_id) ON DELETE CASCADE,
    bot_name VARCHAR(255) NOT NULL,
    status VARCHAR(10) CHECK (status IN ('STOPPED', 'RUNNING')) NOT NULL DEFAULT 'STOPPED',
    live_trading BOOLEAN DEFAULT FALSE,
    enable_trade_buying BOOLEAN DEFAULT TRUE,
    enable_trade_shorting BOOLEAN DEFAULT TRUE,
    symbol_ironbeam VARCHAR(50) NOT NULL,  -- Ironbeam Symbol
    symbol_schwab VARCHAR(50) NOT NULL,   -- Schwab Symbol
    lot_size INT CHECK (lot_size > 0) NOT NULL,
    current_trade_status VARCHAR(10) CHECK (current_trade_status IN ('BUY', 'SELL', 'NONE')) NOT NULL DEFAULT 'NONE',
    current_bot_trade_status VARCHAR(10) CHECK (current_trade_status IN ('BUY', 'SELL', 'NONE')) NOT NULL DEFAULT 'NONE',
    strategy VARCHAR(20) CHECK (strategy IN ('Strategy_One', 'Strategy_Two')) NOT NULL DEFAULT 'Strategy_One',
    stop_loss_adjust DECIMAL(10, 2) DEFAULT 0.00,  -- New Column for Stop Loss Adjustment
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (customer_id, bot_name)
);



-- 3. Trades Table
CREATE TABLE trades (
    trade_id SERIAL PRIMARY KEY,
    bot_id INT REFERENCES bots(bot_id) ON DELETE CASCADE,
    symbol VARCHAR(50) NOT NULL,
    lot_size INT CHECK (lot_size > 0) NOT NULL,
    trade_type VARCHAR(10) CHECK (trade_type IN ('BUY', 'SELL')) NOT NULL,
    price DECIMAL(18,8) NOT NULL,
    status VARCHAR(50) CHECK (status IN ('PENDING', 'EXECUTED', 'FAILED', 'CANCELLED')) NOT NULL DEFAULT 'PENDING',
    executed_at TIMESTAMP DEFAULT NOW()
);


-- Grant full privileges on the database
GRANT ALL PRIVILEGES ON DATABASE wealth_wise TO wealth_user;

-- Grant full privileges on all tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO wealth_user;

-- Grant privileges on sequences (for AUTO_INCREMENT columns)
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO wealth_user;

-- Grant usage and creation privileges on schema
GRANT USAGE, CREATE ON SCHEMA public TO wealth_user;

-- Change the schema owner
ALTER SCHEMA public OWNER TO wealth_user;


ALTER TABLE bots MODIFY strategy VARCHAR(20) NOT NULL DEFAULT 'Strategy_One';
