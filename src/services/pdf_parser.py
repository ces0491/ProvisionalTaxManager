import pdfplumber
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

class BankStatementParser:
    """Parse Standard Bank PDF statements"""

    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.account_type = None
        self.account_number = None
        self.start_date = None
        self.end_date = None
        self.transactions = []

    def parse(self):
        """Main parsing method - detects account type and parses accordingly"""
        with pdfplumber.open(self.pdf_path) as pdf:
            first_page_text = pdf.pages[0].extract_text()
            first_page_text_upper = first_page_text.upper()

            # Detect account type (case-insensitive)
            if 'SIGNATURE' in first_page_text_upper or 'CHEQUE' in first_page_text_upper:
                self.account_type = 'cheques'
                return self._parse_cheques_account(pdf)
            elif ('CREDIT CARD' in first_page_text_upper or
                  'CARD DIVISION' in first_page_text_upper or
                  'WORLD CITIZEN CARD' in first_page_text_upper or
                  ('CARD' in first_page_text_upper and 'ACCOUNT 5520' in first_page_text_upper)):
                self.account_type = 'credit_card'
                return self._parse_credit_card(pdf)
            elif 'HOUSING LOAN' in first_page_text_upper or 'HOME LOAN' in first_page_text_upper:
                self.account_type = 'mortgage'
                return self._parse_mortgage(pdf)
            else:
                raise ValueError("Unknown account type in PDF")

    def _parse_cheques_account(self, pdf):
        """Parse cheques/signature account statement"""
        # Detect which format this statement uses
        first_page_text = pdf.pages[0].extract_text()

        # Check if it's the 6-month summary format (has "Payments" and "Deposits" columns)
        if 'Payments' in first_page_text and 'Deposits' in first_page_text:
            return self._parse_6month_format(pdf)
        else:
            return self._parse_monthly_detailed_format(pdf)

    def _parse_monthly_detailed_format(self, pdf):
        """Parse monthly detailed statement format (In/Out/Bank fees columns)"""
        transactions = []

        for page in pdf.pages:
            text = page.extract_text()

            # Extract account number from first page (try different patterns)
            if not self.account_number:
                # Try "Account: Signature 10-21-709-576-1" format
                acc_match = re.search(r'Account:\s+(?:Signature|Cheque)\s+([\d\-\s]+)', text)
                if acc_match:
                    self.account_number = acc_match.group(1).strip().replace(' ', '').replace('-', '')
                else:
                    # Try "Account number: ..." format
                    acc_match = re.search(r'Account number:\s*(\d+\s+\d+\s+\d+\s+\d+\s+\d+)', text)
                    if acc_match:
                        self.account_number = acc_match.group(1).replace(' ', '')

            # Extract date range (try different patterns)
            if not self.start_date:
                # Try "Transaction date range: DD Month YYYY - DD Month YYYY" format
                date_match = re.search(r'Transaction date range:\s*(\d+\s+\w+\s+\d+)\s*-\s*(\d+\s+\w+\s+\d+)', text)
                if date_match:
                    self.start_date = self._parse_date(date_match.group(1))
                    self.end_date = self._parse_date(date_match.group(2))
                else:
                    # Try "From: ... To: ..." format
                    date_match = re.search(r'From:\s*(\d+\s+\w+\s+\d+).*?To:\s*(\d+\s+\w+\s+\d+)', text, re.DOTALL)
                    if date_match:
                        self.start_date = self._parse_date(date_match.group(1))
                        self.end_date = self._parse_date(date_match.group(2))

            # Extract transactions from table
            lines = text.split('\n')
            i = 0
            # Track current year context
            current_year = None
            while i < len(lines):
                line = lines[i]

                # Check if this line is a year marker (e.g., "2024" or "2025")
                if re.match(r'^\d{4}$', line.strip()):
                    year_str = line.strip()
                    current_year = year_str[-2:]  # Get last 2 digits
                    i += 1
                    continue

                # Look for date pattern at start of line (e.g., "01 Apr" or "01 Apr 25")
                date_match = re.match(r'^(\d{1,2}\s+\w{3})(?:\s+\d{2})?\s+(.+)', line)
                if date_match:
                    date_str = date_match.group(1)
                    rest = date_match.group(2)

                    # Add year if we have it from context
                    if current_year:
                        full_date_str = f"{date_str} {current_year}"
                    else:
                        # Try to extract year from the line itself
                        year_in_line = re.search(r'^(\d{1,2}\s+\w{3}\s+\d{2})', line)
                        if year_in_line:
                            full_date_str = year_in_line.group(1)
                        else:
                            full_date_str = date_str + " 25"  # default to 2025

                    # Parse the transaction
                    transaction = self._parse_transaction_line(full_date_str, rest)
                    if transaction:
                        transactions.append(transaction)

                i += 1

        self.transactions = transactions
        return {
            'account_type': self.account_type,
            'account_number': self.account_number,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'transactions': transactions
        }

    def _parse_6month_format(self, pdf):
        """Parse 6-month summary statement format (Payments/Deposits columns)"""
        transactions = []

        for page in pdf.pages:
            text = page.extract_text()

            # Extract account number from first page
            if not self.account_number:
                acc_match = re.search(r'Account number:\s*(\d+\s+\d+\s+\d+\s+\d+\s+\d+)', text)
                if acc_match:
                    self.account_number = acc_match.group(1).replace(' ', '')

            # Extract date range
            if not self.start_date:
                date_match = re.search(r'From:\s*(\d+\s+\w+\s+\d+).*?To:\s*(\d+\s+\w+\s+\d+)', text, re.DOTALL)
                if date_match:
                    self.start_date = self._parse_date(date_match.group(1))
                    self.end_date = self._parse_date(date_match.group(2))

            # Extract transactions from table
            lines = text.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i]
                # Look for date pattern at start of line (e.g., "23 May 25")
                date_match = re.match(r'^(\d{1,2}\s+\w{3}\s+\d{2})\s+(.+)', line)
                if date_match:
                    date_str = date_match.group(1)
                    rest = date_match.group(2)

                    # In 6-month format, description might be on the next line
                    description_line = rest
                    # Check if next line is a description continuation (doesn't start with date)
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line and not re.match(r'^\d{1,2}\s+\w{3}\s+\d{2}', next_line):
                            # Next line is likely a description detail, skip certain lines
                            if not next_line.startswith('Customer Care') and not next_line.startswith('The Standard'):
                                description_line = rest + ' ' + next_line

                    # Parse the transaction for 6-month format
                    transaction = self._parse_6month_transaction_line(date_str, description_line)
                    if transaction:
                        transactions.append(transaction)

                i += 1

        self.transactions = transactions
        return {
            'account_type': self.account_type,
            'account_number': self.account_number,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'transactions': transactions
        }

    def _parse_6month_transaction_line(self, date_str, rest):
        """Parse a single transaction line from 6-month format"""
        # Remove extra whitespace
        rest = ' '.join(rest.split())

        # In 6-month format, amounts can be negative (payments) or positive (deposits)
        # Pattern: Description amount balance
        # Amount can be: -1,234.56 or 1,234.56

        parts = rest.split()
        if len(parts) < 2:
            return None

        # Last 1 or 2 parts should be numbers
        amounts = []
        description_parts = []

        for i, part in enumerate(parts):
            # Remove commas for number detection
            clean_part = part.replace(',', '')
            # Check if this looks like an amount
            if re.match(r'^-?\d+\.\d{2}$', clean_part):
                amounts.append(part)
            else:
                description_parts.append(part)

        if not amounts:
            return None

        # First amount is the transaction amount (could be last item before balance)
        # If we have 2 amounts, first is transaction, second is balance
        amount_str = amounts[0].replace(',', '')

        try:
            amount = Decimal(amount_str)
        except (ValueError, InvalidOperation):
            return None

        description = ' '.join(description_parts)

        # Parse date
        transaction_date = self._parse_date(date_str)

        return {
            'date': transaction_date,
            'description': description,
            'amount': amount
        }

    def _parse_credit_card(self, pdf):
        """Parse credit card statement"""
        # Detect which format this statement uses
        first_page_text = pdf.pages[0].extract_text()

        # Check if it's the summary format (has "Payments" and "Deposits" columns)
        if 'Payments' in first_page_text and 'Deposits' in first_page_text:
            return self._parse_credit_card_summary_format(pdf)
        else:
            return self._parse_credit_card_detailed_format(pdf)

    def _parse_credit_card_detailed_format(self, pdf):
        """Parse detailed credit card statement format"""
        transactions = []

        for page in pdf.pages:
            text = page.extract_text()

            # Extract account number
            if not self.account_number:
                acc_match = re.search(r'Account number:\s*([\d\*\s]+)', text)
                if acc_match:
                    self.account_number = acc_match.group(1).replace(' ', '')
                else:
                    # Try pattern like "Account: Credit Card 5520-xxxx-xxxx-9115"
                    acc_match = re.search(r'Account:\s*Credit Card\s*([\d\-x]+)', text)
                    if acc_match:
                        self.account_number = acc_match.group(1).replace('-', '').replace('x', '*')
                    else:
                        # Try pattern like "Account 5520 **** **** 7880"
                        acc_match = re.search(r'Account\s+(5520\s*[\*\d]+\s*[\*\d]+\s*[\*\d]+)', text)
                        if acc_match:
                            self.account_number = acc_match.group(1).replace(' ', '')

            # Extract date range
            if not self.start_date:
                # Try "Transaction date range: DD Month YYYY - DD Month YYYY" format
                date_match = re.search(r'Transaction date range:\s*(\d+\s+\w+\s+\d+)\s*-\s*(\d+\s+\w+\s+\d+)', text)
                if date_match:
                    self.start_date = self._parse_date(date_match.group(1))
                    self.end_date = self._parse_date(date_match.group(2))
                else:
                    # Try "Statement Period DD Mon YY to DD Mon YY" format
                    date_match = re.search(r'Statement Period\s+(\d+\s+\w+\s+\d+)\s+to\s+(\d+\s+\w+\s+\d+)', text)
                    if date_match:
                        self.start_date = self._parse_date(date_match.group(1))
                        self.end_date = self._parse_date(date_match.group(2))
                    else:
                        # Try "From: ... To: ..." format
                        date_match = re.search(r'From:\s*(\d+\s+\w+\s+\d+).*?To:\s*(\d+\s+\w+\s+\d+)', text, re.DOTALL)
                        if date_match:
                            self.start_date = self._parse_date(date_match.group(1))
                            self.end_date = self._parse_date(date_match.group(2))

            # Extract transactions
            lines = text.split('\n')
            i = 0
            # Track current year context
            current_year = None
            while i < len(lines):
                line = lines[i]

                # Check if this line is a year marker (e.g., "2024" or "2025")
                if re.match(r'^\d{4}$', line.strip()):
                    year_str = line.strip()
                    current_year = year_str[-2:]  # Get last 2 digits
                    i += 1
                    continue

                # Look for date pattern at start of line (e.g., "01 Apr" or "01 Apr 25")
                date_match = re.match(r'^(\d{1,2}\s+\w{3})(?:\s+\d{2})?\s+(.+)', line)
                if date_match:
                    date_str = date_match.group(1)
                    rest = date_match.group(2)

                    # If year is in the date string, use it; otherwise use context year
                    full_date_match = re.match(r'^(\d{1,2}\s+\w{3}\s+\d{2})', line)
                    if full_date_match:
                        full_date_str = full_date_match.group(1)
                    else:
                        # Use current_year if available, otherwise extract from statement dates
                        if current_year:
                            full_date_str = f"{date_str} {current_year}"
                        elif self.start_date:
                            # Use year from start_date
                            year = str(self.start_date.year)[-2:]
                            full_date_str = f"{date_str} {year}"
                        else:
                            full_date_str = f"{date_str} 25"  # fallback

                    # Check if description is on the next line
                    # If rest only contains amounts (no alphabetic description), check next line
                    rest_has_description = any(c.isalpha() for c in rest)
                    if not rest_has_description and i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        # Make sure next line isn't another transaction line
                        if next_line and not re.match(r'^\d{1,2}\s+\w{3}', next_line):
                            rest = next_line + ' ' + rest
                            i += 1  # Skip the next line since we consumed it

                    transaction = self._parse_transaction_line(full_date_str, rest)
                    if transaction:
                        # Credit card transactions are typically expenses (negative)
                        if transaction['amount'] > 0:
                            transaction['amount'] = -transaction['amount']
                        transactions.append(transaction)

                i += 1

        self.transactions = transactions
        return {
            'account_type': self.account_type,
            'account_number': self.account_number,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'transactions': transactions
        }

    def _parse_credit_card_summary_format(self, pdf):
        """Parse credit card summary statement format (Payments/Deposits columns)"""
        transactions = []

        for page in pdf.pages:
            text = page.extract_text()

            # Extract account number (may be masked with asterisks)
            if not self.account_number:
                acc_match = re.search(r'Account number:\s*([\d\*\s]+)', text)
                if acc_match:
                    self.account_number = acc_match.group(1).replace(' ', '')
                else:
                    # Try pattern like "Account: Credit Card 5520-xxxx-xxxx-9115"
                    acc_match = re.search(r'Account:\s*Credit Card\s*([\d\-x]+)', text)
                    if acc_match:
                        self.account_number = acc_match.group(1).replace('-', '').replace('x', '*')
                    else:
                        # Try pattern like "Account 5520 **** **** 7880"
                        acc_match = re.search(r'Account\s+(5520\s*[\*\d]+\s*[\*\d]+\s*[\*\d]+)', text)
                        if acc_match:
                            self.account_number = acc_match.group(1).replace(' ', '')

            # Extract date range
            if not self.start_date:
                # Try "Transaction date range: DD Month YYYY - DD Month YYYY" format
                date_match = re.search(r'Transaction date range:\s*(\d+\s+\w+\s+\d+)\s*-\s*(\d+\s+\w+\s+\d+)', text)
                if date_match:
                    self.start_date = self._parse_date(date_match.group(1))
                    self.end_date = self._parse_date(date_match.group(2))
                else:
                    # Try "Statement Period DD Mon YY to DD Mon YY" format
                    date_match = re.search(r'Statement Period\s+(\d+\s+\w+\s+\d+)\s+to\s+(\d+\s+\w+\s+\d+)', text)
                    if date_match:
                        self.start_date = self._parse_date(date_match.group(1))
                        self.end_date = self._parse_date(date_match.group(2))
                    else:
                        # Try "From: ... To: ..." format
                        date_match = re.search(r'From:\s*(\d+\s+\w+\s+\d+).*?To:\s*(\d+\s+\w+\s+\d+)', text, re.DOTALL)
                        if date_match:
                            self.start_date = self._parse_date(date_match.group(1))
                            self.end_date = self._parse_date(date_match.group(2))

            # Extract transactions from table
            lines = text.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i]
                # Look for date pattern at start of line
                date_match = re.match(r'^(\d{1,2}\s+\w{3}\s+\d{2})\s+(.+)', line)
                if date_match:
                    date_str = date_match.group(1)
                    rest = date_match.group(2)

                    # In summary format, description might be on the next line
                    description_line = rest
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line and not re.match(r'^\d{1,2}\s+\w{3}\s+\d{2}', next_line):
                            if not next_line.startswith('Customer Care') and not next_line.startswith('The Standard'):
                                description_line = rest + ' ' + next_line

                    # Parse the transaction
                    transaction = self._parse_6month_transaction_line(date_str, description_line)
                    if transaction:
                        transactions.append(transaction)

                i += 1

        self.transactions = transactions
        return {
            'account_type': self.account_type,
            'account_number': self.account_number,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'transactions': transactions
        }

    def _parse_mortgage(self, pdf):
        """Parse mortgage/home loan statement"""
        transactions = []

        for page in pdf.pages:
            text = page.extract_text()

            # Extract account number (try different patterns)
            if not self.account_number:
                # Try pattern like "53-733-325-8" or "10 21 709 576 1"
                acc_match = re.search(r'Account[:\s]+(?:Housing Loan|Home Loan)?\s*([\d\s\-]+)', text)
                if acc_match:
                    self.account_number = acc_match.group(1).strip().replace(' ', '').replace('-', '')
                else:
                    acc_match = re.search(r'Account number:\s*(\d+\s+\d+\s+\d+\s+\d+)', text)
                    if acc_match:
                        self.account_number = acc_match.group(1).replace(' ', '')

            # Extract date range
            if not self.start_date:
                # Try "Transaction date range: DD Month YYYY - DD Month YYYY" format
                date_match = re.search(r'Transaction date range:\s*(\d+\s+\w+\s+\d+)\s*-\s*(\d+\s+\w+\s+\d+)', text)
                if date_match:
                    self.start_date = self._parse_date(date_match.group(1))
                    self.end_date = self._parse_date(date_match.group(2))
                else:
                    # Try "From: ... To: ..." format
                    date_match = re.search(r'From:\s*(\d+\s+\w+\s+\d+).*?To:\s*(\d+\s+\w+\s+\d+)', text, re.DOTALL)
                    if date_match:
                        self.start_date = self._parse_date(date_match.group(1))
                        self.end_date = self._parse_date(date_match.group(2))

            # Extract transactions
            lines = text.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i]
                # Look for date pattern at start of line (could be standalone or with description)
                date_match = re.match(r'^(\d{1,2}\s+\w{3})\s+(.+)', line)
                if date_match:
                    date_str = date_match.group(1)
                    rest = date_match.group(2)

                    # Get the year from context (look at previous lines for year marker like "2024" or "2025")
                    year = "25"  # default
                    for j in range(max(0, i-10), i):
                        if re.match(r'^\d{4}$', lines[j].strip()):
                            year_full = lines[j].strip()
                            year = year_full[-2:]
                            break

                    full_date_str = f"{date_str} {year}"

                    # Check if next line is a continuation of the description
                    description_line = rest
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        # If next line doesn't start with a date and isn't empty, it's likely a continuation
                        if next_line and not re.match(r'^\d{1,2}\s+\w{3}', next_line) and not next_line.startswith('Customer Care'):
                            description_line = rest + ' ' + next_line

                    transaction = self._parse_transaction_line(full_date_str, description_line)
                    if transaction:
                        transactions.append(transaction)

                i += 1

        self.transactions = transactions
        return {
            'account_type': self.account_type,
            'account_number': self.account_number,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'transactions': transactions
        }

    def _parse_transaction_line(self, date_str, rest):
        """Parse a single transaction line"""
        # Remove extra whitespace
        rest = ' '.join(rest.split())

        # Try to extract description and amounts
        # Pattern: Description [-]amount [balance]
        # Amounts can be like: -1,234.56 or 1,234.56 or "- 1,234.56" or "+ 1,234.56"

        parts = rest.split()
        if len(parts) < 2:
            return None

        # Last 1 or 2 parts should be numbers (amount and possibly balance)
        # Also handle cases where sign is separate: "- 199.98" becomes ["-", "199.98"]
        amounts = []
        description_parts = []

        i = 0
        while i < len(parts):
            part = parts[i]

            # Check if this is a standalone sign
            if part in ['-', '+'] and i + 1 < len(parts):
                # Next part might be the number
                next_part = parts[i + 1]
                if re.match(r'^[\d,]+\.\d{2}$', next_part):
                    # Combine sign with number
                    amounts.append(part + next_part.replace(',', '').replace(' ', ''))
                    i += 2  # Skip both parts
                    continue
                else:
                    description_parts.append(part)
                    i += 1
                    continue

            # Check if this looks like an amount (has digits and possibly comma/decimal)
            clean_part = part.replace(',', '').replace(' ', '')
            if re.match(r'^-?[\d]+\.\d{2}$', clean_part):
                amounts.append(clean_part)
                i += 1
            else:
                description_parts.append(part)
                i += 1

        if not amounts:
            return None

        # First amount is the transaction amount
        amount_str = amounts[0].replace(',', '').replace(' ', '')

        try:
            # Handle negative sign
            if amount_str.startswith('-'):
                amount = Decimal(amount_str[1:])
                amount = -amount
            elif amount_str.startswith('+'):
                amount = Decimal(amount_str[1:])
            else:
                amount = Decimal(amount_str)
        except (ValueError, InvalidOperation):
            return None

        description = ' '.join(description_parts)

        # Parse date
        try:
            transaction_date = self._parse_date(date_str)
        except (ValueError, AttributeError):
            return None

        return {
            'date': transaction_date,
            'description': description,
            'amount': amount
        }

    def _parse_date(self, date_str):
        """Parse date string like '01 Apr 25' to Python date"""
        # Clean up the string
        date_str = date_str.strip()

        # Try different date formats
        formats = [
            '%d %b %y',  # 01 Apr 25
            '%d %B %y',  # 01 April 25
            '%d %b %Y',  # 01 Apr 2025
            '%d %B %Y',  # 01 April 2025
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        raise ValueError(f"Could not parse date: {date_str}")


def detect_duplicates(transactions_list):
    """
    Detect duplicate transactions across multiple statements
    Returns list of (transaction1_index, transaction2_index, similarity_score)
    """
    duplicates = []

    for i, trans1 in enumerate(transactions_list):
        for j, trans2 in enumerate(transactions_list[i+1:], start=i+1):
            # Same date
            if trans1['date'] == trans2['date']:
                # Same amount
                if trans1['amount'] == trans2['amount']:
                    # Similar description (allow for minor differences)
                    desc1 = trans1['description'].upper()
                    desc2 = trans2['description'].upper()

                    if desc1 == desc2:
                        duplicates.append((i, j, 1.0))  # Exact match
                    elif desc1 in desc2 or desc2 in desc1:
                        duplicates.append((i, j, 0.8))  # Partial match

    return duplicates
