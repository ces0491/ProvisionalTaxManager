"""
Test script to parse PDFs and check categorization
"""
from pdf_parser import BankStatementParser
from categorizer import categorize_transaction, is_inter_account_transfer

# Test with the 3 historical statements
statements = [
    r'C:\Users\cesai_b8mratk\OneDrive\Documents\Admin\Tax\2025\bank_statements\std_bank_statement_cheque.pdf',
    r'C:\Users\cesai_b8mratk\OneDrive\Documents\Admin\Tax\2025\bank_statements\std_bank_statement_cc.pdf',
    r'C:\Users\cesai_b8mratk\OneDrive\Documents\Admin\Tax\2025\bank_statements\std_bank_statement_mortgage.pdf',
]

print("=" * 80)
print("TESTING PDF PARSER")
print("=" * 80)

for statement_path in statements:
    filename = statement_path.split('\\')[-1]
    print(f"\n\nParsing: {filename}")
    print("-" * 80)

    try:
        parser = BankStatementParser(statement_path)
        result = parser.parse()

        print(f"Account Type: {result['account_type']}")
        print(f"Account Number: {result['account_number']}")
        print(f"Period: {result['start_date']} to {result['end_date']}")
        print(f"Transactions Found: {len(result['transactions'])}")

        # Show first 10 transactions
        print("\nFirst 10 Transactions:")
        for i, trans in enumerate(result['transactions'][:10], 1):
            cat_key, confidence = categorize_transaction(trans['description'], trans['amount'])

            # Check if inter-account transfer
            is_transfer = is_inter_account_transfer(trans['description'])

            print(f"\n  {i}. {trans['date']}")
            print(f"     Description: {trans['description'][:60]}")
            print(f"     Amount: R {trans['amount']}")
            if cat_key:
                from categorizer import CATEGORIES
                cat_name = CATEGORIES.get(cat_key, {}).get('name', 'Unknown')
                cat_type = CATEGORIES.get(cat_key, {}).get('type', 'Unknown')
                print(f"     Category: {cat_name} ({cat_type})")
            else:
                print("     Category: UNCATEGORIZED")

            if is_transfer:
                print("     [!] INTER-ACCOUNT TRANSFER - Excluded from income")

        # Summary by category type
        print("\n\nCategory Summary:")
        income_count = 0
        business_exp_count = 0
        personal_exp_count = 0
        uncategorized_count = 0

        for trans in result['transactions']:
            cat_key, confidence = categorize_transaction(trans['description'], trans['amount'])
            if cat_key:
                from categorizer import CATEGORIES
                cat_type = CATEGORIES.get(cat_key, {}).get('type', '')
                if cat_type == 'income':
                    income_count += 1
                elif cat_type == 'business_expense':
                    business_exp_count += 1
                elif cat_type == 'personal_expense':
                    personal_exp_count += 1
            else:
                uncategorized_count += 1

        print(f"  Income: {income_count}")
        print(f"  Business Expenses: {business_exp_count}")
        print(f"  Personal Expenses: {personal_exp_count}")
        print(f"  Uncategorized: {uncategorized_count}")

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

print("\n\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
