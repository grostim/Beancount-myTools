#!/usr/bin/env python3
# -*- coding: utf8 -*-
""" Parseur de l'historique Generali.

Ce script s'attend à trouver un ficher de config nommé "generali.ini" qui contiendra vos identifiants sous la forme suivante:

[GENERALI]
User = identifiant
Password = MotDePasse

"""
__copyright__ = "Copyright (C) 2019  Grostim"
__license__ = "Je ne sais pas"

import requests
import re
import pprint
import json
import configparser
from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_datetime


def balayagetableau():
    """Procédure qui balaye les lignes du tableau"""
    for ligne in lignes[1:]:
        dataline = dict()
        try:
            dataline["fond"] = re.search(
                "codeFonds=(.*)&", ligne.td.a.get("onclick")
            ).group(1)
            urlfond = re.search(
                "javascript:creerPageExterne\('(.*)'\);", ligne.input.get("value")
            ).group(1)
            r = s.get(baseurl + urlfond)
            compote = BeautifulSoup(r.text, "lxml")
            dataline["isin"] = re.search("ISIN\s:\s(..\d{10})", compote.text).group(1)
            dataline["nomfond"] = ligne.find_all("td")[0].text
        except:
            dataline["fond"] = ligne.find_all("td")[0].text
            dataline["isin"] = dataline["fond"]
            dataline["nomfond"] = dataline["fond"]

        dataline["date"] = str(
            parse_datetime(ligne.find_all("td")[1].text, dayfirst="True").date()
        )

        try:
            dataline["valeurpart"] = re.search(
                "(\d{0,3}\s?\d*,\d{2})", ligne.find_all("td")[2].text
            ).group(1)
        except:
            dataline["valeurpart"] = ""

        dataline["nbpart"] = ligne.find_all("td")[3].text
        dataline["montant"] = re.search(
            "(\d{0,3}\s?\d*,\d{2})", ligne.find_all("td")[4].text
        ).group(1)
        ope["table"].append(dataline)


EXPORTDIR = "A_Importer/"
config = configparser.ConfigParser()
config.read("generali.ini")

"""On ouvre la session et on va sur la page d'acceuil pour receuillir les cookies qui vont bien"""
s = requests.Session()
baseurl = "https://assurancevie.linxea.com"
r = s.get(baseurl)

"""Login avec les identifiants"""
url = (
    baseurl
    + "/b2b2c/entreesite/EntAccLog?task=Valider&valider=%2Fb2b2c%2Fentreesite%2FEntAccLog%3Ftask%3DValider"
    + "&loginSaisi="
    + config["GENERALI"]["User"]
    + "&loginSaisi=&loginSaisi=N&loginSaisi=loginSaisi&loginSaisi=M&"
    + "password="
    + config["GENERALI"]["Password"]
    + "&password=&password=N&password=password&password=M"
)
r = s.get(url)
"""A la recherche de l'accès au compte"""
soup = BeautifulSoup(r.text, "html.parser")
finurl = soup.find_all("a")[1].get("href")
r = s.get(baseurl + finurl)
finurl = "/b2b2c/epargne/CoeDetCon"
r = s.get(baseurl + finurl)
"""Récupération des liens sur la plage"""
url = "https://assurancevie.linxea.com/b2b2c/epargne/CoeLisMvt"
firstpass = 1
while 1:
    r = s.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    liens = soup.table.table.table.find_all("a")
    ope = dict()
    fini = 0
    if firstpass == 1:
        lastdate = str(parse_datetime(liens[0].text, dayfirst="True").date())
    for lien in liens:
        print(str(parse_datetime(lien.text, dayfirst="True").date()))
        print(config["GENERALI"]["last"])
        if (
            str(parse_datetime(lien.text, dayfirst="True").date())
            == config["GENERALI"]["last"]
        ):
            print("OK, nous sommes à jour")
            fini = 1
            break
        r = s.get("https://assurancevie.linxea.com/b2b2c/epargne/" + lien.get("href"))
        soupette = BeautifulSoup(r.text, "lxml")
        ope["ope"] = re.search(".*:\s(.*)", soupette.table.h1.text).group(1)
        ope["compte"] = re.search("Adhésion.*(P\d{8})", soup.h2.text).group(1)
        ope["table"] = []

        """On passe en revue les différentes lignes du tableau (sauf la première)"""
        lignes = soupette.table.find_all("table")[2].table.find_all("tr")
        if ope["ope"] == "Arbitrage" or ope["ope"] == "Opération sur titres":
            balayagetableau()
            lignes = soupette.table.find_all("table")[4].find_all("tr")
            balayagetableau()
        else:
            balayagetableau()

        """Sauvegarde en fichier json"""
        filename = (
            str(parse_datetime(lien.text, dayfirst="True").date()) + "-" + ope["ope"]
        )
        print(filename)
        with open(EXPORTDIR + filename + ".json", "w") as fp:
            json.dump(ope, fp, sort_keys=True, indent=4)

        """Si on a rattrapé le retard , on sort"""
    if fini == 1:
        config["GENERALI"]["last"] = str(lastdate)
        with open("generali.ini", "w") as configfile:
            config.write(configfile)
        break
        """Si il y a un lien vers la page suivante, on reboucle, sinon, on sort"""
    if re.search("Suivante", soup.text) is not None:
        firstpass = 0
        url = "https://assurancevie.linxea.com/b2b2c/epargne/CoeLisMvt?task=VoirPageSuivante"
    else:
        break
