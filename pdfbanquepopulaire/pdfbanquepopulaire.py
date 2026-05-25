"""Importateur pour les releves PDF Banque Populaire.

Cet importateur cible les formats "compte cheques" et "compte courant" observes sur les releves
Banque Populaire Aquitaine Centre Atlantique. Il extrait :
- le numero de compte,
- la date de releve,
- le solde d'ouverture,
- les mouvements du tableau principal,
- le solde de cloture.

Par hygiene pour un depot public, aucun PDF reel ni texte confidentiel ne
doit etre ajoute a `myTools`. Les tests de ce module utilisent uniquement des
extraits synthetiques et anonymises.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from beancount.core import amount, data, flags
import beangulp
from dateutil.parser import parse as parse_datetime

try:
    from myutils import pdf_to_text
except ImportError:
    from ..myutils import pdf_to_text


class PDFBanquePopulaire(beangulp.Importer):
    """Importeur beangulp pour les releves Banque Populaire."""

    ACCOUNT_NUMBER_PATTERN = re.compile(
        r"COMPTE (?:CHEQUES|COURANT) N[°º]\s*(\d{11})"
    )
    STATEMENT_DATE_PATTERN = re.compile(
        r"RELEV[ÉE](?:\s+DE\s+COMPTE)?\s+N[°º]?\s*\d+\s+AU\s+"
        r"(\d{2}/\d{2}/\d{4})",
        re.IGNORECASE,
    )
    BALANCE_PATTERN = re.compile(
        r"SOLDE\s+(CREDITEUR|DEBITEUR)\s+AU\s+(\d{2}/\d{2}/\d{4})\*?\s+"
        r"([+-]?\s*\d(?:[\d .]*\d)?,\d{2})\s*€",
        re.IGNORECASE,
    )
    TRANSACTION_START_PATTERN = re.compile(r"^\s*(\d{2}/\d{2})\b")
    TRANSACTION_DETAILS_PATTERN = re.compile(
        r"(?P<prefix>.*?)"
        r"(?P<reference>[A-Z0-9]{7,})\s+"
        r"(?P<operation>\d{2}/\d{2})\s+"
        r"(?P<value>\d{2}/\d{2})\s+"
        r"[-–]?\s*(?P<amount>\d[\d\s,.]*(?:\d\s*€?|\s+€)?)(?:\s+[KSTGDCP]\s*)?$"
    )
    AMOUNT_SPLIT_LINE_PATTERN = re.compile(r"^\s*€")

    def __init__(self, account_list: dict[str, str], debug: bool = False):
        self.account_list = account_list
        self.debug = debug

    def _debug(self, message: str) -> None:
        if self.debug:
            print(f"[PDFBanquePopulaire] {message}")

    def _get_pdf_text(self, file: str) -> str:
        return pdf_to_text(file)

    def identify(self, file) -> bool:
        if not str(file).lower().endswith(".pdf"):
            return False

        text = self._get_pdf_text(str(file))
        upper = text.upper()
        return (
            "BANQUE POPULAIRE" in upper
            and (
                "DETAIL DES OPERATIONS DE VOTRE COMPTE CHEQUES" in upper
                or "DETAIL DES OPERATIONS DE VOTRE COMPTE COURANT" in upper
            )
        )

    def filename(self, _) -> str:
        return "Relevé Compte.pdf"

    def account(self, file) -> Optional[str]:
        account_number = self._extract_account_number(self._get_pdf_text(str(file)))
        return self.account_list.get(account_number)

    def date(self, file) -> Optional[dt.date]:
        text = self._get_pdf_text(str(file))
        match = self.STATEMENT_DATE_PATTERN.search(text)
        if not match:
            return None
        return parse_datetime(match.group(1), dayfirst=True).date()

    def extract(self, file, existing=None) -> List[data.Directive]:
        del existing  # Unused but kept for importer API compatibility.

        text = self._get_pdf_text(str(file))
        account_number = self._extract_account_number(text)
        account_name = self.account_list.get(account_number)
        if not account_name:
            raise ValueError(
                "Compte Banque Populaire absent de account_list: "
                f"{account_number}"
            )

        statement_date = self.date(str(file))
        if statement_date is None:
            raise ValueError("Date de releve Banque Populaire introuvable.")

        document = f"{statement_date} {self.filename(file)}"
        entries: List[data.Directive] = []

        opening_balance, closing_balance = self._extract_balances(
            text, statement_date
        )
        sepa_detail_amounts = self._extract_sepa_detail_amounts(text)
        if opening_balance:
            status, raw_date, raw_amount = opening_balance
            balance_date = (
                parse_datetime(raw_date, dayfirst=True).date()
                + dt.timedelta(days=1)
            )
            entries.append(
                self._create_balance(
                    file=str(file),
                    line=0,
                    entry_date=balance_date,
                    account_name=account_name,
                    balance_amount=self._balance_amount(status, raw_amount),
                    document=document,
                )
            )

        transaction_entries: list[data.Transaction] = []
        for index, block in enumerate(self._split_transaction_blocks(text), start=1):
            transaction_entries.append(
                self._parse_transaction_block(
                    block_lines=block,
                    statement_date=statement_date,
                    account_name=account_name,
                    file=str(file),
                    line=index,
                    document=document,
                    sepa_detail_amounts=sepa_detail_amounts,
                )
            )
        entries.extend(transaction_entries)

        if closing_balance:
            status, raw_date, raw_amount = closing_balance
            balance_date = parse_datetime(raw_date, dayfirst=True).date()
            entries.append(
                self._create_balance(
                    file=str(file),
                    line=0,
                    entry_date=balance_date,
                    account_name=account_name,
                    balance_amount=self._balance_amount(status, raw_amount),
                    document=document,
                )
            )
        elif opening_balance:
            status, _raw_date, raw_amount = opening_balance
            derived_closing_amount = self._balance_amount(status, raw_amount)
            for entry in transaction_entries:
                derived_closing_amount += entry.postings[0].units.number
            entries.append(
                self._create_balance(
                    file=str(file),
                    line=0,
                    entry_date=statement_date,
                    account_name=account_name,
                    balance_amount=derived_closing_amount,
                    document=document,
                )
            )

        return entries

    def _extract_account_number(self, text: str) -> str:
        match = self.ACCOUNT_NUMBER_PATTERN.search(text)
        if not match:
            raise ValueError("Numero de compte Banque Populaire introuvable.")
        return match.group(1)

    def _extract_balances(
        self, text: str, statement_date: dt.date
    ) -> tuple[
        Optional[tuple[str, str, str]],
        Optional[tuple[str, str, str]],
    ]:
        matches = list(self.BALANCE_PATTERN.finditer(text))
        if not matches:
            return None, None

        opening_match = matches[0]
        opening = (
            opening_match.group(1),
            opening_match.group(2),
            opening_match.group(3),
        )
        if len(matches) == 1:
            single_balance_date = parse_datetime(
                opening_match.group(2), dayfirst=True
            ).date()
            if single_balance_date == statement_date:
                return None, opening
            return opening, None
        closing_match = matches[-1]
        closing = (
            closing_match.group(1),
            closing_match.group(2),
            closing_match.group(3),
        )
        return opening, closing

    def _split_transaction_blocks(self, text: str) -> list[list[str]]:
        section = self._extract_main_operations_section(text)
        blocks: list[list[str]] = []
        current: list[str] = []

        for raw_line in section.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("SOLDE "):
                continue
            if self._is_operations_section_terminator(stripped):
                break

            if self.TRANSACTION_START_PATTERN.match(line):
                if current:
                    blocks.append(current)
                current = [line]
                continue

            if current:
                current.append(line)

        if current:
            blocks.append(current)

        self._debug(f"Blocs de transactions detectes: {len(blocks)}")
        return blocks

    def _extract_main_operations_section(self, text: str) -> str:
        upper = text.upper()
        detail_index = upper.find("DETAIL DES OPERATIONS DE VOTRE COMPTE CHEQUES")
        if detail_index == -1:
            detail_index = upper.find(
                "DETAIL DES OPERATIONS DE VOTRE COMPTE COURANT"
            )
        if detail_index == -1:
            raise ValueError("Section des operations Banque Populaire introuvable.")

        start_index = upper.find("SOLDE ", detail_index)
        end_markers = [
            upper.find("TOTAL DES MOUVEMENTS DEBITEURS", start_index),
            upper.find("DETAIL DE VOS MOUVEMENTS SEPA", start_index),
        ]
        end_candidates = [index for index in end_markers if index != -1]
        end_index = min(end_candidates) if end_candidates else -1
        if start_index == -1 or end_index == -1:
            raise ValueError(
                "Bornes de la section d'operations Banque Populaire introuvables."
            )

        return text[start_index:end_index]

    def _parse_transaction_block(
        self,
        *,
        block_lines: list[str],
        statement_date: dt.date,
        account_name: str,
        file: str,
        line: int,
        document: str,
        sepa_detail_amounts: dict[str, Decimal],
    ) -> data.Transaction:
        first_line_match = re.match(
            r"^\s*(\d{2}/\d{2})(?:\s+[A-Z]\s+)?(.*)$", block_lines[0]
        )
        if not first_line_match:
            raise ValueError(
                "Impossible de lire la date comptable Banque Populaire: "
                f"{block_lines[0]!r}"
            )

        detail_index = -1
        detail_match = None
        for index in range(len(block_lines) - 1, -1, -1):
            candidate = self.TRANSACTION_DETAILS_PATTERN.search(block_lines[index])
            if candidate:
                detail_index = index
                detail_match = candidate
                break

        if detail_match is None:
            raise ValueError(
                "Impossible de lire les details de transaction Banque "
                f"Populaire: {' | '.join(line.strip() for line in block_lines)}"
            )

        raw_payee = (
            detail_match.group("prefix").strip()
            if detail_index == 0
            else first_line_match.group(2).strip()
        )
        raw_payee = re.sub(
            r"^\d{2}/\d{2}(?:\s+[A-Z]\s+)?",
            "",
            raw_payee,
        )
        payee = self._normalize_spaces(raw_payee)
        if not payee:
            payee = "Operation Banque Populaire"

        narration_lines: list[str] = []
        if detail_index > 0:
            for index, line_text in enumerate(block_lines[1:], start=1):
                if index == detail_index:
                    prefix = self._normalize_spaces(
                        detail_match.group("prefix").strip()
                    )
                    if prefix:
                        narration_lines.append(prefix)
                    continue
                cleaned = self._normalize_spaces(line_text)
                if cleaned:
                    narration_lines.append(cleaned)
        else:
            for line_text in block_lines[1:]:
                cleaned = self._normalize_spaces(line_text)
                if cleaned:
                    narration_lines.append(cleaned)

        transaction_date = self._resolve_partial_date(
            detail_match.group("value"), statement_date
        )
        transaction_amount = self._resolve_transaction_amount(
            raw_amount=detail_match.group("amount"),
            payee=payee,
            block_lines=block_lines,
            sepa_detail_amounts=sepa_detail_amounts,
        )

        meta = data.new_metadata(file, line)
        meta["source"] = "pdfbanquepopulaire"
        meta["document"] = document

        postings = [
            data.Posting(
                account=account_name,
                units=amount.Amount(transaction_amount, "EUR"),
                cost=None,
                price=None,
                flag=None,
                meta=None,
            )
        ]
        counter_account = self._guess_counter_account(
            payee=payee,
            narration=self._normalize_spaces(" ".join(narration_lines)),
        )
        if counter_account:
            postings.append(
                data.Posting(
                    account=counter_account,
                    units=None,
                    cost=None,
                    price=None,
                    flag=None,
                    meta=None,
                )
            )

        return data.Transaction(
            meta=meta,
            date=transaction_date,
            flag=flags.FLAG_OKAY,
            payee=payee,
            narration=self._normalize_spaces(" ".join(narration_lines)),
            tags=data.EMPTY_SET,
            links=data.EMPTY_SET,
            postings=postings,
        )

    def _resolve_partial_date(
        self, partial_date: str, statement_date: dt.date
    ) -> dt.date:
        day, month = [int(part) for part in partial_date.split("/")]
        year = statement_date.year
        candidate = dt.date(year, month, day)
        if candidate > statement_date:
            candidate = dt.date(year - 1, month, day)
        return candidate

    def _balance_amount(self, status: str, raw_amount: str) -> Decimal:
        value = self._parse_decimal(raw_amount)
        explicit_sign = "-" in raw_amount or "+" in raw_amount
        if explicit_sign:
            return value
        if status.upper() == "DEBITEUR":
            return -abs(value)
        return abs(value)

    def _parse_decimal(self, raw_amount: str) -> Decimal:
        cleaned = raw_amount.replace("€", "").replace("\xa0", " ").strip()
        sign = -1 if "-" in cleaned else 1
        cleaned = cleaned.replace("-", "").replace("+", "").strip()

        if "," not in cleaned and "." not in cleaned:
            digits = cleaned.replace(" ", "")
            if digits.isdigit():
                cleaned = (
                    f"{digits[:-2]}.{digits[-2:]}"
                    if len(digits) > 2
                    else f"0.{digits.zfill(2)}"
                )
            else:
                cleaned = digits
        else:
            compact = cleaned.replace(" ", "")
            if "," in compact:
                compact = compact.replace(".", "").replace(",", ".")
            elif "." in compact:
                integer_part, decimal_part = compact.rsplit(".", 1)
                compact = integer_part.replace(".", "") + "." + decimal_part
            cleaned = compact
        try:
            value = Decimal(cleaned)
        except InvalidOperation as exc:
            raise ValueError(
                f"Montant Banque Populaire invalide: {raw_amount!r}"
            ) from exc
        return value * sign

    def _resolve_transaction_amount(
        self,
        *,
        raw_amount: str,
        payee: str,
        block_lines: list[str],
        sepa_detail_amounts: dict[str, Decimal],
    ) -> Decimal:
        if payee.upper().startswith("PRLV SEPA"):
            joined_block = " ".join(
                self._normalize_spaces(line) for line in block_lines if line.strip()
            )
            for reference, amount_value in sepa_detail_amounts.items():
                if reference in joined_block:
                    return amount_value
        try:
            return self._parse_decimal(raw_amount)
        except (ValueError, InvalidOperation):
            pass
        stripped_amount = raw_amount.strip()
        if stripped_amount and self.AMOUNT_SPLIT_LINE_PATTERN.match(
            stripped_amount
        ):
            return self._parse_decimal(raw_amount)
        for candidate_line in block_lines:
            if self.AMOUNT_SPLIT_LINE_PATTERN.match(candidate_line.strip()):
                return self._parse_decimal(
                    f"{raw_amount.rstrip()}{candidate_line.strip()}"
                )
        raise ValueError(
            f"Montant Banque Populaire non parseable apres fallback:"
            f" {raw_amount!r}"
        )

    def _extract_sepa_detail_amounts(self, text: str) -> dict[str, Decimal]:
        marker = "DETAIL DE VOS MOUVEMENTS SEPA"
        upper = text.upper()
        section_index = upper.find(marker)
        if section_index == -1:
            return {}

        lines = [
            self._normalize_spaces(line)
            for line in text[section_index:].splitlines()
            if self._normalize_spaces(line)
        ]
        results: dict[str, Decimal] = {}
        amount_pattern = re.compile(r"(?<![A-Z0-9])\d(?:[\d ]*\d)?[,.]\d{2}")
        reference_pattern = re.compile(r"^(?P<reference>[A-Z0-9]{12,})\b")

        for index, line in enumerate(lines[:-1]):
            amount_matches = amount_pattern.findall(line)
            if not amount_matches:
                continue
            reference_match = reference_pattern.match(lines[index + 1])
            if not reference_match:
                continue
            results[reference_match.group("reference")] = -abs(
                self._parse_decimal(amount_matches[-1])
            )

        return results

    def _create_balance(
        self,
        *,
        file: str,
        line: int,
        entry_date: dt.date,
        account_name: str,
        balance_amount: Decimal,
        document: str,
    ) -> data.Balance:
        meta = data.new_metadata(file, line)
        meta["source"] = "pdfbanquepopulaire"
        meta["document"] = document
        return data.Balance(
            meta=meta,
            date=entry_date,
            account=account_name,
            amount=amount.Amount(balance_amount, "EUR"),
            tolerance=None,
            diff_amount=None,
        )

    def _normalize_spaces(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _guess_counter_account(self, *, payee: str, narration: str) -> Optional[str]:
        upper_payee = payee.upper()
        upper_narration = narration.upper()
        if upper_payee.startswith("COTIS ") and "CONTRAT CARTE" in upper_narration:
            return "Depenses:Banque:Frais"
        return None

    def _is_operations_section_terminator(self, stripped_line: str) -> bool:
        upper = stripped_line.upper()
        return (
            upper.startswith("TOTAL DES MOUVEMENTS")
            or upper.startswith("DETAIL DE VOS MOUVEMENTS SEPA")
            or upper.startswith("(*) SOUS RÉSERVE".upper())
            or upper.startswith("(*) SOUS RESERVE")
            or upper.startswith("CE DOCUMENT NE JUSTIFIE PAS")
        )
