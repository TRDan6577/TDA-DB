#!/usr/bin/python3
# Author: Tom Daniels
# Requires logging to be set up
# File: tda_wrapper.py
# License: Mozilla Public License v2.0. See LICENSE file included with repository for more details

#############
## Imports ##
#############
import datetime
import dateutil
import json
import logging
import os
import requests
import sys
import tda
import time


###############
## Functions ##
###############
def _refresh_auth_code(token_path, api_key, tel=None):
    """
    Purpose: Refreshes the OAuth token. This must be outside of the class
             definition otherwise name mangling occurs
    @param token_path (str) - the path to the OAuth token on disk
    @param api_key (str) - the TDAmeritrade API key
    @param tel (Telegram) - a Telegram object used to send messages
    @return (None) - nothing. Updates the token on disk
    """

    # Load the data from the token file
    token_data = tda.auth.__token_loader(token_path)()

    # Build the HTTP body
    body = {
        'grant_type':    'refresh_token',
        'refresh_token':  token_data['refresh_token'],
        'client_id':      api_key
    }

    # Make the request
    try:
        uri = 'https://api.tdameritrade.com/v1/oauth2/token'
        response = requests.post(uri, data=body)
        assert response.ok, "Encountered an error while attempting to refresh the OAuth token. \nStatus code: {0}\nError message: {1}".format(response.status_code, response.text)
    except Exception as e:
        if (tel):
            tel.send_error_message("Error refreshing the auth token: '{0}'".format(repr(e)))
        else:
            raise e

    # Update fields in the token file and write it back out to disk
    new_token_data = json.loads(response.text)
    epoch_time = int(time.time())
    token_data['access_token'] = new_token_data['access_token']
    token_data['scope']        = new_token_data['scope']
    token_data['expires_in']   = new_token_data['expires_in']
    token_data['token_type']   = new_token_data['token_type']
    token_data['expires_at']   = new_token_data['expires_in'] + epoch_time
    tda.auth.__update_token(token_path)(token_data)


#############
## Classes ##
#############
class TdTokenError(Exception):
    pass


class TDApi:

    def __init__(self, token_path, api_key_path, tel=None):
        """
        Purpose: Initializes the OAuth token
        @param self (Object) - reference to current instance of the class
        @param token_path (String) - path to the OAuth2 TDAmeritrade token on disk
        @param api_key_apth (String) - path to the TDAmeritrade API key on disk
        @param tel (Telegram) - a Telegram object used to send errors and other messages
        """
        # Whether or not to use Telegram to send errors
        self.__tel = tel

        # Set the TDAmeritrade variables
        assert (os.path.exists(os.path.expanduser(token_path))), 'Error, token path does not exist'
        assert (os.path.exists(os.path.expanduser(api_key_path))), 'Error, API key path does not exist'
        self.__token_path = os.path.expanduser(token_path)
        with open(os.path.expanduser(api_key_path), 'r') as f:
            self.__api_key = f.read()

        # Set up the OAuth token
        self.refresh_auth_code()


    def refresh_auth_code(self):
        """
        Purpose: Updates the OAuth token
        """
        # Refresh the authorization token
        _refresh_auth_code(self.__token_path, self.__api_key, self.__tel)

        # Set the client object
        self._client = tda.auth.client_from_token_file(self.__token_path, self.__api_key)


    def __catch_error(self, e, error_message):
        """
        Purpose: Logs the error, then either raises it or sends it to telegram if
                 self.tel is True
        @param self (object) - instance of the current class
        @param e (Exception) - the Exception that was raised
        @param error_message (str) - a string describing the error
        @return (None) - this function either ends with exit() or raises an error
        """

        # Set up logging to log the error
        logger = logging.getLogger()
        logger.error(error_message)

        # Send the error notification or fail
        if ('token_invalid' in repr(e)):
            raise TdTokenError
        elif (self.__tel):
            self.__tel.send_error_message(error_message)
        else:
            raise e


    def get_accounts(self):
        """
        Purpose: Gets the accounts available via the API and the
                 liquidation value of each (for some extra context
        @return (list) - a list of dictionaries containing account_id, liquidation, and cash values
        """
        
        # Set up debugging for the function
        logger = logging.getLogger()
        logger.debug("Entering get_accounts")

        # Get the accounts
        try:
            response = self._client.get_accounts()
            assert response.status_code == 200, "Response from TD API was status code {0}".format(response.status_code)
        except Exception as e:
            self.__catch_error(e, "Error retrieving the accounts. Error: '{0}'".format(repr(e)))

        # Perform validation to make sure everything is as expected in the json
        try:
            accounts = []
            for account in response.json():
                accounts.append( { 'account_id' : account['securitiesAccount']['accountId'],
                                   'liquidation_value' : account['securitiesAccount']['currentBalances']['liquidationValue'],
                                   'cash_value' : account['securitiesAccount']['currentBalances']['cashBalance'] })
        except Exception as e:
            self.__catch_error(e, "Unexpected error while parsing the JSON returned by the API: {0}".format(repr(e)))

        # Return the balance
        logger.debug("Successfully retrieved accounts")
        return accounts


    def get_liquidation_value(self, account_id):
        """
        Purpose: Gets the liquidation value of the specified account
        @param self (Object) - instance of current class
        @param account_id (str) - the ID of the TD Ameritrade account to use
        @return (float) - the liquidation value of the specified account
        """
        
        # Set up debugging for the function
        logger = logging.getLogger()
        logger.debug("Entering get_liquidation_value. Parameters are:\n\taccount_id: {0}".format(account_id))

        # Get the account balance
        try:
            response = self._client.get_account(account_id)
            assert response.status_code == 200, "Response from TD API was status code {0}".format(response.status_code)
        except Exception as e:
            self.__catch_error(e, "Error retrieving total account balance. Error: '{0}'".format(repr(e)))

        # Perform validation to make sure everything is as expected in the json
        try:
            account = response.json()
            assert account['securitiesAccount']['currentBalances']['liquidationValue'], "JSON returned from API doesn't contain the liquidation value"
            total_value = account['securitiesAccount']['currentBalances']['liquidationValue']
        except Exception as e:
            self.__catch_error(e, "Unexpected error while parsing the JSON returned by the API: {0}".format(repr(e)))

        # Return the balance
        logger.debug("Account has total balance of ${0}".format(total_value))
        return total_value


    def get_cash_balance(self, account_id):
        """
        Purpose: Gets the amount of unused cash in the specified account
        @param self (Object) - an instance of the class
        @param account_id (str) - the ID of the TD Ameritrade account to use
        @return (float) - the current amount of unused cash in the specified account
        """

        # Set up debugging for the function
        logger = logging.getLogger()
        logger.debug("Entering get_cash_balance. Parameters are:\n\taccount_id: {0}".format(account_id))

        # Get the account balance
        try:
            response = self._client.get_account(account_id)
            assert response.status_code == 200, "Response from TD API was status code {0}".format(response.status_code)
        except Exception as e:
            self.__catch_error(e, "Error retrieving account balance. Error: '{0}'".format(repr(e)))

        # Perform validation to make sure everything is as expected in the json
        try:
            account = response.json()
            assert account['securitiesAccount']['currentBalances']['cashAvailableForTrading'], "JSON returned from API doesn't contain the expected properties"
            cash_balance = account['securitiesAccount']['currentBalances']['cashAvailableForTrading']
        except Exception as e:
            self.__catch_error(e, "Unexpected error while parsing the JSON returned by the API: {0}".format(repr(e)))

        # Return the balance
        logger.debug("Account has cash balance of ${0}".format(cash_balance))
        return cash_balance


    def get_price_history(self, ticker, start_date=(datetime.datetime.now() + datetime.timedelta(days=-31)), end_date=None):
        """
        Purpose: Gets the candle price history of a particular stock for the past month
        @param self (Object) - an instance of the current class
        @param ticker (str) - the ticker symbol of a stock (ex: AAPL)
        @param start_date (datetime) - the beginning date to get prices for. Defaults to 30 days ago
        @param end_date (datetime) - the end date to get prices for. Defaults to last trading day
        @return (list) - a list of dictionaries, each continaing the date, volume, open, close
                         high, and low prices of the ticker for a given day
        """

        # Set up debugging for the function
        logger = logging.getLogger()
        logger.debug("Entering get_price_history. Parameters are:\n\tticker: {0}\n\tstart_date: {1}\n\tend_date: {2}".format(ticker, start_date, end_date))

        # Initialize the variables for the API call
        frequency_type = self._client.PriceHistory.FrequencyType.DAILY
        frequency      = self._client.PriceHistory.Frequency.DAILY
        period_type    = self._client.PriceHistory.PeriodType.MONTH

        # If unset, set end_date to today (provided it's past 4 PM)
        if (not end_date and datetime.datetime.now().hour >= 16):
            end_date = datetime.datetime.now()

        # Get the price history
        try:
            response = self._client.get_price_history(ticker, frequency_type=frequency_type,
                                                      frequency=frequency, period_type=period_type,
                                                      start_datetime=start_date, end_datetime=end_date)
            assert response.status_code == 200, "Response from the TD API was status code {0}".format(response.status_code)
        except Exception as e:
            self.__catch_error(e, "Error retrieving the price history. Error: '{0}'".format(repr(e)))

        logger.debug("Successfully retrieved price history for '{0}'".format(ticker))
        return response.json()['candles']


    def get_account_positions(self, account_id):
        """
        Purpose: Gets all of the position information in a specified account.
                 This includes average buy price of a ticker, market value,
                 price paid, etc
        @param self (Object) - the current instance of the class
        @param account_id (str) - the ID of the TD Ameritrade account to use
        @return (list) - a list of dictionaries, each one containing information
                 about a particular stock
        """
        
        # Set up debugging for the function
        logger = logging.getLogger()
        logger.debug("Entering get_account_positions")

        # Get the contents of the portfolio
        try:
            response = self._client.get_account(account_id, fields=self._client.Account.Fields.POSITIONS)
            assert response.status_code == 200, "Response from TD API was status code {0}".format(response.status_code)
        except Exception as e:
            self.__catch_error(e, "Error retrieving the account positions. Error: '{0}'".format(repr(e)))

        # Perform validation to make sure everything is as expected in the json
        try:
            response = response.json()
            assert response['securitiesAccount']['positions'], "JSON returned from API doesn't contain the positions"
            positions = response['securitiesAccount']['positions']
        except Exception as e:
            self.__catch_error(e, "Unexpected error while parsing the JSON returned by the API: {0}".format(repr(e)))

        # Return the positions
        logger.debug("Retrieved the positions for account ID {0}".format(account_id))
        return positions


    def get_saved_orders(self, account_id):
        """
        Purpose: Retrieves the saved orders for the specified account
        @param self (Object) - an instance of the current class
        @param account_id (str) - the ID of the TD Ameritrade account to use
        @return (I don't remember) Returns [] when there are no saved orders
        """

        # Set up debugging for the function
        logger = logging.getLogger()
        logger.debug("Entering get_saved_orders. Parameters are:\n\taccount_id: {0}".format(account_id))

        # Get the saved orders
        try:
            response = self._client.get_saved_orders_by_path(account_id)
            assert response.status_code == 200, "Response from TD API was status code {0}".format(response.status_code)
        except Exception as e:
            self.__catch_error(e, "Error getting saved orders from TD ameritrade: '{0}'".format(repr(e)))

        logger.debug("Retrieved saved orders")
        return json.loads(response.text)


    def remove_saved_order(self, account_id, order_id):
        """
        Purpose: Deletes a saved order from an account
        @param self (Object) - an instance of the current class
        @param account_id (str) - the account to delete the order from
        @param order_id (str) - the ID of the saved order we want to delete
        @return (None) - nothing
        """

        # Set up debugging for the function
        logger = logging.getLogger()
        logger.debug("Entering remove_saved_order. Parameters are:\n\taccount_id: {0}\n\torder_id: {1}".format(account_id, order_id))

        # Delete the saved order
        try:
            response = self._client.delete_saved_order(account_id, order_id)
            assert response.status_code == 200, "Response from TD API was status code {0}".format(response.status_code)
        except Exception as e:
            self.__catch_error(e, "Error removing saved order from TD ameritrade: '{0}'".format(repr(e)))

        logger.debug("Deleted saved order")
        return None


    def new_saved_order(self, account_id, ticker, count):
        """
        Purpose: Creates a new saved order on the specified account. This saved
                 order is hard coded to be a market order during a normal trading
                 session and to not be contingent on or for any other trade
        @param self (Object) - an instance of the current class
        @param account_id (str) - the ID of the account we want to save the order on
        @param ticker (str) - the stock symbol we want to create a saved order for
        @param count (int) - the quantity of stocks to buy
        @return (None) - nothing
        """

        # Set up debugging for the function
        logger = logging.getLogger()
        logger.debug("Entering new_saved_order. Parameters are:\n\taccount_id: {0}\n\tticker: {1}\n\tcount: {2}".format(account_id,ticker, count))

        # Create the order
        order = json.loads("""
    {{
        "orderType":         "MARKET",
        "session":           "NORMAL",
        "duration":          "DAY",
        "orderStrategyType": "SINGLE",
        "orderLegCollection": [
            {{
                "instruction": "Buy",
                "quantity":    {0},
                "instrument":
                    {{
                        "symbol":    "{1}",
                        "assetType": "EQUITY"
                    }}
            }}
        ]
    }}""".format(str(count), ticker))
        logger.debug("Order: {0}".format(order))

        # Save the order
        try:
            response = self._client.create_saved_order(account_id, order)
            assert response.status_code == 200, "Response from TD API was status code {0}".format(response.status_code)
        except Exception as e:
            self.__catch_error(e, "Error sending order to TD ameritrade: '{0}'".format(repr(e)))

        logger.debug("New saved order successfully created")
        return None


    def send_order(self, account_id, ticker, count):
        """
        Purpose: Executes an order on the specified account. This
                 order is hard coded to be a market order during a normal trading
                 session and to not be contingent on or for any other trade
        @param self (Object) - an instance of the current class
        @param account_id (str) - the ID of the account we want to send the order on
        @param ticker (str) - the stock symbol we want to purchase
        @param count (int) - the quantity of stocks to buy
        @return (None) - nothing
        """

        # Set up debugging for the function
        logger = logging.getLogger()
        logger.debug("Entering send_order. Parameters are:\n\taccount_id: {0}\n\tticker: {1}\n\tcount: {2}".format(account_id, ticker, count))

        # Create the order
        order = json.loads("""
    {{
        "orderType":         "MARKET",
        "session":           "NORMAL",
        "duration":          "DAY",
        "orderStrategyType": "SINGLE",
        "orderLegCollection": [
            {{
                "instruction": "Buy",
                "quantity":    {0},
                "instrument":
                    {{
                        "symbol":    "{1}",
                        "assetType": "EQUITY"
                    }}
            }}
        ]
    }}""".format(str(count), ticker))
        logger.debug("Order: {0}".format(order))

        # Execute the order
        try:
            response = self._client.place_order(account_id, order)
            assert (response.status_code == 200 or response.status_code == 201), "Response from TD API was status code {0}".format(response.status_code)
        except Exception as e:
            self.__catch_error(e, "Error sending order to TD ameritrade: '{0}'".format(repr(e)))

        logger.debug("Order placed successfully")
        return None


    def get_transactions(self, account_id, symbol=None, start_date=None, end_date=None):
        """
        Purpose: Gets the transactions that occurred on the specified account
        @param self (Object) - an instance of the current class
        @param account_id (str) - the ID of the account we want to retrieve transactions from
        @param symbol (str) - filter the results to only transactions involving the specified symbol
        @param start_date (datetime) - Only return transactions starting after this date. Must be
        @param end_date (datetime) - Only return transactions before this date
        @return (list) - a list of dictionaries containing transactions
        """

        # TODO: It seems like supplying no start or end date, by default, gets all
        # transactions ever made on the account. Unfortunately, I don't have a
        # way to verify if it's all transactions or just all transactions from the
        # past year as my account hasn't been open for more than a year yet

        # Set up debugging for the function
        logger = logging.getLogger()
        logger.debug("Entering get_transactions. Parameters are:\n\taccount_id: {0}\n\tsymbol: {1}\n\tstart_date: {2}\n\tend_date: {3}".format(account_id, symbol, start_date, end_date))

        # Double check the parameters
        assert ((start_date and end_date) or (not start_date and not end_date)), "Both start_date and end_date must be specified"
        assert (not start_date or start_date < end_date), "start_date must be less than end_date"
        assert (not start_date or start_date >= datetime.datetime(1970, 1, 1)), "start_date must be greater than or equal to Jan 1, 1970"

        # Get the transactions. TD limits the range of the transactions to one year;
        # We'll use a for loop to get around that limitation for any arbitrary date
        result = []
        try:
            if (start_date):  # A range was specified
                while (start_date < end_date):

                    # Calculate the end date
                    effective_end_date = (start_date + datetime.timedelta(days=365)) if ((end_date - start_date).days > 365) else end_date
                    logger.debug("Getting transactions from {0} to {1}".format(start_date, effective_end_date))

                    # Call the TD API and validate the response
                    response = self._client.get_transactions(account_id, symbol=symbol, start_date=start_date, end_date=effective_end_date)
                    assert (response.status_code == 200 or response.status_code == 201), "Response from TD API was status code {0}".format(response.status_code)
                    result += response.json()

                    # Update the start date for the next iteration
                    start_date = effective_end_date

            else:  # no range was specified
                    response = self._client.get_transactions(account_id, symbol=symbol)
                    assert (response.status_code == 200 or response.status_code == 201), "Response from TD API was status code {0}".format(response.status_code)
                    result = response.json()

        except Exception as e:
            self.__catch_error(e, "Error sending order to TD ameritrade: '{0}'".format(repr(e)))

        logger.debug("Finished retrieving transactions")
        return result
