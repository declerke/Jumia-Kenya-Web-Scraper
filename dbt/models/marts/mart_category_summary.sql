/*
  mart_category_summary
  ----------------------
  Aggregated price intelligence per category per scrape_date.

  Metrics:
  - avg_price_kes, min_price_kes, max_price_kes
  - avg_discount_pct (only among products that have a discount)
  - product_count
  - discounted_count : number of products with a discount
*/

SELECT
    category,
    scrape_date,

    COUNT(*)                                                   AS product_count,
    ROUND(AVG(current_price_kes), 2)                          AS avg_price_kes,
    MIN(current_price_kes)                                     AS min_price_kes,
    MAX(current_price_kes)                                     AS max_price_kes,
    ROUND(AVG(CASE WHEN discount_pct > 0 THEN discount_pct END), 2)
                                                               AS avg_discount_pct,
    COUNT(CASE WHEN has_discount THEN 1 END)                  AS discounted_count,
    ROUND(
        100.0 * COUNT(CASE WHEN has_discount THEN 1 END) / NULLIF(COUNT(*), 0),
        1
    )                                                          AS pct_discounted

FROM {{ ref('fct_product_prices') }}
GROUP BY category, scrape_date
ORDER BY scrape_date DESC, product_count DESC
