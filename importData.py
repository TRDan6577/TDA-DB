#!/usr/bin/python3
# Author: Tom Daniels

#############
## Imports ##
#############
import configparser
import datetime
import gzip
import json
import logging
import logging.handlers
import os
import sqlite3
import sys
import tda
import time


######################
## Static Variables ##
######################
script_dir  = os.path.dirname(os.path.abspath(__file__))
script_name = os.path.basename(__file__)
log_dir     = os.path.join(script_dir, 'logs')
log_file    = os.path.join(log_dir, script_name.replace('.py', '.log'))
db_name     = os.path.join(script_dir, 'tda.sqlite')


#############################
## Import Custom Libraries ##
#############################
sys.path.append(os.path.join(script_dir, 'lib'))
import telegram
import tda_db
import tda_wrapper
import utility


###############
## Functions ##
###############
def rotator(source, dest):
    with open(source, 'rb') as source_file:
        with gzip.open(dest, 'wb') as zipped_file:
            zipped_file.write(source_file.read())
    os.remove(source)


def namer(name):
    return name + '.gz'


###########################
## The main() Attraction ##
###########################
def main():

    # Ensure logging directory exists
    if (not os.path.exists(log_dir)):
        os.mkdir(log_dir, mode=0o700)

    # Initalize debugging
    handler = logging.handlers.TimedRotatingFileHandler(log_file,when='W5',backupCount=8)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)-8s %(message)s'))
    handler.rotator = rotator
    handler.namer = namer
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    # Read config file
    config = configparser.ConfigParser()
    config.read('config.ini')

    # Set up messaging via Telegram
    logger.debug("Creating Telegram object")
    tel = telegram.Telegram(config['Telegram']['bot_id'], config['Telegram']['chat_id'])

    # Connect to the TD Ameritrade API
    logger.debug("Connecting to the TD Api and getting account positions")
    td = tda_wrapper.TDApi(config['TDAmeritrade']['td_token_path'], config['TDAmeritrade']['td_api_key_path'], tel=tel)

    # Connect to the database
    try:
        logging.debug("Connecting to the sqlite database (filename '{0}')".format(db_name))
        con    = sqlite3.connect(db_name)
        cursor = con.cursor()
    except Exception as e:
        tel.send_error_message("Unable to connect to the sqlite db file. Error: {0}".format(repr(e)))

    # If the database is empty, create the tables
    try:
        cursor.execute("SELECT * FROM SQLite_master;")
        if (not cursor.fetchall()):
            try:
                logger.warning("Database appears empty. Creating it...")
                tda_db.create_database(con, cursor)
            except Exception as e:
                tel.send_error_message("Unable to create the database. Error: {0}".format(repr(e)))
    except Exception as e:
        tel.send_error_message("Unable to look for tables in the database. Error: {0}".format(repr(e)))

    # Keep track of all the transactions we made and our current positions
    # so we can update the price history
    transactions = []
    position_symbols = set()

    # Go through each account looking at all the positions
    for account in td.get_accounts():
        logger.debug("Working on positions held in account ID {0}".format(account['account_id']))

        # Insert the account if it doesn't exist
        try:
            tda_db.insert_account(con, cursor, account['account_id'])
        except Exception as e:
            tel.send_error_message("Unable to insert account. Error: {0}".format(repr(e)))

        # Record the amount of cash in the account for later
        cash = account['cash_value']

        # Clear the positions table
        try:
            tda_db.clear_positions(con, cursor, account['account_id'])
        except Exception as e:
            tel.send_error_message("Unable to clear the positions table. Error: {0}".format(repr(e)))
        
        # Iterate through each position in the account adding new
        # transactions and prices to the DB as well as updating our
        # positions if we bought or sold anything
        for position in td.get_account_positions(account['account_id']):

            # Cash in IRA accounts is stored as a position
            if (position['instrument']['assetType'] == 'CASH_EQUIVALENT' and position['instrument']['symbol'] == 'MMDA1'):
                cash = position['longQuantity']
                continue
            
            # Make sure we're not dealing with unexpected asset types
            elif (position['instrument']['assetType'] != 'EQUITY'):
                tel.send_error_message("Database isn't configured for anything other than stocks. Encountered asset type of {0}".format(position['instrument']['assetType']))
                
            logger.debug("Working on symbol {0}".format(position['instrument']['symbol']))

            # Confirm that the ticker exists in the ticker table
            try:
                tda_db.insert_ticker(con, cursor, position['instrument']['symbol'])
            except Exception as e:
                tel.send_error_message("Unable to insert ticker. Error: {0}".format(repr(e)))

            # Insert our position into the database
            try:
                tda_db.insert_position(con, cursor, position, account['account_id'])
            except Exception as e:
                tel.send_error_message("Unable to update position. Error: {0}".format(repr(e)))


        # Insert the amount of cash for the account, faking the position dict.
        # This will, without a doubt, be a PITA to maintain if we update tda_db.insert_position.
        # Assumes the symbol  '$CASH$' was inserted when the DB was created
        try:
            position = { 'longQuantity': cash,
                         'averagePrice': 1.0,
                         'instrument': { 'assetType': 'CASH',
                                         'symbol':    '$CASH$' } }
            tda_db.insert_position(con, cursor, position, account['account_id'])
        except Exception as e:
            tel.send_error_message("Unable to update cash values. Error: {0}".format(repr(e)))

        # Get all the symbols of our current positions. We'll
        # use this to update the price history for each symbol below
        position_symbols = position_symbols | {position[1] for position in tda_db.get_positions(con, cursor, account_id=[account['account_id']])}

        # Record any transactions that took place in the account since
        # the last transaction if any positions were updated
        try:
            logger.debug("Updating the transactions table")
            cursor.execute("SELECT Date "
                           "FROM Transactions "
                           "WHERE AccountId = ? "
                           "ORDER BY Date DESC "
                           "LIMIT 1", [account['account_id']])
            last_trans_date = cursor.fetchall()

            # Get either all the transactions in the account since the last transaction
            # or all the transactions in the account over the lifetime of the account if Transactions table is empty
            if (len(last_trans_date) == 1):
                start_date = utility.from_epoch(last_trans_date[0][0])
                end_date   = datetime.datetime.now()
                logger.debug("Getting all transactions made since {0}".format(start_date))
            else:
                start_date = None
                end_date   = None
                logger.debug("Transactions table is empty. Getting all transactions over the lifetime of the account")

            # Update the transactions in the database
            transactions += tda_db.insert_transactions(con, cursor, td, account['account_id'], start_date=start_date, end_date=end_date)

        except Exception as e:
            tel.send_error_message("Unable to update account transactions. Error: {0}".format(repr(e)))


    # Update the price history for all symbols in the transactions
    # except our current positions. We want to handle those a bit differently
    try:
        logger.debug("Updating the price history for all recently imported transactions")
        for symbol in {tda_db.get_ticker_from_id(con, cursor, transaction[2]) for transaction in transactions}:
            logger.debug("Updating price history for {0}".format(symbol))
            if (symbol in position_symbols or symbol == '$CASH$'):
                logger.debug("Not updating {0} yet as we currently hold a position in it".format(symbol))
                continue

            # Set the end date to the date of the last transaction
            # since we don't currently have a position in the given symbol
            query = ("SELECT Transactions.Date AS Date "
                     "FROM Transactions "
                     "JOIN Tickers on Transactions.TickerId = Tickers.Id "
                     "WHERE Ticker = ? "
                     "ORDER BY Date DESC "
                     "LIMIT 1;")
            cursor.execute(query, [symbol])
            tda_db.update_price_history(con, cursor, td, symbol=symbol, end_date=utility.from_epoch(cursor.fetchall()[0][0]))
    except Exception as e:
        tel.send_error_message("Unable to update price history for the recent transactions. Error: {0}".format(repr(e)))

    # Update the price history for our current positions
    try:
        logger.debug("Updating price history for our current positions")
        for symbol in position_symbols:
            if (symbol == '$CASH$'):  # Ignore the fake symbol we created
                continue
            tda_db.update_price_history(con, cursor, td, symbol)
    except Exception as e:
        tel.send_error_message("Unable to update price history for our current positions. Error: {0}".format(repr(e)))


    logger.debug("Closing DB connection and exiting")
    con.close()
    return None


if (__name__ == "__main__"):
    main()
