-- Create the coffee table
CREATE TABLE coffee (
    coffee_id SERIAL PRIMARY KEY,
    coffee_name VARCHAR(100) UNIQUE
);

-- Create the transactions table with a foreign key to coffee
CREATE TABLE transactions (
    transaction_id SERIAL PRIMARY KEY,
    datetime TIMESTAMP NOT NULL,
    cash_type VARCHAR(10),
    card VARCHAR(50),
    money DECIMAL(10, 2),
    coffee_id INT,
    FOREIGN KEY (coffee_id) REFERENCES coffee(coffee_id)
);

CREATE TEMP TABLE staging_sales (
    date DATE,
    datetime TIMESTAMP,
    cash_type VARCHAR(10),
    card VARCHAR(50),
    money DECIMAL(10, 2),
    coffee_name VARCHAR(100)
);

-- Adjust path to your CSV file as needed
COPY staging_sales FROM 'coffee_sales.csv' DELIMITER ',' CSV HEADER;

INSERT INTO coffee (coffee_name)
SELECT DISTINCT coffee_name
FROM staging_sales
WHERE coffee_name IS NOT NULL;

INSERT INTO transactions (datetime, cash_type, card, money, coffee_id)
SELECT 
    s.datetime,
    s.cash_type,
    s.card,
    s.money,
    c.coffee_id
FROM staging_sales s
JOIN coffee c ON s.coffee_name = c.coffee_name;


-- Create a read-only user
CREATE USER readonly_user WITH PASSWORD 'coffeesales';
GRANT CONNECT ON DATABASE coffeesales TO readonly_user;

-- Grant usage on schema
GRANT USAGE ON SCHEMA public TO readonly_user;

-- Grant SELECT on all tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;

-- Future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO readonly_user;

select * from transactions;
select * from coffee;
