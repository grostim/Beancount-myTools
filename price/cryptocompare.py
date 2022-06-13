"""Fetch prices from CryptoCompare.com JSON API
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

bean-price -e 'GBP:cryptocompare/BTC:GBP'
"""


class CryptoCompareError(ValueError):
    "An error from the CryptoCompare Price Fetcher"


class Source(source.Source):
    "CryptoCompare API price extractor."

    def get_historical_price(self, ticker, date):
        commodity, currency = ticker.split(":")
        trade_date = datetime.combine(date, datetime.max.time())
        trade_date = trade_date.replace(tzinfo=pytz.UTC)
        ts = int(time.mktime(trade_date.timetuple()))
        url = "https://min-api.cryptocompare.com/data/pricehistorical?fsym={}&tsyms={}&ts={}".format(
            commodity, currency, ts
        )
        logging.info("Fetching %s", url)
        try:
            response = net_utils.retrying_urlopen(url)
            if response is None:
                return None
            response = response.read().decode("utf-8").strip()
            response = json.loads(response)
        except error.HTTPError:
            return None
        try:
            price = D(response[commodity][currency]).quantize(
                D("1.000000000000000000")
            )
            return (
                None
                if price == 0
                else source.SourcePrice(price, trade_date, currency)
            )
        except Exception:
            raise CryptoCompareError("Pas de cours disponible ?")
            return None

    def get_latest_price(self, ticker):
        commodity, currency = ticker.split(":")
        url = "https://min-api.cryptocompare.com/data/price?fsym={}&tsyms={}".format(
            commodity, currency
        )
        logging.info("Fetching %s", url)
        try:
            response = net_utils.retrying_urlopen(url)
            if response is None:
                return None
            response = response.read().decode("utf-8").strip()
            response = json.loads(response)
        except error.HTTPError:
            raise CryptoCompareError("L'API Cryptocompare ne répond pas")
            return None
        try:
            price = D(response[currency]).quantize(D("1.000000000000000000"))
            trade_date = datetime.now()
            trade_date = trade_date.replace(tzinfo=pytz.UTC)
            return (
                None
                if price == 0
                else source.SourcePrice(price, trade_date, currency)
            )
        except Exception:
            raise CryptoCompareError("Pas de cours disponible ?")
            return None
