# E-Commerce Business Intelligence Dashboard

A college project prototype using Flask, MySQL, Pandas, NumPy, and Matplotlib.

## 1. Prerequisites
- Python 3.10 or newer
- MySQL Server and MySQL Workbench (or another MySQL client)
- VS Code (recommended)

## 2. Create the database
1. Open MySQL Workbench and connect to your local server.
2. Open `schema.sql`.
3. Execute the full script.
4. The script creates the `ecommerce_bi` database and tables and inserts clearly labelled DEMONSTRATION DATA.
   Do not present these demo values as actual startup sales.

## 3. Set up Python
Open the project folder in VS Code. Open Terminal > New Terminal and run:

### Windows Command Prompt
```bat
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
copy .env.example .env
```

If you use PowerShell and activation is blocked, use Command Prompt in VS Code, or run the venv Python directly:
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and enter your MySQL username and password. Example:
```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_actual_mysql_password
DB_NAME=ecommerce_bi
```
Do not share `.env` or commit it to a public repository.

## 4. Start the dashboard
With the virtual environment activated:
```bash
python -m flask --app app run --debug
```
Open http://127.0.0.1:5000 in your browser. Keep the terminal open while using the site.

## 5. Replace demo data with actual sales
Only use actual records you are authorized to use. Back up the database first. Map your source records into:
- `products`: one row per product; `product_id`, `product_name`, `category`
- `orders`: one row per order; `order_id`, `order_date`, `order_status`, `region`
- `order_items`: one row per product line in an order; `item_id`, `order_id`, `product_id`, `quantity`, `unit_price`, `discount_amount`, `return_amount`

Important assumptions:
- `discount_amount` and `return_amount` are amounts in rupees per order line, not percentages.
- If your source has a discount percentage, convert it to a rupee amount before importing.
- Keep one unique `order_id` per order and one unique `item_id` per line.
- Do not import names, phone numbers, addresses, or other customer personal data; this dashboard doesn't need them.
- Cancelled/Canceled orders are excluded. Review your actual status values and adjust `fetch_data()` if they differ.
- Demo dates are January–October 2026; update the date filter for your data.

## 6. Testing checklist
- `/health` should show `{"status":"ok","database":"connected"}`.
- Dashboard should show four KPI cards and three charts.
- Choose a date range with data and click Apply filters.
- Choose a date range without data; zero KPIs and a no-data message should appear.
- Check that cancelled orders are not counted.
- Verify a sample line manually: gross line sales = quantity × unit price; net line sales = gross line sales − discount − return amount.
- If only one month is present, growth should show as unavailable.

## 7. Project scope and limitations
This is an analytics dashboard, not a shopping checkout/payment system. It provides aggregated business performance, not customer-level analysis. It has no authentication, so keep it local for the college demo; do not expose it publicly without adding security and production configuration.
