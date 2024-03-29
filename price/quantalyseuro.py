"""Récupère les prix de Quantalys.

Récupère uniqument la dernière VL

In order to use this price fetcher with bean-price make sure it is in the PYTHON_PATH.
"""

__copyright__ = "Copyright (C) 2019  Grostim"
__license__ = "MIT"

import re
from dateutil.parser import parse as parse_datetime
from dateutil import tz
import requests
from bs4 import BeautifulSoup
from beancount.core.number import D
from beancount.prices import source

BASEURL = "https://www.quantalys.com/SupportEuro/"


class QuantalysError(ValueError):
    "An error from the Quantalys Price Fetcher"


class Source(source.Source):
    "Quantalys price extractor."

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
        session = requests.Session()
        url = BASEURL + ticker
        request = session.get(url)
        soup = BeautifulSoup(request.text, "html.parser")
        try:
            cours = soup.find("span", class_="vl-box-value").get_text(
                strip=True
            )
        except Exception:
            raise QuantalysError("Pas de cours disponible ?")
        control = r"(.*)\s*(%)"
        match = re.match(control, cours)
        the_price = D(
            match.group(1).replace(" ", "").replace(",", ".")
        ).quantize(D("0.01"))

        the_date = soup.find("span", class_="vl-box-date").get_text(strip=True)
        the_date = parse_datetime(the_date, dayfirst=True)
        fr_timezone = tz.gettz("Europe/Paris")
        the_date = the_date.astimezone(fr_timezone)

        return source.SourcePrice(the_price, the_date, match.group(2))

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
        raise QuantalysError("Import de l'historique pas encore implémenté")
