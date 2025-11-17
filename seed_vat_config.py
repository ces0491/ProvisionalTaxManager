"""
Seed VAT configuration with current and historical rates

Current VAT rate: 15% (effective from 1 April 2018)
Previous rate: 14% (1 April 1993 - 31 March 2018)
"""
from app import app
from models import db, VATConfig
from datetime import date
from decimal import Decimal


def seed_vat_rates():
    """Seed VAT rates (historical and current)"""
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()

        # Check if any VAT config exists
        existing = VATConfig.query.first()
        if existing:
            print("VAT configuration already exists. Skipping...")
            return

        # Historical rate: 14% (1993-2018)
        vat_14 = VATConfig(
            effective_from=date(1993, 4, 1),
            effective_to=date(2018, 3, 31),
            standard_rate=Decimal('0.14'),
            is_active=False,
            notes='VAT rate 14% - Superseded by 15% rate in 2018'
        )
        db.session.add(vat_14)

        # Current rate: 15% (2018-present)
        vat_15 = VATConfig(
            effective_from=date(2018, 4, 1),
            effective_to=None,  # NULL = current rate
            standard_rate=Decimal('0.15'),
            is_active=True,
            notes='VAT rate 15% - Increased from 14% per 2018 Budget'
        )
        db.session.add(vat_15)

        db.session.commit()
        print("Successfully seeded VAT configuration")
        print("  - Historical rate: 14% (1993-2018)")
        print("  - Current rate: 15% (2018-present)")


if __name__ == '__main__':
    seed_vat_rates()
