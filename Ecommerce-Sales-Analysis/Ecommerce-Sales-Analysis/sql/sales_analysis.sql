-- E-Commerce Sales & Customer Insights | MySQL 8+
-- Run this DDL first, then import outputs/sales_clean.csv using MySQL Workbench.
CREATE DATABASE IF NOT EXISTS ecommerce_analysis;
USE ecommerce_analysis;

DROP TABLE IF EXISTS sales_clean;
CREATE TABLE sales_clean (
    InvoiceNo VARCHAR(20) NOT NULL,
    StockCode VARCHAR(30),
    Description TEXT,
    Quantity INT,
    InvoiceDate DATETIME,
    UnitPrice DECIMAL(12, 4),
    CustomerID BIGINT NULL,
    Country VARCHAR(100),
    LineRevenue DECIMAL(14, 4),
    InvoiceMonth CHAR(7)
);

-- 1. Monthly sales trends
SELECT InvoiceMonth,
       ROUND(SUM(LineRevenue), 2) AS revenue,
       SUM(Quantity) AS units_sold,
       COUNT(DISTINCT InvoiceNo) AS order_count,
       COUNT(DISTINCT CustomerID) AS unique_customers
FROM sales_clean
GROUP BY InvoiceMonth
ORDER BY InvoiceMonth;

-- 2. Top 10 products by revenue
SELECT StockCode, Description,
       ROUND(SUM(LineRevenue), 2) AS revenue,
       SUM(Quantity) AS units_sold,
       COUNT(DISTINCT InvoiceNo) AS order_count
FROM sales_clean
GROUP BY StockCode, Description
ORDER BY revenue DESC
LIMIT 10;

-- 3. Country-wise performance
SELECT Country,
       ROUND(SUM(LineRevenue), 2) AS revenue,
       COUNT(DISTINCT InvoiceNo) AS order_count,
       COUNT(DISTINCT CustomerID) AS unique_customers
FROM sales_clean
GROUP BY Country
ORDER BY revenue DESC;

-- 4. Average order value (AOV = revenue / distinct invoices)
SELECT ROUND(SUM(LineRevenue) / NULLIF(COUNT(DISTINCT InvoiceNo), 0), 2) AS average_order_value
FROM sales_clean;

-- 5. Repeat-customer overview (customers with more than one distinct invoice)
WITH customer_orders AS (
    SELECT CustomerID, COUNT(DISTINCT InvoiceNo) AS order_count,
           SUM(LineRevenue) AS customer_revenue
    FROM sales_clean
    WHERE CustomerID IS NOT NULL
    GROUP BY CustomerID
)
SELECT COUNT(*) AS identified_customers,
       SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) AS repeat_customers,
       ROUND(100.0 * SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS repeat_customer_pct,
       ROUND(AVG(customer_revenue), 2) AS average_revenue_per_customer
FROM customer_orders;

-- 6. Customers with the highest recorded revenue
SELECT CustomerID, COUNT(DISTINCT InvoiceNo) AS order_count,
       ROUND(SUM(LineRevenue), 2) AS customer_revenue
FROM sales_clean
WHERE CustomerID IS NOT NULL
GROUP BY CustomerID
ORDER BY customer_revenue DESC
LIMIT 20;
