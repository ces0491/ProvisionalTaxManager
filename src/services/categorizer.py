"""
Transaction categorization engine
Based on provisional_tax_calc_system.md rules
"""
import re

# Category definitions
CATEGORIES = {
    # INCOME
    'income': {
        'name': 'Income',
        'type': 'income',
        'patterns': ['PRECISE DIGITAL', 'PRECISE DIGITA'],
    },

    # BUSINESS EXPENSES - Alphabetical order
    'advertising_marketing': {
        'name': 'Advertising/Marketing',
        'type': 'business_expense',
        'patterns': ['FACEBOOK ADS', 'GOOGLE ADS', 'LINKEDIN', 'MARKETING'],
    },
    'startup_costs': {
        'name': 'Business Start-up Costs',
        'type': 'business_expense',
        'patterns': ['CIPC', 'COMPANY REGISTRATION'],
    },
    'capital_equipment': {
        'name': 'Capital Equipment',
        'type': 'business_expense',
        'patterns': ['APPLE STORE', 'INCREDIBLE CONNECTION', 'COMPUTER', 'LAPTOP'],
    },
    'cleaning': {
        'name': 'Cleaning',
        'type': 'business_expense',
        'patterns': ['CLEANING SERVICE', 'DOMESTIC'],
    },
    'coffee_meals': {
        'name': 'Coffee/Meals (Business)',
        'type': 'business_expense',
        'patterns': [
            'BOOTLEGGER', 'SHIFT ESPRESS', 'SHIFT ESPR',
            'FORESTERS ARM',
            'BOSSA',
            'OUMEUL BAKERY',
        ],
    },
    'education': {
        'name': 'Education (UCT)',
        'type': 'business_expense',
        'patterns': ['PAYU.*UC', 'UNIVERSITY OF', 'QUALIFYD', 'PAYFAST.*QUALI'],
    },
    'entertainment_business': {
        'name': 'Entertainment (Business)',
        'type': 'business_expense',
        'patterns': [],  # Populated via manual categorization or rules
    },
    'banking_fees': {
        'name': 'Fees/Bank charges',
        'type': 'business_expense',
        'patterns': [
            'FIXED MONTHLY FEE',
            'TELETRANSMISSION',
            'FEE-TELETRANSMISSION',
            'ADMINISTRATION FEE',
            'UCOUNT',
            'SERVICE FEE',
            'HONOURING FEE',
            'OVERDRAFT SERVICE FEE',
            'ELECTRONIC PMT/TRNSF FEE',
            'INTERNATIONAL TXN FEE',
            'CASH FINANCE CHARGE',
            'EXCESS INTEREST',
            'CREDIT INTEREST',
            'CREDIT CARD INTEREST',
            'INTEREST CHARGE',
            'FINANCE CHARGE',
            'LATE PAYMENT FEE',
            'OVERLIMIT FEE',
        ],
    },
    'insurance': {
        'name': 'Insurance',
        'type': 'business_expense',
        'patterns': ['DISCINSURE', 'DISCLIFE', 'INSURANCE PREMIUM'],
    },
    'interest_mortgage': {
        'name': 'Interest (Mortgage)',
        'type': 'business_expense',
        'patterns': ['SYSTEM INTEREST DEBIT', 'INTEREST DEBIT'],
    },
    'internet': {
        'name': 'Internet (Afrihost)',
        'type': 'business_expense',
        'patterns': ['AFRIHOST'],
    },
    'legal_fees': {
        'name': 'Legal Fees',
        'type': 'business_expense',
        'patterns': ['ATTORNEY', 'LEGAL', 'LAW FIRM', 'ADVOCATE'],
    },
    'maintenance': {
        'name': 'Maintenance',
        'type': 'business_expense',
        'patterns': [
            'POINT GARDEN',
            'LIQUID RAIN', 'JOYCE THINDWA',
            'TRIP ELECTRICAL',
            'FIREWORX',
            'DRAIN UNBLOCK',
            'ABSOLUTE FENCING',
            'CITY OF CAPE TOWN BUILDING', 'CITY BUILDING',
            'WOODENSCAPES', 'LIVEWIRE SYSTEMS',
            'DONALD BEKKER',
        ],
    },
    'medical_aid': {
        'name': 'Medical Aid',
        'type': 'business_expense',
        'patterns': ['DISC PREM', 'MEDICAL AID CONTRIBUTION', 'DISCOVERY'],
    },
    'medical_fees': {
        'name': 'Medical Fees',
        'type': 'business_expense',
        'patterns': ['DR MALCOL', 'SPECSAVERS', 'CLICKS PINELA'],
    },
    'municipal': {
        'name': 'Municipal',
        'type': 'business_expense',
        'patterns': ['CITY OF CAPE TOWN', 'EASYPAY'],
    },
    'office_equipment': {
        'name': 'Office Equipment',
        'type': 'business_expense',
        'patterns': ['PNA PINELANDS'],
    },
    'retirement_other': {
        'name': 'Other Retirement',
        'type': 'business_expense',
        'patterns': ['OM UNITTRU', 'OLD MUTUAL INVEST', 'OLDGM.*INVEST'],
    },
    'phone_data': {
        'name': 'Phone/Data',
        'type': 'business_expense',
        'patterns': ['MTN', 'MTN PREPAID', 'MTN SP'],
    },
    'printing': {
        'name': 'Printing',
        'type': 'business_expense',
        'patterns': ['ROZPRINT'],
    },
    'professional_services': {
        'name': 'Professional Services',
        'type': 'business_expense',
        'patterns': [
            'PERSONAL TAX SERVIC',
            'SHEET SOLVED',
        ],
    },
    'retirement_10x': {
        'name': 'Retirement (10X)',
        'type': 'business_expense',
        'patterns': ['10XRA COL', '10X'],
    },
    'technology_software': {
        'name': 'Technology/Software',
        'type': 'business_expense',
        'patterns': [
            'GOOGLE GSUITE', 'GSUITE', 'GOOGLE ONE', 'GOOGLE WORKSPACE',
            'MSFT', 'MICROSOFT',
            'CLAUDE.AI',
            'RENDER.COM',
            'GODADDY', 'DNH\\*GODADDY',
            'PAYFAST.*TOPC', 'TOP CODER',
            'ADOBE',
        ],
    },
    'travel_accommodation': {
        'name': 'Travel/Accommodation',
        'type': 'business_expense',
        'patterns': ['AIRBNB', 'BOOKING.COM', 'HOTELS', 'GUEST HOUSE', 'LODGE'],
    },
    'uniforms_workwear': {
        'name': 'Uniforms/Workwear',
        'type': 'business_expense',
        'patterns': [],  # Populated via manual categorization
    },

    # PERSONAL EXPENSES (Non-deductible) - Alphabetical order
    'cash_withdrawal': {
        'name': 'Cash Withdrawal',
        'type': 'personal_expense',
        'patterns': ['CASH WITHDRAWAL', 'ATM WITHDRAWAL', 'CASH.*ATM', 'AUTOBANK CASH'],
    },
    'clothing': {
        'name': 'Clothing',
        'type': 'personal_expense',
        'patterns': [
            'MR PRICE', 'MRPRICE', 'ACKERMANS', 'JET STORE', 'EDGARS', 'TRUWORTHS',
            'FOSCHINI', 'MARKHAM', 'ZARA', 'H&M', 'COTTON ON', 'CAPE UNION',
            'SPORTSCENE', 'TOTALSPORTS', 'DUE SOUTH', 'SHOES', 'FOOTWEAR',
        ],
    },
    'credit_repayments': {
        'name': 'Credit Repayments',
        'type': 'personal_expense',
        'patterns': [
            'SBSA RCP', 'REVOLVING CREDIT', 'RCP PAYMENT',
            'CREDIT CARD PAYMENT', 'CC PAYMENT',
        ],
    },
    'entertainment_personal': {
        'name': 'Entertainment (Personal)',
        'type': 'personal_expense',
        'patterns': [
            'NETFLIX',
            'GOOGLE YOUTUBE', 'YOUTUBE',
            'APPLE.COM', 'ITUNE',
            'SABC TV',
            'PLAYSTATION', 'PLAYSTATIONNETWORK',
            'NUMETRO', 'STER.*KINEKOR', 'CINEMA',
            'KIRSTENBOSCH', 'BOTANICAL',
            'HELDERBERG PLAAS',
        ],
    },
    'fuel': {
        'name': 'Fuel',
        'type': 'personal_expense',
        'patterns': [
            'SHELL', 'CALTEX', 'SASOL', 'TOTAL GARAGE', 'BP GARAGE',
            'PETROL', 'DIESEL', 'FUEL', 'FILLING STATION',
        ],
    },
    'groceries': {
        'name': 'Groceries',
        'type': 'personal_expense',
        'patterns': [
            'CHECKERS', 'WOOLWORTHS', 'TOPS SUNRISE', 'PNP CRP',
            'MCD PINELANDS', 'SPUR', 'TASHAS', 'BK GRAND', 'FORESTERS ARM',
            'KRISPY KREME', 'OUMEUL BAKERY', 'KNEAD PANORAM', 'BROWNS CANAL',
            'THE GOAT SHED', 'ASARA WINES', 'WINE', 'LIQUOR',
        ],
    },
    'gym': {
        'name': 'Gym',
        'type': 'personal_expense',
        'patterns': ['VIRGIN ACT', 'O M GYM', 'OM GYM', 'OLDGM.*DEBIT TRANSFER', 'OLD MUTUAL.*GYM'],
    },
    'home_construction': {
        'name': 'Home Construction/Renovation',
        'type': 'personal_expense',
        'patterns': ['VALIDUS', 'AFRIPOOLS'],
    },
    'kids_school': {
        'name': 'Kids School',
        'type': 'personal_expense',
        'patterns': ['KARRI'],
    },
    'meals_personal': {
        'name': 'Meals (Personal)',
        'type': 'personal_expense',
        'patterns': [
            'RESTAURANT', 'STEERS', 'NANDOS', 'KFC', 'PIZZA', 'DEBONAIRS',
            'WIMPY', 'OCEAN BASKET', 'ROCOMAMAS', 'SUSHI', 'MUGG.*BEAN',
            'VIDA.*CAFFE', 'CAFE', 'DELI', 'BISTRO', 'EATERY',
            'SPUR', 'TASHAS', 'STIR CRAZY', 'PEREGRINE FARM',
            'STODELS', 'UTAHSPUR', 'CINCINNATI SPU', 'TABBS',
        ],
    },
    'personal_care': {
        'name': 'Personal Care',
        'type': 'personal_expense',
        'patterns': ['SALON', 'BARBER', 'HAIR', 'SPA', 'BEAUTY', 'NAIL', 'MASSAGE', 'SKINCARE', 'CUTZF'],
    },
    'personal_other': {
        'name': 'Personal/Family Payments',
        'type': 'personal_expense',
        'patterns': [
            'JACKIE TOBIAS', 'CO TOBIAS', 'CESAIRE TOBIAS',
            'INVESTEC BANK LTD JOLION',
            'KM FACTORY',
        ],
    },
    'recreation': {
        'name': 'Recreation Equipment',
        'type': 'personal_expense',
        'patterns': ['WONDERLAND', 'PITKINCYCLES', 'PITKIN CYCLES', 'SPORTSMANS WAREHOUSE'],
    },
    'savings_investments': {
        'name': 'Savings/Investments',
        'type': 'personal_expense',
        'patterns': ['EASY EQUITIES', 'EASYEQUITIES', 'FNB SAVINGS', 'SAVINGS POCKET', 'UNIT TRUST'],
    },
    'shopping': {
        'name': 'Shopping',
        'type': 'personal_expense',
        'patterns': [
            'TAKEALOT', 'TAKEALO',
            'AE HOWARD CEN', 'HOWARD CENTRE', 'ADVANCE CANAL',
            'CONSTANTIA UI', 'BUILDERS SUNNI',
            'PETWORLD', 'ABSOLUTE PETS', 'FREEDOM ADVEN', 'BARGAIN BOO',
            'CLICKS', 'SPECSAVERS', 'BWH CITY', 'THE CRAZY S',
            'OUTDOORWARE', 'PINELANDS VIL', 'BUILD IT', 'KOODOO',
            'PNP EXP', 'CAPE TOWN FIRE',
        ],
    },
    'vehicle': {
        'name': 'Vehicle/Transport',
        'type': 'personal_expense',
        'patterns': ['CARTRACK', 'ENGEN', 'C\\*BP PINELAND', 'ACSA', 'UBER', 'SBSAVAFNO.*DEBICHECK'],
    },
    'vehicle_other': {
        'name': 'Vehicle (Other)',
        'type': 'personal_expense',
        'patterns': [
            'CAR SERVICE', 'CAR WASH', 'TYRES', 'AUTO PARTS', 'BATTERY CENTRE',
            'MIDAS', 'TIGER WHEEL', 'SUPA QUICK', 'EXHAUST', 'WINDSCREEN',
            'LICENSE RENEWAL', 'VEHICLE LICENSE', 'E-TOLL', 'SANRAL', 'N1 CITY MOTOR',
            'AUTOZONE', 'GOLDWAGEN', 'PANEL BEATER',
            'COCT TRAF', 'TRAFFIC',
        ],
    },

    # EXCLUDED (not expenses, ignore these)
    'tax_refund': {
        'name': 'Tax Refund (Excluded)',
        'type': 'excluded',
        'patterns': ['SARS.*MAGTAPE', 'SARS.*CREDIT', 'SARS.*REFUND'],
    },
    'tax_payment': {
        'name': 'Tax Payment (Excluded)',
        'type': 'excluded',
        'patterns': ['SARS.*PAYMENT', 'SARS.*PROV', 'SARS.*IRP', 'PROV TAX', 'SARS.*PENALTY'],
    },
    'bond_payment': {
        'name': 'Bond Payment (Excluded)',
        'type': 'excluded',
        'patterns': ['DEBIT ORDER - DO', 'STD BANK BOND', 'SBSA HOMEL', 'DEBIT ORDER REVERSAL'],
    },
    'inter_account_transfer': {
        'name': 'Inter-Account Transfer',
        'type': 'excluded',
        'patterns': ['IB TRANSFER', 'AUTOBANK TRANSFER', 'FUND TRANSFERS'],
    },
    'transfers': {
        'name': 'Transfers (Excluded)',
        'type': 'excluded',
        'patterns': ['DEBI CHECK PAYMENT'],
    },
}


def _is_fee_not_income(description_upper):
    """Check if this is a teletransmission fee (not income)"""
    return 'FEE' in description_upper and 'TELETRANSMISSION' in description_upper


def _match_pattern(pattern, description_upper, is_regex=True):
    """Match a pattern against description"""
    if is_regex:
        try:
            return bool(re.search(pattern, description_upper))
        except re.error:
            return False
    return pattern in description_upper


def categorize_transaction(description, amount=None, db_rules=None):
    """
    Categorize a transaction based on description and optional database rules.

    Database rules take priority over hardcoded patterns.

    Args:
        description: Transaction description
        amount: Transaction amount (optional, for future use)
        db_rules: List of ExpenseRule objects from database (optional)

    Returns:
        (category_name, confidence_score) tuple
    """
    description_upper = description.upper()

    # Check database rules first (higher priority)
    if db_rules:
        sorted_rules = sorted(db_rules, key=lambda r: r.priority, reverse=True)

        for rule in sorted_rules:
            if not rule.is_active:
                continue

            pattern = rule.pattern.upper()

            if _match_pattern(pattern, description_upper, rule.is_regex):
                # Skip income match if it's actually a fee
                if rule.category.category_type == 'income' and _is_fee_not_income(description_upper):
                    continue
                return (rule.category.name, 1.0)

    # Check hardcoded income patterns
    for pattern in CATEGORIES['income']['patterns']:
        if pattern in description_upper:
            if _is_fee_not_income(description_upper):
                return (CATEGORIES['banking_fees']['name'], 1.0)
            return (CATEGORIES['income']['name'], 1.0)

    # Check excluded patterns first (to catch things like SARS refunds before SARS payments)
    for cat_key, cat_info in CATEGORIES.items():
        if cat_info['type'] != 'excluded':
            continue

        for pattern in cat_info['patterns']:
            if _match_pattern(pattern, description_upper):
                return (cat_info['name'], 1.0)

    # Check all other hardcoded categories (business and personal expenses)
    for cat_key, cat_info in CATEGORIES.items():
        if cat_info['type'] in ('income', 'excluded'):
            continue  # Already handled above

        for pattern in cat_info['patterns']:
            if _match_pattern(pattern, description_upper):
                return (cat_info['name'], 1.0)

    # No match found
    return (None, 0.0)


# Legacy alias for backward compatibility
def categorize_transaction_with_rules(description, amount, db_rules=None):
    """
    Legacy wrapper - use categorize_transaction instead.
    """
    return categorize_transaction(description, amount, db_rules)


def is_inter_account_transfer(description):
    """Check if transaction is an inter-account transfer (should be excluded from income)"""
    transfer_patterns = [
        'IB TRANSFER TO',
        'IB TRANSFER FROM',
        'FUND TRANSFERS',
        'AUTOBANK TRANSFER',
    ]
    description_upper = description.upper()
    return any(p in description_upper for p in transfer_patterns)


def is_personal_from_business_mixed(description):
    """
    Check if this is a mixed business/personal purchase that needs splitting.
    Currently only handles Takealot, but can be extended.
    """
    return 'TAKEALOT' in description.upper() or 'TAKEALO' in description.upper()


def init_categories_in_db(db, Category):
    """Initialize categories in the database, adding any missing ones"""
    existing_names = {c.name for c in Category.query.all()}

    added = 0
    for cat_info in CATEGORIES.values():
        if cat_info['name'] not in existing_names:
            pattern_desc = ', '.join(cat_info['patterns'][:3]) if cat_info['patterns'] else 'Manual only'
            category = Category(
                name=cat_info['name'],
                category_type=cat_info['type'],
                description=f"Auto-categorized: {pattern_desc}"
            )
            db.session.add(category)
            added += 1

    if added > 0:
        db.session.commit()


def get_category_by_name(db, Category, name):
    """Get category from database by name"""
    return Category.query.filter_by(name=name).first()
