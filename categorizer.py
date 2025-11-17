"""
Transaction categorization engine
Based on provisional_tax_calc_system.md rules
"""

# Category definitions
CATEGORIES = {
    # INCOME
    'income': {
        'name': 'Income',
        'type': 'income',
        'patterns': ['PRECISE DIGITAL', 'PRECISE DIGITA'],
    },

    # BUSINESS EXPENSES
    'interest_mortgage': {
        'name': 'Interest (Mortgage)',
        'type': 'business_expense',
        'patterns': ['SYSTEM INTEREST DEBIT', 'INTEREST DEBIT'],
    },
    'retirement_10x': {
        'name': 'Retirement (10X)',
        'type': 'business_expense',
        'patterns': ['10XRA COL', '10X'],
    },
    'retirement_other': {
        'name': 'Other Retirement',
        'type': 'business_expense',
        'patterns': ['OLD MUTUAL', 'OLDGM', 'OM UNITTRU'],
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
    'education': {
        'name': 'Education (UCT)',
        'type': 'business_expense',
        'patterns': ['PAYU.*UC', 'UNIVERSITY OF', 'QUALIFYD', 'PAYFAST.*QUALI'],
    },
    'internet': {
        'name': 'Internet (Afrihost)',
        'type': 'business_expense',
        'patterns': ['AFRIHOST'],
    },
    'phone_data': {
        'name': 'Phone/Data',
        'type': 'business_expense',
        'patterns': ['MTN', 'MTN PREPAID', 'MTN SP'],
    },
    'technology_software': {
        'name': 'Technology/Software',
        'type': 'business_expense',
        'patterns': [
            'GOOGLE GSUITE', 'GSUITE', 'GOOGLE ONE',
            'MSFT', 'MICROSOFT',
            'CLAUDE.AI',
            'RENDER.COM',
            'GODADDY', 'DNH\\*GODADDY',
            'PAYFAST.*TOPC', 'TOP CODER',
        ],
    },
    'office_equipment': {
        'name': 'Office Equipment',
        'type': 'business_expense',
        'patterns': ['TAKEALO.*T', 'TAKEALOT', 'PNA PINELANDS', 'ROZPRINT'],
    },
    'maintenance': {
        'name': 'Maintenance',
        'type': 'business_expense',
        'patterns': [
            'POINT GARDEN',
            'LIQUID RAIN', 'JOYCE THINDWA',
            'TRIP ELECTRICAL',
            'VALIDUS', 'FIREWORX',
            'DRAIN UNBLOCK',
            'ABSOLUTE FENCING',
            'CITY OF CAPE TOWN BUILDING', 'CITY BUILDING',
            'WOODENSCAPES', 'LIVEWIRE SYSTEMS',
            'DONALD BEKKER',
        ],
    },
    'municipal': {
        'name': 'Municipal',
        'type': 'business_expense',
        'patterns': ['CITY OF CAPE TOWN', 'EASYPAY 081907422748'],
    },
    'insurance': {
        'name': 'Insurance',
        'type': 'business_expense',
        'patterns': ['DISCINSURE', 'DISCLIFE', 'INSURANCE PREMIUM'],
    },
    'professional_services': {
        'name': 'Professional Services',
        'type': 'business_expense',
        'patterns': [
            'SARS', 'PROV TAX', 'SBSA RCP',
            'PERSONAL TAX SERVIC',
            'SHEET SOLVED',
        ],
    },
    'coffee_meals': {
        'name': 'Coffee/Meals (Business)',
        'type': 'business_expense',
        'patterns': [
            'BOOTLEGGER', 'SHIFT ESPRESS', 'SHIFT ESPR',
            'FORESTERS ARM',
            'BOSSA',
            'YOCO.*PINEH', 'YOCO.*CUTZF', 'YOCO.*FAIRV', 'YOCO.*MAITG', 'YOCO.*PURPO',
            'YOCO.*KRIST', 'YOCO.*PINEL',
        ],
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
        ],
    },
    'printing': {
        'name': 'Printing',
        'type': 'business_expense',
        'patterns': ['ROZPRINT'],
    },

    # PERSONAL EXPENSES (Non-deductible)
    'vehicle': {
        'name': 'Vehicle/Transport',
        'type': 'personal_expense',
        'patterns': ['CARTRACK', 'ENGEN', 'C\\*BP PINELAND', 'ACSA', 'UBER', 'KARRI MAIN'],
    },
    'groceries': {
        'name': 'Groceries/Personal Shopping',
        'type': 'personal_expense',
        'patterns': [
            'CHECKERS', 'WOOLWORTHS', 'TOPS SUNRISE',
            'MCD PINELANDS', 'SPUR', 'TASHAS', 'BK GRAND', 'FORESTERS ARM',
            'KRISPY KREME', 'OUMEUL BAKERY', 'KNEAD PANORAM', 'BROWNS CANAL',
            'THE GOAT SHED', 'AE HOWARD CEN', 'HOWARD CENTRE', 'ADVANCE CANAL',
            'CONSTANTIA UI', 'PNP CRP', 'BUILDERS SUNNI', 'PITKIN CYCLES',
            'PETWORLD', 'ABSOLUTE PETS', 'FREEDOM ADVEN', 'BARGAIN BOO',
            'CLICKS', 'SPECSAVERS', 'BWH CITY', 'THE CRAZY S',
        ],
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
    'entertainment': {
        'name': 'Entertainment',
        'type': 'personal_expense',
        'patterns': [
            'NETFLIX',
            'GOOGLE YOUTUBE', 'YOUTUBE',
            'APPLE.COM', 'ITUNE',
            'SABC TV',
            'PLAYSTATION', 'PLAYSTATIONNETWORK',
        ],
    },
    'gym': {
        'name': 'Gym',
        'type': 'personal_expense',
        'patterns': ['VIRGIN ACT', 'O M GYM', 'OM GYM'],
    },
    'alcohol': {
        'name': 'Alcohol',
        'type': 'personal_expense',
        'patterns': ['ASARA WINES', 'WINE'],
    },
    'recreation': {
        'name': 'Recreation Equipment',
        'type': 'personal_expense',
        'patterns': ['WONDERLAND', 'PITKIN CYCLES', 'SPORTSMANS WAREHOUSE'],
    },

    # EXCLUDED (not expenses, ignore these)
    'bond_payment': {
        'name': 'Bond Payment (Excluded)',
        'type': 'excluded',
        'patterns': ['DEBIT ORDER - DO', 'STD BANK BOND', 'SBSA HOMEL', 'DEBIT ORDER REVERSAL'],
    },
    'transfers': {
        'name': 'Transfers (Excluded)',
        'type': 'excluded',
        'patterns': ['AUTOBANK TRANSFER', 'DEBI CHECK PAYMENT'],
    },
}


def categorize_transaction(description, amount):
    """
    Categorize a transaction based on description
    Returns (category_key, confidence_score)
    """
    description_upper = description.upper()

    # Special case: Income (PRECISE DIGITAL)
    if 'PRECISE DIGITAL' in description_upper or 'PRECISE DIGITA' in description_upper:
        # If it's a teletransmission FEE, it's a business expense
        if 'FEE' in description_upper and 'TELETRANSMISSION' in description_upper:
            return ('banking_fees', 1.0)
        # Otherwise it's income
        return ('income', 1.0)

    # Check each category
    import re
    matches = []

    for cat_key, cat_info in CATEGORIES.items():
        if cat_info['type'] == 'income':
            continue  # Already handled above

        for pattern in cat_info['patterns']:
            # Use regex matching
            if re.search(pattern, description_upper):
                matches.append((cat_key, 1.0))
                break

    if matches:
        # Return first match (you could implement priority logic here)
        return matches[0]

    # Default: uncategorized
    return (None, 0.0)


def is_inter_account_transfer(description):
    """Check if transaction is an inter-account transfer (should be excluded from income)"""
    transfer_patterns = [
        'IB TRANSFER TO',
        'IB TRANSFER FROM',
        'IB Transfer to',
        'FUND TRANSFERS',
        'AUTOBANK TRANSFER',
    ]

    description_upper = description.upper()
    for pattern in transfer_patterns:
        if pattern.upper() in description_upper:
            return True
    return False


def is_personal_from_business_mixed(description):
    """
    Check if this is a mixed business/personal purchase that needs splitting
    Currently only handles Takealot, but can be extended
    """
    if 'TAKEALO' in description.upper() or 'TAKEALOT' in description.upper():
        # Return True to flag for manual review
        # In the UI, user can split these
        return True
    return False


def init_categories_in_db(db, Category):
    """Initialize categories in the database"""
    existing = Category.query.count()
    if existing > 0:
        return  # Already initialized

    for cat_key, cat_info in CATEGORIES.items():
        category = Category(
            name=cat_info['name'],
            category_type=cat_info['type'],
            description=f"Auto-categorized: {', '.join(cat_info['patterns'][:3])}"
        )
        db.session.add(category)

    db.session.commit()


def get_category_by_name(db, Category, name):
    """Get category from database by name"""
    return Category.query.filter_by(name=name).first()
