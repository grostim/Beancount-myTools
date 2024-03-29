"""Fetch prices from the IEXcloud v1.0 API.

This price fetcher use the iexfinance python library:
https://addisonlynch.github.io/iexfinance

You need an API key.
You have to declare it in the environment variable IEX_TOKEN

In order to use this price fetcher with bean-price make sure it is in the PYTHON_PATH.
"""

__copyright__ = "Copyright (C) 2019  Grostim"
__license__ = "MIT"

import datetime
from dateutil.parser import parse as parse_datetime
import requests
from iexfinance.stocks import Stock
from iexfinance.stocks import get_historical_data
from dateutil import tz
from beancount.core.number import D
from beancount.prices import source


class IEXError(ValueError):
    "An error from the IEX API."


class Source(source.Source):
    "IEX API price extractor."

    def get_latest_price(self, ticker):
        """Fetch the current latest price. The date may differ.

        This routine attempts to fetch the most recent available price, and
        returns the actual date of the quoted price, which may differ from the
        date this call is made at. {1cfa25e37fc1}

        Args:
          ticker: A string, the ticker to be fetched by the source. This ticker
            may include structure, such as the exchange code. Also note that
            this ticker is source-specified, and is not necessarily the same
            value as the commodity symbol used in the Beancount file.
        Returns:
          A SourcePrice instance. If the price could not be fetched, None is
          returned and another source should be consulted. There is never any
          guarantee that a price source will be able to fetch its value; client
          code must be able to handle this. Also note that the price's returned
          time must be timezone-aware.
        """
        try:
            theStock = Stock(ticker)
            theQuote = theStock.get_book()["quote"]

            # IEX is American markets.
            us_timezone = tz.gettz("America/New_York")
            theDate = datetime.datetime.fromtimestamp(
                theQuote["latestUpdate"] / 1000
            )
            theDate = theDate.astimezone(us_timezone)

            thePrice = D(theQuote["latestPrice"]).quantize(D("0.01"))
            return source.SourcePrice(thePrice, theDate, "USD")
        except Exception:
            raise IEXError("Erreur lors de l'execution de la requete")
            return None

    def get_historical_price(self, ticker, time):
        """Return the historical price found for the symbol at the given date.

        This could be the price of the close of the day, for instance. We assume
        that there is some single price representative of the day.

        Args:
          ticker: A string, the ticker to be fetched by the source. This ticker
            may include structure, such as the exchange code. Also note that
            this ticker is source-specified, and is not necessarily the same
            value as the commodity symbol used in the Beancount file.
          time: The timestamp at which to query for the price. This is a
            timezone-aware timestamp you can convert to any timezone. For past
            dates we query for a time that is equivalent to 4pm in the user's
            timezone.
        Returns:
          A SourcePrice instance. If the price could not be fetched, None is
          returned and another source should be consulted. There is never any
          guarantee that a price source will be able to fetch its value; client
          code must be able to handle this. Also note that the price's returned
          time must be timezone-aware.
        """
        try:
            theQuote = get_historical_data(
                ticker, time.date(), close_only=True
            )
            for theDate in theQuote.keys():
                thePrice = D(theQuote[theDate]["close"]).quantize(D("0.01"))
                # IEX is American markets.
                us_timezone = tz.gettz("America/New_York")
                theDate = parse_datetime(theDate)
                theDate = theDate.astimezone(us_timezone)
                break
            return source.SourcePrice(thePrice, theDate, "USD")
        except Exception:
            raise IEXError("Erreur lors de l'execution de la requete")
            return None
