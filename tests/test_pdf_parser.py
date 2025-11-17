"""
Tests for pdf_parser module
"""
from datetime import date

from pdf_parser import BankStatementParser, detect_duplicates


class TestBankStatementParser:
    """Test PDF bank statement parsing"""

    def test_parse_date(self):
        """Test date parsing"""
        parser = BankStatementParser('dummy.pdf')

        # Test various date formats
        assert parser._parse_date('15 Mar 25') == date(2025, 3, 15)
        assert parser._parse_date('01 Jan 25') == date(2025, 1, 1)
        assert parser._parse_date('31 Dec 25') == date(2025, 12, 31)

    def test_parse_date_various_formats(self):
        """Test parsing various date formats"""
        parser = BankStatementParser('dummy.pdf')

        # Test full year format
        assert parser._parse_date('01 Jan 2025') == date(2025, 1, 1)
        assert parser._parse_date('31 Dec 2025') == date(2025, 12, 31)

        # Test abbreviated month names
        assert parser._parse_date('15 Mar 25') == date(2025, 3, 15)
        assert parser._parse_date('01 Apr 25') == date(2025, 4, 1)


class TestDetectDuplicates:
    """Test duplicate transaction detection"""

    def test_detect_exact_duplicates(self):
        """Test detection of exact duplicate transactions"""
        transactions = [
            {
                'id': 1,
                'date': date(2025, 3, 15),
                'description': 'NETFLIX.COM',
                'amount': -15.99
            },
            {
                'id': 2,
                'date': date(2025, 3, 15),
                'description': 'NETFLIX.COM',
                'amount': -15.99
            },
            {
                'id': 3,
                'date': date(2025, 3, 20),
                'description': 'DIFFERENT',
                'amount': -100.00
            }
        ]

        duplicates = detect_duplicates(transactions)

        # Should find one duplicate pair
        assert len(duplicates) >= 1

        # Check the duplicate pair
        idx1, idx2, score = duplicates[0]
        assert score > 0.9  # High confidence
        assert transactions[idx1]['description'] == transactions[idx2]['description']

    def test_detect_similar_duplicates(self):
        """Test detection of similar transactions with partial description match"""
        transactions = [
            {
                'id': 1,
                'date': date(2025, 3, 15),
                'description': 'GOOGLE GSUITE',
                'amount': -100.00
            },
            {
                'id': 2,
                'date': date(2025, 3, 15),
                'description': 'GOOGLE GSUITE SHEETSOL EXTRA',  # Contains first
                'amount': -100.00
            },
        ]

        duplicates = detect_duplicates(transactions)

        # Should find similar transactions (partial match with score 0.8)
        assert len(duplicates) >= 1
        if duplicates:
            idx1, idx2, score = duplicates[0]
            assert score == 0.8  # Partial match (one contains the other)

    def test_no_duplicates(self):
        """Test with no duplicates"""
        transactions = [
            {
                'id': 1,
                'date': date(2025, 3, 15),
                'description': 'NETFLIX.COM',
                'amount': -15.99
            },
            {
                'id': 2,
                'date': date(2025, 3, 20),
                'description': 'SPOTIFY',
                'amount': -9.99
            },
            {
                'id': 3,
                'date': date(2025, 3, 25),
                'description': 'GOOGLE',
                'amount': -100.00
            }
        ]

        duplicates = detect_duplicates(transactions)

        # Should not find any duplicates with high confidence
        high_confidence = [d for d in duplicates if d[2] > 0.9]
        assert len(high_confidence) == 0

    def test_different_amounts_not_duplicates(self):
        """Test that transactions with different amounts are not duplicates"""
        transactions = [
            {
                'id': 1,
                'date': date(2025, 3, 15),
                'description': 'NETFLIX.COM',
                'amount': -15.99
            },
            {
                'id': 2,
                'date': date(2025, 3, 15),
                'description': 'NETFLIX.COM',
                'amount': -99.99  # Different amount
            },
        ]

        duplicates = detect_duplicates(transactions)

        # Should not be considered duplicates due to amount difference
        high_confidence = [d for d in duplicates if d[2] > 0.9]
        assert len(high_confidence) == 0

    def test_different_dates_not_duplicates(self):
        """Test that transactions on different dates are less likely duplicates"""
        transactions = [
            {
                'id': 1,
                'date': date(2025, 3, 15),
                'description': 'NETFLIX.COM',
                'amount': -15.99
            },
            {
                'id': 2,
                'date': date(2025, 4, 15),  # Different month
                'description': 'NETFLIX.COM',
                'amount': -15.99
            },
        ]

        duplicates = detect_duplicates(transactions)

        # Different dates should reduce confidence
        if duplicates:
            for _, _, score in duplicates:
                # Score should be lower for different dates
                assert score < 1.0
