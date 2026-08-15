"""
Transaction categorization engine
Based on provisional_tax_calc_system.md rules

Each CATEGORIES entry carries:
    name        display name, and the key every other module joins on
    type        income | business_expense | personal_expense | excluded
    patterns    regular expressions matched against the upper-cased description
    priority    optional int, default 0. Higher is tested first. Dict order is
                only a tie-breaker, so entries stay alphabetical and a category
                that must beat a more general one says so explicitly.
    apportion   optional bool. True marks a home-office category, which
                tax_calculator reads to build HOME_OFFICE_CATEGORIES.

Patterns are compiled once at import (see _COMPILED); a malformed one raises
here rather than silently never matching.
"""
import re
from typing import Any, Dict

# Category definitions
CATEGORIES: Dict[str, Dict[str, Any]] = {
    # INCOME
    'income': {
        'name': 'Income',
        'type': 'income',
        'patterns': ['PRECISE DIGITAL', 'PRECISE DIGITA'],
    },

    # BUSINESS EXPENSES - Alphabetical order. Precedence between categories is
    # set by 'priority', never by position, so this order is free to change.
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
            'ELECTRONIC PMT/TRNSF FEE',
            r'INTER[\s-]*ACC TRANSFER FEE',
            'INTERNATIONAL TXN FEE',
            # Covers both '#EMAIL PMT CONFIRM FEE' and '#SMS PMT CONFIRM FEE'.
            'PMT CONFIRM FEE',
            # The charge on a prepaid airtime top-up, in both renderings the
            # statements use. Anchored on the word FEE so neither pattern can
            # reach the top-up itself, which is Phone/Data and reads
            # 'PRE-PAID PAYMENT TO'.
            r'FEE\s*-\s*PRE-PAID TOP UP',
            r'\bPREPAID FEE\b',
            'CASH FINANCE CHARGE',
            'EXCESS INTEREST',
            'CREDIT CARD INTEREST',
            'INTEREST CHARGE',
            'FINANCE CHARGE',
            'LATE PAYMENT FEE',
            'OVERLIMIT FEE',
            # 'CREDIT INTEREST' is deliberately absent: it is interest earned on
            # a credit balance, so matching it here would book income as a
            # deduction. It is left uncategorized for manual triage.
        ],
    },
    'home_loan_costs': {
        # Home-loan account running costs are a cost of the property, so they
        # are home-office apportioned alongside mortgage interest rather than
        # deducted in full as a bank charge. The priority puts them ahead of
        # 'banking_fees', whose generic 'ADMINISTRATION FEE' pattern would
        # otherwise claim the home-loan admin fee at full value.
        'name': 'Home Loan Costs',
        'type': 'business_expense',
        'priority': 100,
        'apportion': True,
        'patterns': [
            # The trailing \b keeps 'ADMINISTRATION FEE HLOAN' out.
            r'ADMINISTRATION FEE\s*-?\s*HL\b',
            r'\bHL\s+ADMINISTRATION FEE',
            'ADMINISTRATION FEE HOME LOAN',
            'HOME LOAN ADMIN',
        ],
    },
    'insurance_life': {
        # Life / credit-life cover is not deductible and is kept out of the
        # home-office apportionment entirely. The priority puts it ahead of the
        # generic 'insurance' rule below, since DISCLIFE descriptions also
        # contain "INSURANCE PREMIUM".
        'name': 'Insurance (Life/Personal)',
        'type': 'personal_expense',
        'priority': 100,
        'patterns': ['DISCLIFE'],
    },
    'insurance': {
        # Deductible building / household-contents cover, home-office apportioned.
        # DISCINSURE (Discovery) is only partly deductible (contents portion) -
        # the deductible amount is applied in tax_calculator. INSURANCE PREMIUM
        # is the bond building/homeowner's cover (fully deductible).
        'name': 'Insurance',
        'type': 'business_expense',
        'apportion': True,
        'patterns': ['DISCINSURE', 'INSURANCE PREMIUM'],
    },
    'interest_mortgage': {
        'name': 'Interest (Mortgage)',
        'type': 'business_expense',
        'apportion': True,
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
        # Home/garden maintenance is not claimed (per practitioner treatment) -
        # kept as a non-deductible personal expense.
        'name': 'Maintenance',
        'type': 'personal_expense',
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
        # Medical scheme contributions are NOT a business deduction - they
        # generate the Medical Scheme Fees Tax Credit (applied per member in the
        # tax calculation), so they must not reduce business income.
        'name': 'Medical Aid',
        'type': 'personal_expense',
        'patterns': ['DISC PREM', 'MEDICAL AID CONTRIBUTION', 'DISCOVERY'],
    },
    'medical_fees': {
        # Out-of-pocket medical costs are not a business deduction; they feed the
        # additional medical expenses tax credit.
        'name': 'Medical Fees',
        'type': 'personal_expense',
        'patterns': ['DR MALCOL', 'SPECSAVERS', 'CLICKS PINELA'],
    },
    'municipal': {
        'name': 'Municipal',
        'type': 'business_expense',
        'apportion': True,
        'patterns': ['CITY OF CAPE TOWN', 'EASYPAY'],
    },
    'office_equipment': {
        'name': 'Office Equipment',
        'type': 'business_expense',
        'patterns': ['PNA PINELANDS'],
    },
    'retirement_other': {
        # Deliberately manual-only. 10X is the sole retirement product, so
        # nothing auto-classifies here; the category is kept as a target for a
        # future fund, assigned by hand or by a database rule.
        'name': 'Other Retirement',
        'type': 'business_expense',
        'patterns': [],  # Populated via manual categorization or rules
    },
    'phone_data': {
        'name': 'Phone/Data',
        'type': 'business_expense',
        'patterns': [r'\bMTN\b'],
    },
    'printing': {
        'name': 'Printing',
        'type': 'business_expense',
        'patterns': ['ROZPRINT'],
    },
    'professional_services': {
        # The priority puts this ahead of 'startup_costs', so a GovChain
        # annual-return descriptor carrying the word CIPC is billed as a
        # recurring professional fee rather than one-off start-up expenditure.
        'name': 'Professional Services',
        'type': 'business_expense',
        'priority': 100,
        'patterns': [
            'PERSONAL TAX SERVIC',
            'SHEET SOLVED',
            'GOVCHAIN',          # CIPC annual returns / company filings
        ],
    },
    'retirement_10x': {
        # Closed at both ends: an unanchored '10X' matches inside merchant
        # references such as 'CARD PURCHASE 10X4832', which would fabricate a
        # retirement deduction.
        'name': 'Retirement (10X)',
        'type': 'business_expense',
        'patterns': [r'\b10XRA\b', r'\b10X\b'],
    },
    'technology_software': {
        # Card descriptors separate the vendor from the product with either a
        # space or an asterisk ('GOOGLE WORKSPACE_SHEET' vs 'GOOGLE*WORKSPACE
        # SHEET'), so the Google pattern allows both. A bare 'GOOGLE' must not
        # be used - it would swallow GOOGLE YOUTUBE, which is personal.
        'name': 'Technology/Software',
        'type': 'business_expense',
        'patterns': [
            r'GOOGLE[\s*]*(GSUITE|ONE|WORKSPACE|COLAB|CLOUD)', 'GSUITE',
            'MSFT', 'MICROSOFT',
            # Covers the API billing and the newer subscription descriptor
            # 'ANTHROPIC* CLAUDE SUB'; 'CLAUDE.AI' the older one. Anchored so
            # it cannot match inside PHILANTHROPIC.
            r'\bANTHROPIC', r'CLAUDE\.AI',
            r'RENDER\.COM',
            'GODADDY',
            'PAYFAST.*TOPC', 'TOP CODER',
            'ADOBE',
        ],
    },
    'travel_accommodation': {
        'name': 'Travel/Accommodation',
        'type': 'business_expense',
        # 'LODGE' excludes LODGEMENT, a routine banking term.
        'patterns': ['AIRBNB', 'BOOKING.COM', 'HOTELS', 'GUEST HOUSE', r'\bLODGE(?!MENT)'],
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
            'FOSCHINI', 'MARKHAM', r'\bZARA\b', 'H&M', 'COTTON ON', 'CAPE UNION',
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
            'CHECKERS', 'WOOLWORTHS', r'\bSPAR\b', 'TOPS SUNRISE', 'PNP CRP',
            'MCD PINELANDS', 'SPUR', 'TASHAS', 'BK GRAND', 'FORESTERS ARM',
            'KRISPY KREME', 'OUMEUL BAKERY', 'KNEAD PANORAM', 'BROWNS CANAL',
            # 'WINE' is closed at both ends so it cannot match WINELANDS.
            'THE GOAT SHED', 'ASARA WINES', r'\bWINES?\b', 'LIQUOR',
        ],
    },
    'gym': {
        # 'OLDGM' is the Old Mutual gym debit order, e.g.
        # 'OLD MUTUALOLDGM24484 DEBIT TRANSFER'. It is matched either as its own
        # token or immediately after 'OLD MUTUAL' (the descriptor runs the two
        # together), which keeps it out of unrelated words like MARIGOLDGM. The
        # 'DEBIT TRANSFER' suffix is not required, so a truncated descriptor
        # still matches.
        'name': 'Gym',
        'type': 'personal_expense',
        'patterns': [
            'VIRGIN ACT', 'O M GYM', 'OM GYM',
            r'OLD MUTUAL.*OLDGM', r'\bOLDGM', 'OLD MUTUAL.*GYM',
        ],
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
            # CAFE and DELI are closed at both ends: unanchored they match
            # CAFETERIA and DELIVERY.
            'VIDA.*CAFFE', r'\bCAFE\b', r'\bDELI\b', 'BISTRO', 'EATERY',
            'SPUR', 'TASHAS', 'STIR CRAZY', 'PEREGRINE FARM',
            'STODELS', 'UTAHSPUR', 'CINCINNATI SPU', 'TABBS',
        ],
    },
    'personal_care': {
        # Short tokens here are word-anchored: unanchored, 'SPA' matches
        # WORKSPACE, 'HAIR' matches CHAIR and MOHAIR, and 'NAIL' matches SNAIL.
        # 'SPA' additionally excludes SPAR (the grocer) while still reaching the
        # plural and numbered forms the statements carry, e.g. 'HEALTH SPAS'.
        'name': 'Personal Care',
        'type': 'personal_expense',
        'patterns': [
            'SALON', 'BARBER', r'\bHAIR', r'\bSPA(?!R)', 'BEAUTY', r'\bNAIL',
            'MASSAGE', 'SKINCARE', 'CUTZF',
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
    'recreation': {
        'name': 'Recreation Equipment',
        'type': 'personal_expense',
        'patterns': ['WONDERLAND', 'PITKINCYCLES', 'PITKIN CYCLES', 'SPORTSMANS WAREHOUSE'],
    },
    'savings_investments': {
        # The Old Mutual investment debit orders are savings contributions, so
        # they are non-deductible. 'OM UNITTRU' and 'OLD MUTUAL INVEST' are
        # listed explicitly because only some descriptors carry the 'UNIT TRUST'
        # wording.
        'name': 'Savings/Investments',
        'type': 'personal_expense',
        'patterns': [
            'EASY EQUITIES', 'EASYEQUITIES', 'FNB SAVINGS', 'SAVINGS POCKET',
            'UNIT TRUST', 'OM UNITTRU', 'OLD MUTUAL INVEST',
        ],
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
        'patterns': [
            'CARTRACK', 'ENGEN', r'C\*BP PINELAND', r'\bACSA\b', r'\bUBER\b',
            'SBSAVAFNO.*DEBICHECK',
        ],
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


def _compile_categories():
    """Compile every CATEGORIES pattern once, failing loudly on a bad one.

    A pattern that does not compile would otherwise never match, silently
    dropping its transactions into the uncategorized (non-deductible) bucket.
    """
    compiled = {}
    for cat_key, cat_info in CATEGORIES.items():
        cat_patterns = []
        for pattern in cat_info['patterns']:
            try:
                cat_patterns.append(re.compile(pattern))
            except re.error as exc:
                raise ValueError(
                    f"Invalid pattern {pattern!r} in CATEGORIES['{cat_key}']: {exc}"
                ) from exc
        compiled[cat_key] = cat_patterns
    return compiled


_COMPILED = _compile_categories()


def _match_order(types):
    """Category keys of the given types, highest priority first.

    sorted() is stable, so entries sharing a priority keep their dict order.
    """
    keys = [k for k, v in CATEGORIES.items() if v['type'] in types]
    return sorted(keys, key=lambda k: -CATEGORIES[k].get('priority', 0))


_EXCLUDED_ORDER = _match_order({'excluded'})
_EXPENSE_ORDER = _match_order({'business_expense', 'personal_expense'})

# Home-office categories, declared on the entry itself so tax_calculator and the
# export read one list rather than a second hand-maintained copy of these names.
APPORTIONED_CATEGORIES = [c['name'] for c in CATEGORIES.values() if c.get('apportion')]


def _is_fee_not_income(description_upper):
    """Check if this is a teletransmission fee (not income)"""
    return 'FEE' in description_upper and 'TELETRANSMISSION' in description_upper


def _match_pattern(pattern, description_upper, is_regex=True):
    """Match a user-supplied pattern against an upper-cased description.

    Only used for database rules; CATEGORIES patterns go through _COMPILED.
    A literal is upper-cased to match, but a regex is not - upper-casing a
    regex inverts its escapes (\\b -> \\B, \\s -> \\S), so it is matched
    case-insensitively as written instead.
    """
    if is_regex:
        try:
            return bool(re.search(pattern, description_upper, re.IGNORECASE))
        except re.error:
            return False
    return pattern.upper() in description_upper


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

            if _match_pattern(rule.pattern, description_upper, rule.is_regex):
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

    # Excluded categories are tested ahead of expenses, so a bond repayment or
    # an inter-account transfer is dropped rather than deducted.
    for cat_key in _EXCLUDED_ORDER:
        for pattern in _COMPILED[cat_key]:
            if pattern.search(description_upper):
                return (CATEGORIES[cat_key]['name'], 1.0)

    # Business and personal expenses, highest priority first
    for cat_key in _EXPENSE_ORDER:
        for pattern in _COMPILED[cat_key]:
            if pattern.search(description_upper):
                return (CATEGORIES[cat_key]['name'], 1.0)

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
