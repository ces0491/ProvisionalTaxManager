"""
Seed database with SARS tax tables for 2025/2026 tax year

Run this script to populate the database with the current tax year's tables.
For subsequent years, either:
1. Run this script again with updated values
2. Use the /admin/tax_tables web interface to add new tax years

Source: SARS Tax Tables 2025/2026
https://www.sars.gov.za/tax-rates/income-tax/rates-of-tax-for-individuals/
"""
from app import app
from models import db, TaxYear, TaxBracket, TaxRebate, MedicalAidCredit
from datetime import date
from decimal import Decimal


def seed_2025_tax_year():
    """Seed 2025/2026 tax year data"""
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()

        # Check if 2025 tax year already exists
        existing = TaxYear.query.filter_by(year=2025).first()
        if existing:
            print("2025 tax year already exists. Skipping...")
            return

        # Create tax year
        tax_year = TaxYear(
            year=2025,
            description='2025/2026 Tax Year',
            start_date=date(2025, 3, 1),
            end_date=date(2026, 2, 28),
            is_active=True
        )
        db.session.add(tax_year)
        db.session.flush()  # Get ID

        # Add tax brackets
        brackets = [
            {'order': 1, 'min': 0, 'max': 237100, 'rate': 0.18, 'base': 0},
            {'order': 2, 'min': 237100, 'max': 370500, 'rate': 0.26, 'base': 42678},
            {'order': 3, 'min': 370500, 'max': 512800, 'rate': 0.31, 'base': 77362},
            {'order': 4, 'min': 512800, 'max': 673000, 'rate': 0.36, 'base': 121475},
            {'order': 5, 'min': 673000, 'max': 857900, 'rate': 0.39, 'base': 179147},
            {'order': 6, 'min': 857900, 'max': 1817000, 'rate': 0.41, 'base': 251258},
            {'order': 7, 'min': 1817000, 'max': None, 'rate': 0.45, 'base': 644489},
        ]

        for bracket_data in brackets:
            bracket = TaxBracket(
                tax_year_id=tax_year.id,
                min_income=Decimal(str(bracket_data['min'])),
                max_income=Decimal(str(bracket_data['max'])) if bracket_data['max'] else None,
                rate=Decimal(str(bracket_data['rate'])),
                base_tax=Decimal(str(bracket_data['base'])),
                bracket_order=bracket_data['order']
            )
            db.session.add(bracket)

        # Add rebates
        rebates = [
            {'type': 'primary', 'min_age': 0, 'amount': 17235,
             'description': 'Primary rebate (all taxpayers)'},
            {'type': 'secondary', 'min_age': 65, 'amount': 9444,
             'description': 'Secondary rebate (65 years and older)'},
            {'type': 'tertiary', 'min_age': 75, 'amount': 3145,
             'description': 'Tertiary rebate (75 years and older)'},
        ]

        for rebate_data in rebates:
            rebate = TaxRebate(
                tax_year_id=tax_year.id,
                rebate_type=rebate_data['type'],
                min_age=rebate_data['min_age'],
                amount=Decimal(str(rebate_data['amount'])),
                description=rebate_data['description']
            )
            db.session.add(rebate)

        # Add medical aid credits
        credits = [
            {'type': 'main', 'monthly_amount': 364,
             'description': 'Main member monthly credit'},
            {'type': 'first_dependent', 'monthly_amount': 246,
             'description': 'First dependent monthly credit'},
            {'type': 'additional', 'monthly_amount': 246,
             'description': 'Additional dependents monthly credit (each)'},
        ]

        for credit_data in credits:
            credit = MedicalAidCredit(
                tax_year_id=tax_year.id,
                credit_type=credit_data['type'],
                monthly_amount=Decimal(str(credit_data['monthly_amount'])),
                description=credit_data['description']
            )
            db.session.add(credit)

        db.session.commit()
        print("Successfully seeded 2025/2026 tax year data")
        print(f"  - {len(brackets)} tax brackets")
        print(f"  - {len(rebates)} rebates")
        print(f"  - {len(credits)} medical aid credits")


if __name__ == '__main__':
    seed_2025_tax_year()
