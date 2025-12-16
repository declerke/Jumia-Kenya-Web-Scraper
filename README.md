# Jumia Kenya Product Scraper

A Python-based web scraping project designed to extract product and pricing data from Jumia Kenya's e-commerce platform across multiple categories.

This project was developed as a data acquisition component, demonstrating proficiency in web scraping best practices and data pipeline preparation.

---

## 🚀 Project Overview

The goal of this assignment was to accurately extract product information—including name, current price, old price, discount, and product URL—for two key product categories:

1.  **Smartphones**
2.  **Computing Devices**

The resulting data is cleaned, structured, and exported to separate CSV files, ready for downstream analysis or loading into a data warehouse.

---

## 🛠️ Technology Stack

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Language** | Python 3.x | Core programming language. |
| **Web Scraping** | `requests`, `BeautifulSoup4` | For fetching HTML and parsing product elements. |
| **Data Handling** | `Pandas` | For structuring, cleaning, and exporting data to CSV. |
| **Environment** | Jupyter Notebook (or `src/webscraper.py`) | Execution environment. |

### Prerequisites

To run this script locally, you must have Python installed. The required libraries can be installed using the following command:

```bash
pip install -r requirements.txt
# or
pip install pandas beautifulsoup4 requests
