"""Fetch prices from the AMF Geco Database.
https://geco.amf-france.org
Base de donnée de FCP et Sicav francaises.

Le critère de recherche est le code ISIN
"""

__copyright__ = "Copyright (C) 2019  Grostim"
__license__ = "MIT"

import datetime
from dateutil.parser import parse as parse_datetime
import requests
import re
from dateutil import tz
from bs4 import BeautifulSoup
from beancount.core.number import D
from beancount.prices import source

BASEURL = "https://geco.amf-france.org/"


class AMFGecoError(ValueError):
    "An error from the AMFGeco Price Fetcher"


class Source(source.Source):
    "AMF Geco price extractor."

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

        s = requests.Session()
        url = BASEURL + "/Bio/rech_part.aspx?varvalidform=on&CodeISIN=" + ticker + "&CLASSPROD=0&NumAgr=&selectNRJ=0&NomProd=&NomSOc=&action=new&valid_form=Lancer+la+recherche"
        r = s.get(url)
        soup = BeautifulSoup(r.text, "html.parser")
        try:
          numProd = soup.find("input", {"name":"NumProd"})['value']
        except:
          raise AMFGecoError("ISIN introuvable sur AMFGeco")
          return None

        theDate = soup.find('td', text="Date VL :").next_sibling.get_text(strip=True)
        theDate = parse_datetime(theDate, dayfirst=True)
        fr_timezone = tz.gettz("Europe/Paris")
        theDate = theDate.astimezone(fr_timezone)

        thePrice = soup.find('td', text="Valeur (€) :").next_sibling.get_text(strip=True)
        thePrice = D(thePrice.replace(" ","").replace(",",".")).quantize(D('0.01'))

        return source.SourcePrice(thePrice, theDate, 'EUR')

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


        s = requests.Session()
        url = BASEURL + "/Bio/rech_part.aspx?varvalidform=on&CodeISIN=" + ticker + "&CLASSPROD=0&NumAgr=&selectNRJ=0&NomProd=&NomSOc=&action=new&valid_form=Lancer+la+recherche"

        r = s.get(url)
        soup = BeautifulSoup(r.text, "html.parser")
        try:
          numProd = soup.find("input", {"name":"NumProd"})['value']
          numPart = soup.find("input", {"name":"NumPart"})['value']
        except:
          raise AMFGecoError("ISIN introuvable sur AMFGeco")
          return None

        url = BASEURL + "Bio/info_part.aspx?SEC=VL&NumProd=" + numProd + "&NumPart=" + numPart + "&DateDeb=" + str(time.date().day) + "%2F" + str(time.date().month) + "%2F" + str(time.date().year)  + "&DateFin=" + str(time.date().day) + "%2F" + str(time.date().month) + "%2F" + str(time.date().year)  + "&btnvalid=OK"

        r = s.get(url)
        soup = BeautifulSoup(r.text, "html.parser")
        try:
          theDate = soup.find("tr", class_="ligne2").find_all('td')[0].get_text(strip=True)
          theDate = parse_datetime(theDate, dayfirst=True)
          fr_timezone = tz.gettz("Europe/Paris")
          theDate = theDate.astimezone(fr_timezone)

          thePrice = soup.find("tr", class_="ligne2").find_all('td')[1].get_text(strip=True)
          thePrice = D(thePrice.replace(" ","").replace(",",".")).quantize(D('0.01'))

        except:
          raise AMFGecoError("Pas de valeur liquidative publiée à cette date sur AMFGeco")
          return None

        return source.SourcePrice(thePrice, theDate, 'EUR')
