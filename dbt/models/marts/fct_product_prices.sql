/*
  fct_product_prices
  ------------------
  Core fact table. One row per product per scrape_date.

  Adds:
  - days_since_scraped   : age of the record in days (useful for freshness checks)
  - has_discount flag
  - price_delta_kes      : savings amount when old price is available
*/

SELECT
    product_id,
    product_name,
    brand,
    category,
    current_price_kes,
    old_price_kes,
    discount_pct,

    -- Derived columns
    CASE WHEN discount_pct IS NOT NULL AND discount_pct > 0 THEN TRUE ELSE FALSE END
                                                        AS has_discount,
    CASE
        WHEN old_price_kes IS NOT NULL AND old_price_kes > current_price_kes
        THEN (old_price_kes - current_price_kes)
        ELSE NULL
    END                                                AS price_delta_kes,

    product_url,
    page_num,

    -- Partition / time dimension
    scrape_date,
    scraped_at,
    CURRENT_DATE - scrape_date                         AS days_since_scraped

FROM {{ ref('stg_jumia_products') }}
