"""Fetch prices from https://api.realt.community/JSON API
"""
import time
import logging
import json
from datetime import datetime
import pytz
from urllib import error
from math import log10, floor

from beancount.core.number import D
from beancount.prices import source
from beancount.utils import net_utils

"""
Merci : https://github.com/akashin/beancount-price-sources/blob/master/akashin_sources/cryptocompare.py

bean-price -e 'USD:realt/0x499A6c19F5537dd6005E2B5c6E1263103f558Ba4'
"""
class RealtError(ValueError):
    "An error from the Realt Price Fetcher"
    
class Source(source.Source):
    "REALT API price extractor."

    def get_historical_price(self, ticker, date):
        raise RealtError("Import de l'historique pas encore implémenté")
        return None

        
    def get_latest_price(self, ticker):
        url = 'https://api.realt.community/v1/token/{}'.format(ticker)
        logging.info("Fetching %s", url)
        try:
            response = net_utils.retrying_urlopen(url)
            if response is None:
                return None
            response = response.read().decode('utf-8').strip()
            response = json.loads(response)
            logging.info("Reponse: %s", response)
        except error.HTTPError:
            return None
        logging.info("Price: %s", response['tokenPrice'])
        try:
            price = D(response['tokenPrice'].quantize(1.00))
            trade_date = datetime.now()
            trade_date = trade_date.replace(tzinfo=pytz.UTC)
            return None if price == 0 else source.SourcePrice(price, trade_date, response['currency'])
        except:
          raise RealtError("Pas de cours disponible ?")
          return None
