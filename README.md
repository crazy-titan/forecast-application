# ChainCast: Professional Supply Chain Forecasting

ChainCast is a high-precision, decision-intelligence platform designed for supply chain practitioners. It transforms raw time-series data into actionable business insights by combining state-of-the-art statistical models with core supply chain inventory metrics.

## Key Features

### Advanced Forecasting Engine
The application uses the Nixtla statsforecast library to provide world-class forecasting performance.
- Automated Model Selection: Automatically pits AutoARIMA, SeasonalNaive, and SARIMA models against each other using cross-validation.
- Manual Tuning Mode: Direct control over ARIMA parameters (p, d, q) for advanced statistical analysis.
- Seasonality Detection: Automatic identification of business cycles (daily, weekly, monthly).

### Supply Chain Intelligence
Beyond raw predictions, ChainCast calculates critical inventory parameters:
- Reorder Point (ROP): Data-driven determination of when to place new orders.
- Safety Stock: Statistical buffer calculation to prevent stockouts during unexpected demand spikes.
- Service Level Targets: Ability to tune inventory buffers based on desired fulfillment probabilities (e.g., 95% or 99%).
- Stockout Risk Zone: Visual identification of periods where demand is statistically likely to exceed available inventory.

### Professional Reporting
- High-Fidelity PDF Export: Comprehensive 6-section reports including processing transparency, model metrics, and future breakdowns.
- CSV Data Export: Full raw forecast data output for further analysis in Excel or ERP systems.
- Data Transparency: Automated reporting of data gaps, duplicate handling, and stationarity adjustments.

### Modern Interactive Dashboard
- Global Smart Tooltips: Context-aware guidance for every statistical parameter.
- Plotly Visualizations: Interactive history vs. forecast views with confidence interval "glow" zones.
- Glassmorphism Interface: A premium, dark-mode focused UI designed for high performance and reduced visual fatigue.

## Technical Architecture

### Backend
- Framework: FastAPI (Python 3.10+)
- Process Manager: Gunicorn (Production) / Uvicorn (Development)
- Forecasting: Nixtla statsforecast, utilsforecast
- Performance: NumPy, Pandas
- Reporting: fpdf2

### Frontend
- Logic: Vanilla JavaScript (ES6+)
- Styling: Modern CSS with custom design tokens
- Charts: Plotly.js

## Quick Start

### Prerequisites
- Python 3.10 or higher
- Docker (optional, for containerized deployment)

### Local Development (Virtual Environment)
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the development server:
   ```bash
   python -m backend.main
   ```
3. Access the application at: `http://localhost:8000`

### Production Deployment (Docker)
1. Build the image:
   ```bash
   docker build -t chaincast-app .
   ```
2. Run the container:
   ```bash
   docker run -p 8000:8000 chaincast-app
   ```

## Data Requirements
ChainCast requires a CSV file with at least two columns:
1. A Date column (e.g., "date", "timestamp", "ds").
2. A Demand/Value column (e.g., "units", "quantity", "y").
3. (Optional) A Unique ID column (e.g., "SKU", "region", "product_id") for forecasting multiple series at once.

## License
This project is proprietary and built for supply chain decision intelligence.
