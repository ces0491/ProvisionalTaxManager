# ProvisionalTaxManager

A web application for managing bi-annual provisional tax calculations for
self-employed individuals in South Africa. Automates bank statement parsing,
transaction categorization, and tax report generation.

## Features

- **PDF Statement Parsing**: Automatically extracts transactions from
  Standard Bank PDFs (cheques, credit card, mortgage)
- **Smart Categorization**: Auto-categorizes transactions based on 30+
  business rules
- **Duplicate Detection**: Identifies and merges duplicate transactions
  from overlapping statements
- **Manual Editing**: Edit, recategorize, or delete transactions as needed
- **Manual Transactions**: Add cash expenses or income not on statements
- **Transaction Splitting**: Split mixed purchases (like Takealot) into
  business and personal portions
- **Configurable Income Sources**: Add and manage income source patterns for
  automatic detection (PayPal, Stripe, clients, etc.)
- **Flexible Categorization**: Database-driven rules for all transaction
  categories with priority and regex support
- **Tax Calculator**: Calculate provisional tax liability using SARS 2025/2026
  tax tables with rebates and credits
- **Excel Export**: Generates comprehensive 11-table tax reports in native
  Excel format
- **Tax Periods**: Supports both provisional tax periods (Mar-Aug, Sep-Feb)
- **Extrapolation**: Automatically projects incomplete months for current period

## Setup

### Local Development

1. **Create virtual environment:**

   ```bash
   cd ProvisionalTaxManager
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # Mac/Linux
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**

   ```bash
   copy .env.example .env
   ```

   Edit `.env` and set:
   - `FLASK_SECRET_KEY`: Random secret key for sessions
   - `AUTH_PASSWORD`: Password for logging into the app
   - `DATABASE_URL`: Leave as sqlite for local development

4. **Initialize database:**

   ```bash
   flask init-db
   ```

5. **Run the app:**

   ```bash
   python app.py
   ```

   Visit: <http://localhost:5000>

### Deployment to Render

1. **Push code to GitHub:**

   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin YOUR_GITHUB_REPO_URL
   git push -u origin main
   ```

2. **Create Render services:**

   - Go to <https://render.com>
   - Click "New +" → "Blueprint"
   - Connect your GitHub repo
   - Render will automatically detect `render.yaml`
   - Set the `AUTH_PASSWORD` environment variable in the dashboard

3. **Database will be created automatically** from `render.yaml` configuration

## Usage

### 1. Upload Statements

- Download PDF statements from Standard Bank for all 3 accounts:
  - Cheques/Signature Account (account ending 576 1)
  - Credit Card (account ending 7880)
  - Mortgage (account ending 325 8)

- Go to **Upload Statements**
- Select all 3 PDFs (you can upload multiple at once)
- Click **Upload and Process**

### 2. Review Transactions

- Go to **Transactions** to see all parsed transactions
- Use filters to narrow down by:
  - Category
  - Date range
  - Account type

### 3. Handle Duplicates

- Go to **Duplicates** to see potential duplicate transactions
- Review each pair
- Mark one as duplicate (it will be excluded from calculations)

### 4. Edit/Recategorize

- Click the edit icon (pencil) next to any transaction
- Change:
  - Description
  - Amount
  - Category
  - Add notes
- Click **Save Changes**

### 5. Manual Transactions & Splitting

**Add Manual Transactions:**

- Click **Add Manual Transaction** on the Transactions page
- Use for:
  - Cash expenses not on bank statements
  - Additional income from other sources
  - Manual adjustments or corrections
- Enter date, description, amount, category, and notes
- Transaction will be marked with a hand icon

**Split Transactions:**

- Click the scissors icon next to any transaction (e.g., Takealot orders)
- Split between business and personal portions
- Enter amounts for each portion (must total the original amount)
- Select categories for each portion
- Original transaction is marked as deleted, replaced by two new entries
- Split items are marked with a scissors icon

### 6. Configure Income Sources & Rules

- Go to **Settings** from the navigation
- View all current categorization rules
- **Add Income Sources:**
  - Click "Add New Pattern" on the right
  - Select "Income" category
  - Enter pattern (e.g., "PAYPAL", "STRIPE", "CLIENT NAME")
  - Optionally enable regex for advanced patterns
  - Set priority (higher = checked first)
  - Click "Add Pattern"
- **Manage Rules:**
  - Toggle active/inactive status
  - Delete rules you no longer need
  - Higher priority rules are checked first
- **Common income sources to add:**
  - Payment platforms: PayPal, Stripe, Square
  - Freelance platforms: Upwork, Fiverr, Freelancer
  - Client names from invoices
  - Bank deposit descriptions

### 7. Tax Calculator

- Go to **Tax Calculator** from the navigation
- Select date range (e.g., Mar 1 - Aug 31 for first provisional)
- Enter your age (for rebate calculation)
- Enter medical aid members (for tax credits)
- Enter previous tax payments if applicable
- Click **Calculate Tax** to see:
  - Period income and expenses
  - Annual estimate (extrapolated)
  - Estimated annual tax liability
  - **Provisional payment amount due**
  - Expense breakdown by category

### 8. Export Tax Report

- Go to **Dashboard**
- Under "Export Report", choose:
  - **First Provisional** (Mar-Aug for August submission)
  - **Second Provisional** (Sep-Feb for February submission)
- Download the Excel file
- Send to your tax practitioner

## Excel Export Format

The generated Excel file contains 11 tables as per requirements:

1. **Table 1**: Monthly Income Summary
2. **Tables 2-7**: Individual month expense details (one per month)
3. **Table 8**: Monthly Business Expense Summary (cross-month)
4. **Table 9**: Monthly Personal Expense Summary (excluded)
5. **Table 10**: Monthly Net Profit Summary
6. **Table 11**: Annual Summary for Tax Calculation

Format: `PnLMarAugforAug2025.xlsx` or `PnLSepFebforFeb2026.xlsx`

## Business Rules

### Income

- **PRECISE DIGITAL** (NZ payments) - Gross amounts
- Teletransmission fees are expenses, not income deductions
- Inter-account transfers excluded

### Business Expenses (Deductible)

- Technology/Software: Google Workspace, Claude.AI, Render, GoDaddy, etc.
- Internet: Afrihost (100%)
- Phone/Data: MTN, data bundles
- Medical: Discovery Medical Aid, consultations, Specsavers, Clicks
- Retirement: 10X, Old Mutual
- Education: UCT, Qualifyd
- Property: **Full** mortgage interest + insurance (not 8.2%)
- Municipal: City of Cape Town
- Maintenance: Garden, irrigation, electrical, building, fencing
- Professional: SARS payments, tax practitioner
- Coffee/Meals: Bootleggers, Shift, Foresters, Bossa, Yoco locations
- Banking fees: All fees and charges

### Personal Expenses (Non-Deductible)

- Entertainment: Netflix, YouTube, Apple, PlayStation, SABC
- Gym: Virgin Active, OM Gym
- Alcohol: Wine purchases
- Recreation: Sports equipment

### Special Handling

- **Takealot orders**: Flag for manual splitting of business/personal items
- **Mortgage statement**: Extract full interest + insurance with month-end dates
- **Municipal**: Use actual payment date (not service period)

## File Structure

```text
sa-tax-app/
├── app.py                 # Main Flask application
├── models.py              # Database models
├── config.py              # Configuration
├── pdf_parser.py          # PDF parsing logic
├── categorizer.py         # Transaction categorization rules
├── excel_export.py        # Excel report generation
├── requirements.txt       # Python dependencies
├── Procfile              # Render deployment
├── render.yaml           # Render configuration
├── templates/            # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── upload.html
│   ├── transactions.html
│   ├── edit_transaction.html
│   └── duplicates.html
└── uploads/              # Uploaded PDF files (not in git)
```

## Security

- Password-protected with configurable password
- Session-based authentication
- File upload size limited to 16MB
- Only PDF files accepted
- Soft deletion of transactions (recoverable)

## Testing

The application includes a comprehensive test suite with 79 tests covering:

- Tax calculations and SARS tax tables
- Transaction categorization and rules
- PDF parsing and duplicate detection
- Flask routes and API endpoints
- Database models and relationships

### Run Tests

```bash
pytest
```

For detailed test documentation, see [tests/README.md](tests/README.md)

### Current Test Status

**All tests passing: 79/79 (100%)**

- Tax Calculator: 12/12 passing (100%)
- Categorizer: 20/20 passing (100%)
- PDF Parser: 7/7 passing (100%)
- Routes: 26/26 passing (100%)
- Models: 18/18 passing (100%)

## Support

For issues or questions, refer to the requirements document:
`provisional_tax_calc_system.md`

## License

Private use only - Sheet Solved
