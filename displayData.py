#!/usr/bin/python3
# Author: Tom Daniels
# File: displayData.py

#############
## Imports ##
#############
import bokeh.layouts
import bokeh.models
import bokeh.plotting
import bokeh.io
import datetime
import os
import sqlite3


######################
## Static variables ##
######################
TOTAL = 0
EPOCH = 1
QUANTITY = 2
CLOSE = 3
PRICE = 3
DESCRIPTION = 4
X = 0
Y = 1


###############
## Functions ##
###############
def ticker_change(attrname, old, new):
    """
    Purpose: Called when a ticker is selected from the dropdown menu.
             Simply updates the graph with the new data
    @param attrname (str) - name of the changed attribute
    @param old (str) - the previous selected ticker
    @param new (str) - the newly selected ticker
    """
    update()

def account_change(attrname, old, new):
    """
    Purpose: Called when an account is selected from the dropdown menu.
             Adjusts the available account options AND ticker options.
    @param attrname (str) - name of the changed attribute
    @param old (str) - the previous selected account
    @param new (str) - the newly selected account
    """
    account = account_selection.value

    # Update the available tickers for that account
    con = sqlite3.connect("tda.sqlite")
    cursor = con.cursor()
    tickers = cursor.execute(("SELECT DISTINCT Ticker "
                              "FROM Tickers "
                              "JOIN Transactions ON Transactions.TickerId = Tickers.Id "
                              "WHERE Transactions.AccountId = ? "
                              "  AND Ticker != '$CASH$';"), [account]).fetchall()
    con.close()
    assert len(tickers) != 0, "No available tickers in the database for account {0}".format(account)
    tickers = [ticker[0] for ticker in tickers]

    # Update the list of tickers to select from
    ticker_selection.options = tickers
    ticker_selection.value = tickers[0]

    # Update the graph
    update()


def update():
    """
    Purpose: Gathers the price and transaction data, then draws the graph
    """

    # Get the current selected values
    ticker = ticker_selection.value
    account = account_selection.value

    # Get the data from the database
    con = sqlite3.connect("tda.sqlite")
    cursor = con.cursor()
    trans_data = cursor.execute(("SELECT Total, Date, Quantity, Price, Description "
                                 "FROM Transactions "
                                 "JOIN Tickers ON Transactions.TickerId = Tickers.Id "
                                 "WHERE AccountId = ? AND Ticker = ? "
                                 "ORDER BY Date ASC;"), [account, ticker]).fetchall()
    price_data = cursor.execute(("SELECT * " 
                                 "FROM Prices "
                                 "JOIN Tickers ON Prices.TickerId = Tickers.Id "
                                 "WHERE Tickers.Ticker = ? AND Date > (? - 86400)"
                                 "ORDER BY Date ASC;"), [ticker, trans_data[0][EPOCH]]).fetchall()
    con.close

    # Confirm we have price data for all the transaction dates
    assert (price_data[0][EPOCH] < trans_data[0][EPOCH] and trans_data[-1][EPOCH] < price_data[-1][EPOCH]), "Error, price history doesn't cover all transaction dates"

    # Set up variables for the calculations
    dividends = 0.0            # Keep track of the amount of dividends we've earned
    average_cost = 0.0         # The average amount we've paid per share of a stock
    shares = 0.0               # The number of shares we have
    transaction_index = 0      # Keeps track of what transaction to expect next
    cost_basis = [[], []]      # List of [[dates] and [prices]]. Each x,y is the liquidation value at a point in time
    total_invested = [[], []]  # List of [[dates] and [prices]]. Each x,y is the total amount spent at a point in time
    trans_time = 0             # The time a transaction occurred

    # Go through each day
    for day in price_data:

        # Did we have any transactions in the past 24 hours?
        if (trans_time != -1):
            trans_time = trans_data[transaction_index][EPOCH]
        price_time = day[EPOCH]

        # If so, go through all transactions in the past 24 hours
        # and adjust the number of shares, average cost, and dividends accordingly
        while (price_time - trans_time > 0 and trans_time != -1):

            # Determine the amount of shares we purchased (positive) or sold (negative)
            new_shares = trans_data[transaction_index][QUANTITY]
            if (trans_data[transaction_index][TOTAL] > 0):
                new_shares = 0 - new_shares

            # If we had any previous transactions, note that the amount of shares we
            # previously held is the same as today before the buy or sell
            if (shares):
                total_invested[X].append(datetime.datetime.fromtimestamp(day[EPOCH]))
                total_invested[Y].append(average_cost * shares)

            # Update the number of shares, average cost, and dividends
            if (new_shares == 0):  # Dividend transaction
                assert ('DIVIDEND' in trans_data[transaction_index][4]), 'Encountered a transaction without any changes in shares but a change in total'
                dividends += trans_data[transaction_index][TOTAL]
            else:  # A typical buy/sell
                average_cost = (average_cost * shares - trans_data[transaction_index][TOTAL]) / (shares + new_shares)
                shares += new_shares
            
            # Update the amount we've invested
            total_invested[X].append(datetime.datetime.fromtimestamp(day[EPOCH]))
            total_invested[Y].append(average_cost * shares)

            # Now look for the next transaction. If there are no more, set the time to -1
            transaction_index += 1
            if (transaction_index < len(trans_data)):
                trans_time = trans_data[transaction_index][EPOCH]
            else:
                trans_time = -1

        # Update the current value of our asset
        if (shares):
            cost_basis[X].append(datetime.datetime.fromtimestamp(day[EPOCH]))
            cost_basis[Y].append(shares * day[CLOSE] + dividends)

    # Extend the amount invested all the way to the end of the graph
    if (price_data):
        total_invested[X].append(datetime.datetime.fromtimestamp(price_data[-1][EPOCH]))
        total_invested[Y].append(average_cost * shares + dividends)

    # Set the data for the graph
    invested_source.data = { 'x_axis': total_invested[X],
                             'y_axis': total_invested[Y] }
    basis_source.data = { 'x_axis': cost_basis[X],
                          'y_axis': cost_basis[Y] }

    # Color the cost basis line based on performance
    if (total_invested[Y][-1] > cost_basis[Y][-1]):
        basis_renderer.glyph.line_color = 'red'
    else:
        basis_renderer.glyph.line_color = 'green'


##########
## Main ##
##########

#
### Get the data from the database
#
assert (os.path.exists("tda.sqlite")), "Error, tda.sqlite doesn't exist! Have you run importData.py?"
con = sqlite3.connect("tda.sqlite")
cursor = con.cursor()

# Get the list of accounts from the database
accounts = cursor.execute("SELECT AccountId FROM Accounts;").fetchall()
assert len(accounts) != 0, "No available accounts in the database"
accounts = [str(account[0]) for account in accounts]

# Get the list of tickers for the given account from the database
tickers = cursor.execute(("SELECT DISTINCT Ticker "
                          "FROM Tickers "
                          "JOIN Transactions ON Transactions.TickerId = Tickers.Id "
                          "WHERE Transactions.AccountId = ? "
                          "  AND Ticker != '$CASH$';"), [accounts[0]]).fetchall()
assert len(tickers) != 0, "No available tickers in the database for account {0}".format(accounts[0])
tickers = [ticker[0] for ticker in tickers]

con.close()


#
### Set up the graphs
#

# Set up the account and ticker selection widgets
account_selection = bokeh.models.Select(title='Account ID', value=accounts[0], options=accounts)
account_selection.on_change('value', account_change)
ticker_selection = bokeh.models.Select(title='Symbol', value=tickers[0], options=tickers)
ticker_selection.on_change('value', ticker_change)

# Holds the data to be graphed
invested_source = bokeh.models.ColumnDataSource(data=dict(x_axis=[], y_axis=[]))
basis_source = bokeh.models.ColumnDataSource(data=dict(x_axis=[], y_axis=[]))

# Create plot, label and format the axes, and configure the hover tool
plot = bokeh.plotting.figure(plot_width=1000, plot_height=300, x_axis_type='datetime')
plot.line('x_axis', 'y_axis', source=invested_source)
basis_renderer = plot.line('x_axis', 'y_axis', source=basis_source)
plot.xaxis.axis_label = 'Date'
plot.yaxis.axis_label = 'Dollars'
plot.yaxis[0].formatter = bokeh.models.NumeralTickFormatter(format='$0.00')

# Graph the data on the plot
update()

# Format the webpage
bokeh.io.curdoc().add_root(bokeh.layouts.column(bokeh.layouts.row(account_selection, ticker_selection), plot))
bokeh.io.curdoc().title = 'Cost Basis'
