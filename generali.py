# -*- coding: utf8 -*-
""" Parseur de l'historique Generali.
"""
__copyright__ = "Copyright (C) 2019  Grostim"
__license__ = "Je ne sais pas"

import requests
import re
import pprint
from bs4 import BeautifulSoup


"""On ouvre la session et on va sur la page d'acceuil pour receuillir les cookies qui vont bien"""
s = requests.Session()
baseurl = "https://assurancevie.linxea.com"
r = s.get(baseurl)

"""Login avec les identifiants"""
# TODO: A sécuriser
url = (
    baseurl
    + "/b2b2c/entreesite/EntAccLog?task=Valider&valider=%2Fb2b2c%2Fentreesite%2FEntAccLog%3Ftask%3DValider"
    + "&loginSaisi=tgros&loginSaisi=&loginSaisi=N&loginSaisi=loginSaisi&loginSaisi=M&"
    + "password=sorg1234&password=&password=N&password=password&password=M"
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
while 1:
    r = s.get(url)
    soup = BeautifulSoup(r.text, "lxml")
    liens = soup.table.table.table.find_all("a")
    opes = dict()
    ope = dict()
    for lien in liens:
        #    print(lien.get("href"))
        r = s.get("https://assurancevie.linxea.com/b2b2c/epargne/" + lien.get("href"))
        soupette = BeautifulSoup(r.text, "lxml")
        # print(soupette.table.h1.text)
        ope["type"] = re.search(".*:\s(.*)", soupette.table.h1.text).group(1)
        ope["table"] = []
        # print(ope["type"])
        """On passe en revue les différentes lignes du tableau (sauf la première)"""
        lignes = soupette.table.find_all("table")[2].table.find_all("tr")
        for ligne in lignes[1:]:
            try:
                fond = re.search("codeFonds=(.*)&", ligne.td.a.get("onclick")).group(1)
            except:
                fond = ligne.find_all("td")[0].text
            date = ligne.find_all("td")[1].text
            try:
                valeurpart = re.search(
                    "(\d*,\d{2})", ligne.find_all("td")[2].text
                ).group(1)
            except:
                valeurpart = ""
            nbpart = ligne.find_all("td")[3].text
            montant = re.search("(\d*,\d{2})", ligne.find_all("td")[4].text).group(1)
            ope["table"].append([fond, date, valeurpart, nbpart, montant])
        # print(ope)
        # exit()
        opes[lien.text] = ope
        print(lien.text + "-" + ope["type"])
        """Si il y a un lien vers la page suivante, on reboucle, sinon, on sort"""
    if re.search("Suivante", soup.text) is not None:
        url = "https://assurancevie.linxea.com/b2b2c/epargne/CoeLisMvt?task=VoirPageSuivante"
    else:
        break
pprint.pprint(opes)
