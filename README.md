# TDA-DB
For storing all of your GME transactions and other bad investments on the [TD Ameritrade platform](https://tdameritrade.com) into one [sqlite database](https://sqlite.org/index.html). The dispair and sadness that comes with those unfortunate investments isn't tracked in the DB, but you can submit a pull request if you add that functionality.

## Purpose
TDA-DB has two python scripts (and a few helper files) to pull down data about your account from the [TDA API](https://developer.tdameritrade.com/apis), set up your data in a sqlite database, and to display the cost basis of your account in a web UI.

**Disclaimer**: This product is in no way sponsored, endorsed, or affiliated with TD Ameritrade. The authors take no responsibility for any damage that might arise due to use of this code.

## Features
* Stores transactions and price history in a sqlite database
* Graphs cost basis for stocks in the database
* Reports errors through a [Telegram bot](https://core.telegram.org/bots)

## Why you should avoid using this
This section left intentionally blank, as this code is flawless

## Actual reasons to avoid
* Doesn't support all transaction types - The only data I have access to are transactions I've made on my own account so (for example), the database and code don't support options transactions
* ?? I can't think of anything else. If you're interested in the historic cost basis of your account as a whole or for particular tickers in your account and you have a TD Ameritrade brokerage account, this can show you that data.

## Prerequisites
TDA-DB requires the following:
* Python3
* A brokerage account with TD Ameritrade. Why did you care to continue reading the README without one of these?
* An OAuth2 token and API key to access your TD Ameritrade account. You can create these on the [developer website](https://developer.tdameritrade.com)
* The python packages in the requirements.txt file to be installed (namely [`tda-api`](https://github.com/alexgolec/tda-api) and [`bokeh`](https://github.com/bokeh/bokeh)). This can be done with `pip3 install -r requirements.txt`

## Configuration
Configuration is done via the example\_config.ini file. Your very first step should be to rename this file to config.ini. Other than that, I don't want to update this section in the README every time the config file changes so read the config.ini file for inline configuration help.

## Usage
There are two main files TDA-DB has:
* `importData.py` initializes and synchronizes the TD Ameritrade account information with the database. This is required to use displayData.py. To run, use `python3 importData.py`
* `displayData.py` uses `bokeh` to open a web interface and display the cost basis of all accounts in the brokerage. To run, use `python3 -m bokeh serve displayData.py --address <IP address to serve the web UI on> --allow-websocket-origin=<same IP address>:<port the web server is on>`. By default, the webserver is on port 5006, but you can change this with the `--port <port>` option. More information about `bokeh`'s `serve` command can be found [here](https://docs.bokeh.org/en/latest/docs/reference/command/subcommands/serve.html)

## Planned
As with most projects on github, here's the planned features/bug fixes section that will slowly devolve into a list of features that the code lacks and will never have implemented:
* `displayData.py` - Make the transaction occur at the actual transaction time and not on the following day
* `displayData.py` - Implment a hover tool. It should include the date, dollar gain/loss, percent gain/loss, total dollar amount invested, and the current value of the investment in the ticker
* `displayData.py` - Add an option to select all stocks to see how the total cost basis of the account changed over time
* `displayData.py` - Look into a bug that sometime pops up on graphs for my IRA account
* `importData.py` - Add support for options
