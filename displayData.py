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
def calc_cost_basis(ticker, account):
    """
    Purpose: Retrieves the cost_basis and total invested for a given ticker
             in an account
    @param ticker (string) - the stock ticker
    @account (string) - the account for which to calculate the cost basis
    @return (tuple) - a tuple containing a list of dates and total account values
            for the given stock, and a list of dates and the total amount invested
            in the given stock
    """

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
        total_invested[Y].append(average_cost * shares)

    return (total_invested, cost_basis)


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
    tickers.append('Total')

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

    # Calculate the cost basis
    if (ticker == 'Total'):

        # Get all the data from all tickers
        total_invested_dict = {}
        cost_basis_dict = {}
        for t in tickers:

            # Ignore the fake ticker
            if (t == 'Total'):
                continue

            total_invested, cost_basis = calc_cost_basis(t, account)

            # For the ticker, note the date and by how much we invested
            # on that date
            running_total = 0
            for i in range(0, len(total_invested[X])):
                if (total_invested[Y][i] != running_total):
                    if (total_invested[X][i] in total_invested_dict.keys()):
                        total_invested_dict[total_invested[X][i]] += (total_invested[Y][i] - running_total)
                    else:
                        total_invested_dict[total_invested[X][i]] = (total_invested[Y][i] - running_total)
                    running_total = total_invested[Y][i]

            # For the ticker, note each date and the value of our investment at that time
            for i in range(0, len(cost_basis[X])):
                if (cost_basis[X][i] in cost_basis_dict.keys()):
                    cost_basis_dict[cost_basis[X][i]] += cost_basis[Y][i]
                else:
                    cost_basis_dict[cost_basis[X][i]] = cost_basis[Y][i]

        # For each date in the dictionary, sort the dates and
        # note the price at each date
        total_invested = [[], []]
        total_invested_temp = list(total_invested_dict.keys())
        total_invested_temp.sort()
        running_total = 0
        for date in total_invested_temp:
            # Extend the graph line to the next increase in
            # total invested
            if (running_total):
                total_invested[X].append(date)
                total_invested[Y].append(total_invested[Y][-1])
            running_total += total_invested_dict[date]
            total_invested[X].append(date)
            total_invested[Y].append(running_total)

        # For each date in the dictionary, sort the dates and
        # note the price at each date
        cost_basis = [[], []]
        cost_basis_temp = list(cost_basis_dict.keys())
        cost_basis_temp.sort()
        for date in cost_basis_temp:
            cost_basis[X].append(date)
            cost_basis[Y].append(cost_basis_dict[date])

        # Extend the total invested to the end of the graph
        total_invested[X].append(cost_basis[X][-1])
        total_invested[Y].append(running_total)

    else:
        total_invested, cost_basis = calc_cost_basis(ticker, account)

    # Calculate % gain/loss and $ gain/loss for the hover tool
    daily_invested = []
    cost_basis_dollar = []
    cost_basis_percent = []
    invested_index = 0
    invested_max_index = len(total_invested[X]) - 1
    for i in range(0, len(cost_basis[X])):
        while (invested_index < invested_max_index - 1 and
               total_invested[X][invested_index+1] <= cost_basis[X][i]):
            invested_index += 1
        daily_invested.append(total_invested[Y][invested_index])  # Record the amount we have invested on this date
        cost_basis_dollar.append(cost_basis[Y][i] - daily_invested[-1])  # Record the cost basis on this date
        cost_basis_percent.append((cost_basis_dollar[-1] * 100) / daily_invested[-1]) 
    
    # Set the data for the graph
    invested_source.data = { 'x_axis': total_invested[X],
                             'y_axis': total_invested[Y] }
    basis_source.data = { 'x_axis':        cost_basis[X],
                          'y_axis':        cost_basis[Y],
                          'invested':      daily_invested,
                          'basis_dollar':  cost_basis_dollar,
                          'basis_percent': cost_basis_percent }

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
tickers.append('Total')

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
basis_source = bokeh.models.ColumnDataSource(data=dict(x_axis=[], y_axis=[], invested=[], basis_dollar=[], basis_percent=[]))

# Create plot, label and format the axes, and configure the hover tool
plot = bokeh.plotting.figure(plot_width=1000, plot_height=300, x_axis_type='datetime')
plot.line('x_axis', 'y_axis', line_width=1.5, source=invested_source)
basis_renderer = plot.line('x_axis', 'y_axis', line_width=1.5,  source=basis_source)
plot.xaxis.axis_label = 'Date'
plot.yaxis.axis_label = 'Dollars'
plot.yaxis[0].formatter = bokeh.models.NumeralTickFormatter(format='$0.00')

# Add the hover tool to the graph
hover_tool = bokeh.models.HoverTool(
    tooltips = [
        ('Date',           '$x{%F}'),
        ('Current Value',  '$@{y_axis}{%0.2f}'),
        ('Invested',       '$@{invested}{%0.2f}'),
        ('Cost Basis ($)', '$@{basis_dollar}{%0.2f}'),
        ('Cost Basis (%)', '@basis_percent')],
    mode = 'vline'
)
hover_tool.formatters = {
    '$x':              'datetime',
    '@{y_axis}':       'printf',
    '@{invested}':     'printf',
    '@{basis_dollar}': 'printf'
}
plot.add_tools(hover_tool)

# Only show the hover tool over the cost basis
plot.hover.renderers = [basis_renderer]

# Graph the data on the plot
update()

# Format the webpage
bokeh.io.curdoc().add_root(bokeh.layouts.column(bokeh.layouts.row(account_selection, ticker_selection), plot))
bokeh.io.curdoc().title = 'Cost Basis'
