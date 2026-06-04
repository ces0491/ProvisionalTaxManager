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
  from overlapping statements with persistent dismissal tracking
- **Receipt Management**: Upload and view receipt scans/PDFs linked to transactions
- **Manual Editing**: Edit, recategorize, or delete transactions as needed
- **Manual Transactions**: Add cash expenses or income not on statements
- **Transaction Splitting**: Split mixed purchases (like Takealot) into
  business and personal portions
- **Configurable Income Sources**: Add and manage income source patterns for
  automatic detection (PayPal, Stripe, clients, etc.)
- **Flexible Categorization**: Database-driven rules for all transaction
  categories with priority and regex support
- **Tax Calculator**: Calculate provisional tax liability using database-driven
  SARS tax tables (2025/2026 and 2026/2027) with rebates and credits. The first
  provisional period pays 50% of the annual estimate; the second pays the balance
- **Home Office Apportionment**: Apportions qualifying home expenses (bond
  interest, rates, building/contents insurance) by office-to-home floor area;
  insurance is reduced to its deductible building/contents portion, with motor
  and life cover excluded
- **Excel Export**: Generates a tax-practitioner workbook — a one-page
  Provisional Summary (income, deductible expenses, home-office box, medical
  credit) plus a detailed business-expense breakdown; personal expenses are
  excluded
- **Tax Periods**: Supports both provisional tax periods (Mar-Aug, Sep-Feb),
  selectable per tax year
- **Extrapolation**: Automatically projects incomplete months for current period
- **Security**: CSRF protection on all forms and APIs, rate-limited login, and
  hardened session cookies

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
   - `SESSION_COOKIE_SECURE` (optional): set to `true` in production (HTTPS);
     leave unset for local HTTP development
   - `FLASK_DEBUG` (optional): set to `true` to enable the debugger locally

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
  - Category (including "Uncategorized")
  - Tax year (anchors the quick-range presets)
  - Quick ranges: this/last month, last 3/6 months, provisional periods, full tax year
  - A specific month, or a custom start/end date range
- Use **Clear filters** to reset

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
- Choose the **Provisional Period** (1st: Mar-Aug, or 2nd: Sep-Feb) — this
  auto-fills the period dates, which you can still adjust
- Date of birth is used for automatic age-based rebate calculation (65+, 75+)
- Enter medical aid members (for tax credits)
- For the second period, enter previous tax payments (the first provisional
  payment plus any PAYE)
- Click **Calculate Tax** to see:
  - Period income and expenses
  - Annual estimate (extrapolated to 12 months)
  - Estimated annual tax liability
  - **Provisional payment due** — 50% of the annual estimate for the 1st period,
    or the remaining balance for the 2nd
  - Expense breakdown by category
- The rate-table panel shows the SARS rates for the tax year of the period's end date

### 8. Export Tax Report

- Go to **Dashboard**
- Under "Export Report", select the **tax year**, then choose:
  - **First Provisional** (Mar-Aug for August submission)
  - **Second Provisional** (Sep-Feb for February submission)
- Download the Excel file
- Send to your tax practitioner

## Excel Export Format

The workbook opens on a **Provisional Summary** sheet laid out for a tax
practitioner:

- Monthly income summary
- Deductible expense lines (full amounts)
- A home-office apportionment box (qualifying home expenses × office %), rolled
  into a single "Home Office" expense line
- Period net profit

A second **Tax Report** sheet contains the detailed breakdown — deductible
business expenses only (personal expenses are excluded; medical is reported as a
credit, not a deduction):

1. **Table 1**: Monthly Income Summary
2. **Tables 2-7**: Individual month business-expense details
3. **Table 8**: Monthly Business Expense Summary (cross-month)
4. **Table 9**: Monthly Net Profit Summary
5. **Table 10**: Annual Summary for Tax Calculation

Format: `PnLMarAugforAug2025.xlsx` or `PnLSepFebforFeb2026.xlsx`

## Testing

The application includes a comprehensive test suite with 81 tests covering:

- Tax calculations and SARS tax tables
- Transaction categorization and rules
- PDF parsing and duplicate detection
- Flask routes and API endpoints
- Database models and relationships

```bash
pytest
```

## Documentation

Additional documentation in the `docs/` folder:

- [Codebase Map](docs/codebase-map.md) - Project structure and navigation
- [Tax Tables Guide](docs/tax-tables.md) - Managing SARS tax tables
- [VAT Guide](docs/vat-guide.md) - VAT tracking and reporting
