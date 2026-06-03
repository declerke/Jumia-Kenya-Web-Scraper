/*
  stg_jumia_products
  ------------------
  Staging layer: type casting, price cleaning, brand extraction.

  - Rows with NULL current_price_kes are excluded.
  - old_price_kes values of 0.0 are replaced with NULL.
  - Brand is extracted as the first word of product_name when it matches
    a known brand list; otherwise NULL.
*/

WITH source AS (

    SELECT
        product_id,
        product_name,
        current_price_kes::NUMERIC(12,2)                          AS current_price_kes,
        CASE
            WHEN old_price_kes = 0 THEN NULL
            ELSE old_price_kes::NUMERIC(12,2)
        END                                                        AS old_price_kes,
        discount_pct::NUMERIC(5,2)                                AS discount_pct,
        TRIM(category)                                             AS category,
        product_url,
        scraped_at,
        page_num,
        scrape_date
    FROM {{ source('raw', 'product_prices') }}
    WHERE current_price_kes IS NOT NULL

),

with_brand AS (

    SELECT
        *,
        CASE
            WHEN UPPER(SPLIT_PART(product_name, ' ', 1)) IN (
                'SAMSUNG', 'APPLE', 'IPHONE', 'XIAOMI', 'TECNO',
                'INFINIX', 'ITEL', 'NOKIA', 'OPPO', 'REALME',
                'VIVO', 'HUAWEI', 'LG', 'SONY', 'HISENSE',
                'TCL', 'PANASONIC', 'PHILIPS', 'DELL', 'HP',
                'LENOVO', 'ASUS', 'ACER', 'MSI', 'MICROSOFT',
                'CANON', 'EPSON', 'BROTHER', 'TOSHIBA', 'KENWOOD',
                'RAMTONS', 'BRUHM', 'NASCO', 'VON', 'ARISTON',
                'BEKO', 'WHIRLPOOL', 'BOSCH', 'ELECTROLUX', 'MIKA',
                'CENTURY', 'NIKON', 'FUJIFILM', 'JBL', 'BOSE',
                'HARMAN', 'ANKER', 'ORAIMO', 'PROCTER', 'UNILEVER',
                'NESTLE', 'COLGATE', 'DETTOL', 'NIVEA', 'DOVE'
            )
            THEN INITCAP(SPLIT_PART(product_name, ' ', 1))
            ELSE NULL
        END AS brand
    FROM source

)

SELECT
    product_id,
    product_name,
    brand,
    current_price_kes,
    old_price_kes,
    discount_pct,
    category,
    product_url,
    scraped_at,
    page_num,
    scrape_date
FROM with_brand
