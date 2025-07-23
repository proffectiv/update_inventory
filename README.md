# Inventory Update Automation

A simple, modular Python automation that synchronizes inventory data between Dropbox files and Holded ERP system. Email attachments are automatically downloaded to Dropbox by external tools, and the automation is triggered via cron-job.org webhooks.

## 🚀 Features

- **Dropbox Monitoring**: Watches Dropbox folder for new/updated inventory files
- **Smart Comparison**: Compares SKUs and detects price/stock differences
- **Automatic Updates**: Updates prices and stock in Holded via API
- **Offer Detection**: Adds discount tags when prices are reduced
- **Email Notifications**: Sends detailed reports via SMTP
- **Webhook Triggers**: Activated by cron-job.org for reliable scheduling
- **Simple Setup**: No email parsing complexity - external tools handle email downloads

## 📁 Project Structure

```
update_inventory/
├── main.py                    # Main entry point and orchestration
├── config.py                  # Configuration management
├── dropbox_handler.py         # Dropbox file monitoring
├── file_processor.py          # CSV/Excel file parsing
├── holded_api.py             # Holded API integration
├── inventory_updater.py       # Core comparison and update logic
├── email_notifier.py         # Email notifications
├── requirements.txt           # Python dependencies
├── .github/workflows/         # GitHub Actions automation
│   └── inventory-update.yml
└── README.md                 # This file
```

## 🔄 Workflow Overview

1. **Email Processing** (External): Email attachments are automatically downloaded to Dropbox
2. **Scheduled Trigger**: cron-job.org sends webhook to GitHub Actions
3. **Dropbox Check**: Automation scans Dropbox folder for new/updated files
4. **File Processing**: CSV/Excel files are parsed and validated
5. **Inventory Sync**: Products are compared and updated in Holded
6. **Notification**: Email report is sent with update summary

## 🛠️ Setup Instructions

### 1. Environment Variables

Create a `.env` file in the project root:

```bash
# Email Configuration (SMTP - for notifications only, using SSL)
SMTP_HOST=your-smtp-server.com
SMTP_PORT=465
SMTP_USERNAME=your-email@yourdomain.com
SMTP_PASSWORD=your-email-password

# Dropbox Configuration
DROPBOX_ACCESS_TOKEN=your-dropbox-access-token
DROPBOX_FOLDER_PATH=/your-folder-path

# Holded API Configuration
HOLDED_API_KEY=your-holded-api-key
HOLDED_BASE_URL=https://api.holded.com/api
HOLDED_WAREHOUSE_ID=your-warehouse-id

# Notification Email
NOTIFICATION_EMAIL=admin@yourdomain.com

# File Processing Configuration
ALLOWED_EXTENSIONS=csv,xlsx,xls
MAX_FILE_SIZE_MB=10
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Test Connections

```bash
python main.py test
```

This will verify all external connections (Holded API, Dropbox, Email SMTP).

### 4. GitHub Actions Setup

1. Go to your GitHub repository Settings > Secrets and variables > Actions
2. Add the following repository secrets:
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`
   - `DROPBOX_ACCESS_TOKEN`, `DROPBOX_FOLDER_PATH`
   - `HOLDED_API_KEY`, `HOLDED_BASE_URL`
   - `NOTIFICATION_EMAIL`

### 5. cron-job.org Setup

1. Create an account at [cron-job.org](https://cron-job.org)
2. Create a new cron job with the following settings:

   - **URL**: `https://api.github.com/repos/[USERNAME]/[REPO]/dispatches`
   - **HTTP Method**: POST
   - **Headers**:
     ```
     Authorization: token YOUR_GITHUB_TOKEN
     Accept: application/vnd.github.v3+json
     Content-Type: application/json
     ```
   - **Body**:
     ```json
     { "event_type": "inventory-update" }
     ```
   - **Schedule**: Every 15 minutes during business hours

3. Create a GitHub Personal Access Token with `repo` permissions

## 🔧 Usage

### Local Execution

```bash
# Run automation (check Dropbox)
python main.py

# Test connections only
python main.py test

# Dropbox-only mode (same as default)
python main.py dropbox

# Process a local file
python main.py file path/to/inventory.csv
```

### GitHub Actions

The automation runs automatically via webhook from cron-job.org:

- **Trigger**: Webhook from cron-job.org (configurable schedule)
- **Manual**: Use "Actions" tab in GitHub to trigger manually

## 📄 File Format Requirements

Your inventory files (CSV/Excel) should contain columns for:

- **SKU/Code**: Product identifier (required)
- **Price**: Product price (optional)
- **Stock**: Stock quantity (optional)

### CSV Format Examples

The system supports various CSV formats with flexible column mapping:

- **Item/SKU**: Product identifier (maps to SKU)
- **Price**: Regular price (maps to Price)
- **Offer Price**: Special/promotional price (takes priority over regular price)
- **Stock**: Stock quantity (maps to Stock)

**Special Stock Handling**: Stock values like ">10" are automatically converted to numeric values.

### Supported Column Names

The system auto-detects columns using these variations:

- **SKU**: `sku`, `code`, `product_code`, `item_code`, `ref`, `item`, `identifier`
- **Price**: `price`, `cost`, `amount`, `regular_price`, `base_price`
- **Offer**: `offer`, `special_price`, `promo_price`, `discount_price`
- **Stock**: `stock`, `quantity`, `units`, `inventory`, `available`, `qty`

### Example CSV

```csv
SKU,Price,Stock
[PRODUCT_SKU_1],[PRICE_1],[STOCK_1]
[PRODUCT_SKU_2],[PRICE_2],[STOCK_2]
[PRODUCT_SKU_3],[PRICE_3],[STOCK_3]
```

## 🔄 How It Works

1. **Email to Dropbox** (External):

   - Set up email rules or automation tools (Zapier, IFTTT, etc.)
   - Automatically download email attachments to Dropbox folder

2. **Trigger**:

   - cron-job.org sends webhook to GitHub Actions on schedule
   - GitHub Actions starts the automation workflow

3. **File Processing**:

   - Monitors Dropbox folder for new/updated files
   - Downloads and parses CSV/Excel files
   - Validates data format and extracts product information

4. **Inventory Comparison**:

   - Retrieves current products from Holded API
   - Compares SKUs, prices, and stock levels
   - Identifies differences that need updating

5. **Updates**:

   - Generates price update requests (adds discount tags if price is lower)
   - Generates stock update requests
   - Performs PUT requests to Holded API

6. **Notification**:
   - Sends detailed email report with update summary
   - Includes tables of changed products and any errors

## 🔧 Technical Implementation

### Holded API Integration

The system uses the correct Holded API endpoints and data structures:

- **Price Updates**: `PUT /api/invoicing/v1/products/{productId}`
  - Uses `{"kind": "variants", "subtotal": price}` structure for both main products and variants
  - Adds discount tags for reduced prices
- **Stock Updates**: `PUT /api/invoicing/v1/products/{productId}/stock`
  - Uses warehouse-based structure: `{"stock": {"warehouseId": {"variantId": stock_difference}}}`
  - Calculates stock difference (target - current) instead of absolute values
  - Requires `HOLDED_WAREHOUSE_ID` configuration

### Product Matching

Products are matched between CSV and Holded using multiple SKU field variations:

- `sku`, `code`, `reference`, `item_code`, `product_code`, `ref`, `item`, `identifier`

The system creates a lookup table for efficient matching and logs detailed information for debugging.

## 📧 Email Notifications

You'll receive detailed HTML emails with:

- **Summary**: Files processed, products updated, errors
- **Price Updates**: Table showing old vs new prices and offer status
- **Stock Updates**: Table showing stock changes
- **Error Details**: Any issues encountered during processing

## ⚙️ Configuration Options

### File Restrictions

Control which files are processed:

```bash
ALLOWED_EXTENSIONS=csv,xlsx,xls
MAX_FILE_SIZE_MB=10
```

### Dropbox Folder

Set the monitored Dropbox folder:

```bash
DROPBOX_FOLDER_PATH=/your-folder-path
```

### Webhook Schedule

Configure cron-job.org schedule (examples):

```
*/15 8-20 * * 1-5  # Every 15 minutes, 8 AM to 8 PM, Monday to Friday
0 9,12,15,18 * * * # 4 times per day at 9 AM, 12 PM, 3 PM, 6 PM
0 */2 * * *        # Every 2 hours
```

## 🐛 Troubleshooting

### Common Issues

1. **Webhook Not Triggering**

   - Verify GitHub token has correct permissions
   - Check cron-job.org logs for errors
   - Ensure repository dispatch is enabled

2. **Holded API Errors**

   - Verify API key is valid and has sufficient permissions
   - Check if product IDs exist in Holded

3. **Dropbox Connection Failed**

   - Regenerate access token
   - Verify folder path exists

4. **File Processing Errors**
   - Check file format and column names
   - Ensure SKU column is present

### Logs

- Local runs: Check `inventory_update.log`
- GitHub Actions: Download logs from Actions tab
- cron-job.org: Check execution history in dashboard

## 🔒 Security and Privacy Features

### Data Protection
- **Sensitive Data Filtering**: All logs automatically redact sensitive information
- **Secure File Handling**: Files are processed in memory and cleaned up automatically
- **Credential Protection**: API keys, tokens, and passwords are never logged
- **Temporary Storage**: Downloaded files are removed after processing

### Security Best Practices
- Never commit `.env` file to version control
- Use GitHub repository secrets for sensitive data
- Regularly rotate API keys and passwords
- Limit Dropbox access token permissions to specific folder
- Enable two-factor authentication on all accounts
- Use restricted API keys with minimal permissions

## 💡 External Email Processing Options

To automatically download email attachments to Dropbox:

1. **Zapier**: Create zap Email → Dropbox
2. **IFTTT**: Create applet Gmail → Dropbox
3. **Power Automate**: Create flow Outlook → Dropbox
4. **Email Rules**: Server-side rules (if supported)
5. **Custom Script**: Python script with IMAP → Dropbox

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes (keep functions under 100 lines)
4. Add tests and documentation
5. Submit a pull request

## 📝 License

This project is proprietary and confidential.

## 📞 Support

For issues or questions:

1. Check logs for detailed error messages
2. Verify all environment variables are set correctly
3. Test connections using `python main.py test`
4. Check cron-job.org execution logs
5. Create an issue in the repository with logs and error details
