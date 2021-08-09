#!/usr/bin/python3
# Author: Tom Daniels
# File: tda_db.py
# License: Mozilla Public License v2.0. See LICENSE file included with repository for more details

#############
## Imports ##
#############
import datetime
import dateutil
import logging
import json
import os
import sqlite3
import sys


#############################
## Import Custom Libraries ##
#############################
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import tda_wrapper
import utility


###############
## Functions ##
###############
def get_ticker_id(con, cursor, symbol):
    """
    Purpose: Gets the tickerID from the database for the given symbol
    @param con (Object) - sqlite DB connection object
    @param cursor (Object) - sqlite DB cursor object
    @param symbol (str) - the ticker symbol for the stock
    @return (int or None) - the ID if it exists in the database, None otherwise
    """

    # Set up logging
    logger = logging.getLogger()
    logger.debug("Entering get_ticker_id. Parameters are:\n\tsymbol: {0}".format(symbol))

    # Return the ID if it exists, None otherwise
    query = "SELECT * FROM Tickers WHERE Ticker = ?;"
    cursor.execute(query, [symbol])
    result = cursor.fetchall()
    if (result):
        return result[0][0]
    else:
        return None


def get_ticker_from_id(con, cursor, ticker_id):
    """
    Purpose: Gets the ticker symbol from the database for the given ticker DB ID
    @param con (Object) - sqlite DB connection object
    @param cursor (Object) - sqlite DB cursor object
    @param ticker_id (int) - the id of the ticker
    @return (str or None) - the symbol that maps to the ticker ID
            or None if it doesn't exist
    """

    # Set up logging
    logger = logging.getLogger()
    logger.debug("Entering get_ticker_from_id. Parameters are:\n\tticker_id: {0}".format(ticker_id))

    # Return the ticker symbol if it exists, None otherwise
    query = "SELECT * FROM Tickers WHERE Id = ?;"
    cursor.execute(query, [ticker_id])
    result = cursor.fetchall()
    if (result):
        return result[0][1]
    else:
        return None


def create_database(con, cursor):
    """
    Purpose: Creates the DB file and the schema
    @param con (Object) - sqlite DB connection object
    @param cursor (Object) - sqlite DB cursor object
    @return (None)
    """

    # Set up logging
    logger = logging.getLogger()
    logger.debug("Entering create_database")

    
    logger.debug("Creating Tickers table")
    cursor.execute("CREATE TABLE Tickers (Id INTEGER PRIMARY KEY, "
                   "Ticker TEXT NOT NULL);")
    con.commit()

    logger.debug("Creating Accounts table")
    cursor.execute("CREATE TABLE Accounts (AccountId INTEGER PRIMARY KEY, "
                   "AccountName TEXT);")
    con.commit()

    logger.debug("Creating Prices table")
    cursor.execute("CREATE TABLE Prices (TickerId INTEGER NOT NULL, "
                   "Date INTEGER NOT NULL, "
                   "Open REAL NOT NULL, "
                   "Close REAL NOT NULL, "
                   "High REAL NOT NULL, "
                   "Low REAL NOT NULL, "
                   "Volume INTEGER NOT NULL, "
                   "PRIMARY KEY (TickerId, Date), " 
                   "FOREIGN KEY (TickerId) REFERENCES Tickers(Id));")
    con.commit()
    
    logger.debug("Creating Transactions table")
    cursor.execute("CREATE TABLE Transactions (Id INTEGER PRIMARY KEY, "
                   "AccountId INTEGER NOT NULL, "
                   "TickerId INTEGER NOT NULL, "
                   "Date INTEGER NOT NULL, "
                   "Quantity REAL NOT NULL, "
                   "Price REAL NOT NULL, "
                   "Total REAL NOT NULL, "
                   "Description TEXT, "
                   "FOREIGN KEY (AccountId) REFERENCES Accounts(AccountId), "
                   "FOREIGN KEY (TickerId) REFERENCES Tickers(Id));")
    con.commit()

    logger.debug("Creating Positions table")
    cursor.execute("CREATE TABLE Positions (AccountId INTEGER NOT NULL, "
                   "TickerId INTEGER NOT NULL, "
                   "Instrument TEXT NOT NULL, "
                   "Cost REAL NOT NULL, "
                   "Quantity REAL NOT NULL, "
                   "PRIMARY KEY (AccountId, TickerId), "
                   "FOREIGN KEY (AccountId) REFERENCES Accounts(AccountId), "
                   "FOREIGN KEY (TickerId) REFERENCES Tickers(Id)); ")
    con.commit()

    logger.debug("Creating the cash ticker")
    cursor.execute("INSERT INTO Tickers (Ticker) VALUES ('$CASH$');")
    con.commit()

    logger.debug("Created database")
    return None


def insert_account(con, cursor, account_id):
    """
    Purpose: Inserts the account into the account table if it doesn't
             already exist
    @param con (Object) - sqlite DB connection object
    @param cursor (Object) - sqlite DB cursor object
    @param account_id (str) - the new TD account
    @return (None)
    """
    
    # Set up logging
    logger = logging.getLogger()
    logger.debug("Entering insert_account. Parameters are:\n\taccount_id: {0}".format(account_id))

    # Does it exist already?
    logger.debug("Checking to see if the account exists in the DB")
    query = "SELECT * FROM Accounts WHERE AccountId = ?;"
    cursor.execute(query, [account_id])
    if (not cursor.fetchall()):
        logger.debug("No results from DB. Inserting account")
        cursor.execute("INSERT INTO Accounts (AccountId) VALUES (?);", [account_id])
        con.commit()
        logger.debug("Account inserted")
    else:
        logger.debug("Account already existed")

    return None


def insert_ticker(con, cursor, symbol):
    """
    Purpose: Inserts the symbol into the ticker table if it doesn't
             already exist
    @param con (Object) - sqlite DB connection object
    @param cursor (Object) - sqlite DB cursor object
    @param symbol (str) - the ticker symbol for the stock
    @return (bool) True if the symbol was inserted, False otherwise
    """
    
    # Set up logging
    logger = logging.getLogger()
    logger.debug("Entering insert_ticker. Parameters are:\n\tsymbol: {0}".format(symbol))

    # Does it exist already?
    logger.debug("Checking to see if the symbol exists in the DB")
    ticker_id = get_ticker_id(con, cursor, symbol)

    # If not, add it, otherwise, return
    if (not ticker_id):
        logger.debug("No results from DB. Inserting symbol")
        cursor.execute("INSERT INTO Tickers (Ticker) VALUES (?);", [symbol])
        con.commit()
        logger.debug("Symbol inserted")
        symbol_added = True
    else:
        logger.debug("Symbol already existed")
        symbol_added = False

    return symbol_added


def get_positions(con, cursor, account_id=None, symbol=None):
    """
    Purpose: Gets the current position or positions specified from the database
    @param con (Object) - sqlite DB connection object
    @param cursor (Object) - sqlite DB cursor object
    @param account_id (list) - the account(s) to get the positions for
    @param symbol (list) - the symbol(s) to get the positions for
    @return (list) the positions
    """

    # Set up logging
    logger = logging.getLogger()
    logger.debug("Entering get_positions. Parameters are:\n\taccount_id: {0}\n\tsymbol: {1}".format(account_id, symbol))

    # Build the query
    query = ("SELECT AccountId, Tickers.Ticker, Instrument, Cost, Quantity "
             "FROM Positions "
             "JOIN Tickers ON Positions.TickerId = Tickers.Id "
             "WHERE 1=1 ")
    args = []
    if (account_id):
        query += "AND AccountId IN (?" + ((len(account_id)-1) * ", ?") + ") "
        args += account_id
    if (symbol):
        query += "AND Tickers.Ticker IN (?" + ((len(symbol)-1) * ", ?") + ") "
        args += symbol

    # Execute the query and return the results
    logger.debug("Executing query: {0}\nWith args: {1}".format(query, args))
    cursor.execute(query, args)
    return cursor.fetchall()


def update_price_history(con, cursor, td, symbol, start_date=None, end_date=None):
    """
    Purpose: Updates the price history for a stock in the sqlite database
    @param con (Object) - sqlite DB connection object
    @param cursor (Object) - sqlite DB cursor object
    @param td (Object) - TD Ameritrade wrapper object
    @param symbol (str) - the ticker symbol for the stock
    @param start_date (datetime) - the first day to get price history for. If
           unspecified, this is the last 30 days
    @param end_date (datetime) - the last day to get price history for
    @return (None)
    """

    # Set up logging
    logger = logging.getLogger()
    logger.debug("Entering update_price_history. Parameters are:\n\tsymbol: {0}\n\tstart_date: {1}\n\tend_date: {2}".format(symbol, start_date, end_date))

    # If no start date is provided, base the start date off of the most recent
    # price point in the DB. If no prior history, base it off of the oldest
    # transaction for the given symbol
    if (start_date == None):

        # Get the latest price history entry for the stock in our DB
        logger.debug("Excuting SQLite query")
        query = ("SELECT Prices.Date AS Date "
                 "FROM Prices "
                 "JOIN Tickers ON Prices.TickerId = Tickers.Id "
                 "WHERE Ticker = ? "
                 "ORDER BY Date DESC "
                 "LIMIT 1;")
        cursor.execute(query, [symbol])
        price_history_db = cursor.fetchall()

        # If we have no price history, then set the start date to the
        # earliest transaction date
        if (not price_history_db):
            logger.debug("No price history. Fetching earliest transaction date")
            query = ("SELECT Transactions.Date AS Date "
                     "FROM Transactions "
                     "JOIN Tickers on Transactions.TickerId = Tickers.Id "
                     "WHERE Ticker = ? "
                     "ORDER BY Date ASC "
                     "LIMIT 1;")
            cursor.execute(query, [symbol])
            last_entry_db = cursor.fetchall()[0][0]
        else:
            last_entry_db = price_history_db[0][0] + 86400  # the start date should be 1 day after the last in the DB
        logger.debug("Retrieving prices for {0} starting from {1}".format(symbol, utility.from_epoch(last_entry_db)))

        # Get all the prices from the API since the latest price data, if it exists
        if (last_entry_db != 0):
            start_date = datetime.datetime(*utility.from_epoch(last_entry_db).timetuple()[:3])  # truncates to yyyy-mm-dd
        # If the start_date is still unset, default to last 30 days
        else:
            start_date = datetime.datetime.now() + datetime.timedelta(days=-31)

    # Get the price history for the past month from TD
    price_history_td = td.get_price_history(symbol, start_date=start_date, end_date=end_date)

    # Get the ticker ID from the SQL database
    cursor.execute("SELECT Id FROM Tickers WHERE Ticker = ?;", [symbol])
    ticker_id = cursor.fetchall()
    assert ticker_id, "No ticker ID for symbol {0}".format(symbol)
    ticker_id = ticker_id[0][0]

    # Gather new price points
    insertion_data = []
    for day in price_history_td:
        date = int(str(day['datetime'])[:-3])  # Truncate the milliseconds off of the time
        insertion_data.append((ticker_id, date, day['open'], day['close'], day['high'], day['low'], day['volume']))
    
    # Bulk insert the new data
    logger.debug("Inserting new data: {0}".format(insertion_data))
    insertion = ("INSERT INTO Prices (TickerId, Date, Open, Close, High, Low, Volume)"
                 "VALUES (?, ?, ?, ?, ?, ?, ?);")
    cursor.executemany(insertion, insertion_data)
    con.commit()

    logger.debug("Inserted new data")
    return None


def insert_position(con, cursor, position, account_id):
    """
    Purpose: Records a position we hold in the Positions table
    @param con (Object) - sqlite DB connection object
    @param cursor (Object) - sqlite DB cursor object
    @param position (dict) - the position as returned by the TD Ameritrade API
    @param account_id (str) - the account to which the position belongs
    @return (bool) - True if the position was updated, False otherwise
    """

    # Set up logging
    logger = logging.getLogger()
    logger.debug("Entering insert_position. Parameters are:\n\tposition: {0}\n\taccount_id: {1}".format(position, account_id))

    assert position['longQuantity'] != 0.0, "We have a non-long position. The DB might not be set up to handle this"

    instrument = position['instrument']['assetType']
    ticker     = position['instrument']['symbol']
    quantity   = position['longQuantity']
    cost       = position['averagePrice']
    ticker_id  = get_ticker_id(con, cursor, ticker)
    insertion  = ("INSERT INTO Positions (AccountId, TickerId, Instrument, Cost, Quantity) "
                 "VALUES (?, ?, ?, ?, ?)")
    cursor.execute(insertion, [account_id, ticker_id, instrument, cost, quantity])
    con.commit()

    logger.debug("Done inserting ticker {0}".format(ticker))
    return None


def clear_positions(con, cursor, account_id):
    """
    Purpose: Deletes all recorded positions for the given account ID
    @param con (Object) - sqlite DB connection object
    @param cursor (Object) - sqlite DB cursor object
    @param account_id (str) - the account id to clear the positions for
    """

    # Set up logging
    logger = logging.getLogger()
    logger.debug("Entering clear_positions. Parameters are:\n\taccount_id: {0}".format(account_id))

    query = ("DELETE "
             "FROM Positions "
             "WHERE AccountId = ?;")
    cursor.execute(query, [account_id])

    logger.debug("Cleared positions")
    return None


def insert_transactions(con, cursor, td, account_id, symbol=None, start_date=None, end_date=None):
    """
    Purpose: Inserts all transactions that took place in the given account
             during the given time period
    @param con (Object) - sqlite DB connection object
    @param cursor (Object) - sqlite DB cursor object
    @param td (Object) - TD Ameritrade wrapper object
    @param account_id (str) - the account id to retrieve the transactions for
    @param start_date (datetime) - retrieve transactions on or after this date and time
    @param end_date (datetime) - retrieve transactions up until this time
    @return (list) a list of tuples containing the latest transactions
    """

    # Set up logging
    logger = logging.getLogger()
    logger.debug("Entering insert_transaction. Parameters are:\n\taccount_id: {0}\n\tstart_date: {1}\n\tend_date: {2}".format(account_id, start_date, end_date))

    # Transaction type validation
    IGNORED_TRANSACTIONS = ['JOURNAL', 'CASH_RECEIPT']
    KNOWN_TRANSACTIONS   = ['TRADE', 'ELECTRONIC_FUND', 'DIVIDEND_OR_INTEREST', 'RECEIVE_AND_DELIVER']
    KNOWN_ASSET_TYPES    = ['EQUITY', 'CASH_EQUIVALENT']

    # Get the transactions from the TD API
    transactions = td.get_transactions(account_id, symbol=symbol, start_date=start_date, end_date=end_date)

    # Get a list of transactions from the DB to ensure no duplicates are entered
    query = ("SELECT Id FROM Transactions")
    cursor.execute(query)
    existing_transactions = [item[0] for item in cursor.fetchall()]

    # Insert each into the database
    insertion_data = []
    new_symbols    = []
    for transaction in transactions:

        logger.debug("Working on transactions id {0} of type {1}".format(transaction['transactionId'], transaction['type']))
        
        # ... but only after we ignore certain types
        if (transaction['type'] in IGNORED_TRANSACTIONS):
            logger.warning("Ignoring transaction id {0} of type {1}".format(transaction['transactionId'], transaction['type']))
            continue

        # And we validate that we're not inserting a duplicate
        if (transaction['transactionId'] in existing_transactions):
            logger.warning("Ignoring transaction id {0} because it already exists in the DB".format(transaction['transactionId']))
            continue

        # And we're scared of the unknown
        assert (transaction['type'] in KNOWN_TRANSACTIONS), "Encountered unknown type of transaction '{0}' in transaction id {1}".format(transaction['type'], transaction['transactionId'])
        if (transaction['type'] != 'ELECTRONIC_FUND' and transaction['description'] != 'FREE BALANCE INTEREST ADJUSTMENT'):
            assert (transaction['transactionItem']['instrument']['assetType'] in KNOWN_ASSET_TYPES), "Encountered unknown asset type '{0}' in transaction id {1}".format(transaction['transactionItem']['instrument']['assetType'], transaction['transactionId'])

        # Prepare the transaction(s) for insertion

        # Dividends
        if (transaction['type'] == 'DIVIDEND_OR_INTEREST'):
            if (transaction['description'] == 'FREE BALANCE INTEREST ADJUSTMENT'):
                symbol = '$CASH$'
            else:
                symbol = transaction['transactionItem']['instrument']['symbol']
            # Add the symbol if it doesn't already exist
            insert_ticker(con, cursor, symbol)
            insertion_data.append((transaction['transactionId'], account_id, 
                                   get_ticker_id(con, cursor, symbol),
                                   int((dateutil.parser.parse(transaction['transactionDate'])).timestamp()),
                                   0, 0, transaction['netAmount'], transaction['description']))

        # Money deposit
        elif (transaction['type'] == 'ELECTRONIC_FUND'):
            insertion_data.append((transaction['transactionId'], account_id,
                                   get_ticker_id(con, cursor, '$CASH$'),
                                   int((dateutil.parser.parse(transaction['transactionDate'])).timestamp()),
                                   0, 0, transaction['netAmount'], transaction['description']))

        # Transfer of securities and options
        elif (transaction['type'] == 'RECEIVE_AND_DELIVER'):
            # Money deposit from another account
            if (transaction['transactionItem']['instrument']['assetType'] == 'CASH_EQUIVALENT'):
                insertion_data.append((transaction['transactionId'], account_id,
                                       get_ticker_id(con, cursor, '$CASH$'),
                                       int((dateutil.parser.parse(transaction['transactionDate'])).timestamp()),
                                       0, 0, transaction['transactionItem']['amount'], transaction['description']))
            # Security or option from another account
            else:
                insertion_data.append((transaction['transactionId'], account_id,
                                       get_ticker_id(con, cursor, transaction['transactionItem']['instrument']['symbol']),
                                       int((dateutil.parser.parse(transaction['transactionDate'])).timestamp()),
                                       transaction['transactionItem']['amount'], 0.0,
                                       transaction['netAmount'], transaction['description']))

        # Buy or Sell
        elif (transaction['type'] == 'TRADE'):
            # Add the symbol if it doesn't already exist
            insert_ticker(con, cursor, transaction['transactionItem']['instrument']['symbol'])
            insertion_data.append((transaction['transactionId'], account_id,
                                   get_ticker_id(con, cursor, transaction['transactionItem']['instrument']['symbol']),
                                   int((dateutil.parser.parse(transaction['transactionDate'])).timestamp()),
                                   transaction['transactionItem']['amount'], transaction['transactionItem']['price'],
                                   transaction['netAmount'], transaction['description']))


    # Insert the transactions into the DB
    insertion = ("INSERT INTO Transactions (Id, AccountId, TickerId, Date, Quantity, Price, Total, Description) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
    cursor.executemany(insertion, insertion_data)
    con.commit()

    return insertion_data
