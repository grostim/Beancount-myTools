"""Importateur pour les relevés PDF d'American Express."""

import re
from datetime import timedelta
from decimal import Decimal
from typing import List, Dict, Optional

from dateutil.parser import parse as parse_datetime
from beancount.core import amount, data, flags
from beancount.ingest import importer
from myTools.myutils import pdf_to_text, traduire_mois

class PDFAmex(importer.ImporterProtocol):
    """Importateur pour les relevés PDF American Express."""

    def __init__(self, account_list: Dict[str, str], debug: bool = False):
        self.account_list = account_list
        self.debug = debug

    def identify(self, file) -> bool:
        if file.mimetype() != "application/pdf":
            return False
        text = file.convert(pdf_to_text)
        return text and "Carte Air France KLM" in text

    def file_name(self, _) -> str:
        return "Amex.pdf"

    def file_account(self, file) -> Optional[str]:
        text = file.convert(pdf_to_text)
        match = re.search(r"xxxx-xxxxxx-(\d{5})", text)
        return self.account_list.get(match.group(1)) if match else None

    def file_date(self, file):
        text = file.convert(pdf_to_text)
        match = re.search(r"xxxx-xxxxxx-\d{5}\s*(\d*/\d*/\d*)", text)
        return parse_datetime(match.group(1), dayfirst=True).date() if match else None

    def extract(self, file, existing_entries=None) -> List[data.Directive]:
        text = file.convert(pdf_to_text)
        if self.debug:
            print(text)

        statement_date = self._extract_statement_date(text)
        account_number = self._extract_account_number(text)
        transactions = self._extract_transactions(text, statement_date)
        balance = self._extract_balance(text, account_number)

        entries = [self._create_transaction(t, account_number, file) for t in transactions]
        entries.append(balance)

        return entries

    def _extract_statement_date(self, text: str) -> Dict[str, str]:
        match = re.search(r"xxxx-xxxxxx-\d{5}\s*\d*/(\d*)/(\d*)", text)
        return {"month": match.group(1), "year": match.group(2)} if match else {}

    def _extract_account_number(self, text: str) -> Optional[str]:
        match = re.search(r"xxxx-xxxxxx-(\d{5})", text)
        return match.group(0).split(" ")[-1] if match else None

    def _extract_transactions(self, text: str, statement_date: Dict[str, str]) -> List[Dict]:
        transactions = []
        chunks = re.findall(r"\d{1,2}\s[a-zéèûôùê]{3,4}\s*\d{1,2}\s[a-zéèûôùê]{3,4}.*\d+,\d{2}(?:\s*CR)?", text)
        
        for chunk in chunks:
            transaction = self._parse_transaction(chunk, statement_date)
            if transaction:
                transactions.append(transaction)

        return transactions

    def _parse_transaction(self, chunk: str, statement_date: Dict[str, str]) -> Optional[Dict]:
        date_match = re.search(r"(\d{1,2}\s[a-zéèûôùê]{3,4})\s*(\d{1,2}\s[a-zéèûôùê]{3,4})", chunk)
        amount_match = re.search(r"\d{1,2}\s[a-zéèûôùê]{3,4}\s*\d{1,2}\s[a-zéèûôùê]{3,4}\s+(.*?)\s+(\d{0,3}\s{0,1}\d{1,3},\d{2})(\s*CR)?$", chunk)

        if not date_match or not amount_match:
            return None

        raw_date = date_match.group(2)
        month = date_match.group(2).split()[1]
        year = statement_date['year'] if month != 'déc' or statement_date['month'] != '01' else str(int(statement_date['year']) - 1)
        
        return {
            "date": parse_datetime(traduire_mois(f"{raw_date} 20{year}")),
            "amount": self._parse_amount(amount_match.group(2), amount_match.group(3)),
            "payee": re.sub(r"\s+", " ", amount_match.group(1)),
            "type": "Débit" if amount_match.group(3) else "Credit"
        }

    def _parse_amount(self, amount_str: str, credit_indicator: Optional[str]) -> amount.Amount:
        decimal_amount = Decimal(amount_str.replace(",", ".").replace(" ", ""))
        return amount.Amount(decimal_amount if credit_indicator else -decimal_amount, "EUR")

    def _extract_balance(self, text: str, account_number: str) -> data.Balance:
        match = re.search(r"Total des dépenses pour\s+(?:.*?)\s+(\d{0,3}\s{0,1}\d{1,3},\d{2})", text)
        balance_amount = -Decimal(match.group(1).replace(",", ".").replace(" ", "")) if match else Decimal(0)

        date_match = re.search(r"xxxx-xxxxxx-\d{5}\s*(\d*/\d*/\d*)", text)
        balance_date = parse_datetime(date_match.group(1), dayfirst=True).date() + timedelta(1) if date_match else None

        return data.Balance(
            meta=data.new_metadata("", 0, {"source": "pdfamex"}),
            date=balance_date,
            account=self.account_list[account_number],
            amount=amount.Amount(balance_amount, "EUR"),
            tolerance=None,
            diff_amount=None
        )

    def _create_transaction(self, transaction: Dict, account_number: str, file) -> data.Transaction:
        meta = data.new_metadata(file.name, 0, {"source": "pdfamex", "type": transaction["type"]})
        posting = data.Posting(
            account=self.account_list[account_number],
            units=transaction["amount"],
            cost=None,
            flag=None,
            meta=None,
            price=None
        )
        return data.Transaction(
            meta=meta,
            date=transaction["date"].date(),
            flag=flags.FLAG_OKAY,
            payee=transaction["payee"] or "inconnu",
            narration="",
            tags=data.EMPTY_SET,
            links=data.EMPTY_SET,
            postings=[posting]
        )