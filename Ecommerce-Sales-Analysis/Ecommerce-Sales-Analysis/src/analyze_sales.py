"""Clean the UCI Online Retail dataset and produce analysis-ready CSV files."""
from pathlib import Path
import sys
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "data" / "raw" / "Online Retail.xlsx"
OUTPUT_DIR = ROOT / "outputs"


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {path}\nDownload 'Online Retail.xlsx' from "
            "https://archive.ics.uci.edu/dataset/352/online+retail and place it in data/raw/."
        )
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    required = {"InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing expected columns: {sorted(missing)}")
    return df


def clean_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    original_rows = len(df)
    data = df.copy()
    data["InvoiceNo"] = data["InvoiceNo"].astype("string").str.strip()
    data["StockCode"] = data["StockCode"].astype("string").str.strip()
    data["Description"] = data["Description"].astype("string").str.strip()
    data["Country"] = data["Country"].astype("string").str.strip()
    data["InvoiceDate"] = pd.to_datetime(data["InvoiceDate"], errors="coerce")
    data["Quantity"] = pd.to_numeric(data["Quantity"], errors="coerce")
    data["UnitPrice"] = pd.to_numeric(data["UnitPrice"], errors="coerce")
    data["CustomerID"] = pd.to_numeric(data["CustomerID"], errors="coerce").astype("Int64")

    exact_duplicates = int(data.duplicated().sum())
    data = data.drop_duplicates().copy()
    data = data.dropna(subset=["InvoiceNo", "StockCode", "InvoiceDate", "Quantity", "UnitPrice", "Country"])

    # The source marks cancellation invoices with an invoice number beginning with C.
    data["IsCancellationInvoice"] = data["InvoiceNo"].str.upper().str.startswith("C", na=False)
    data["IsNegativeQuantity"] = data["Quantity"] < 0
    data["IsReturnOrCancellationLike"] = data["IsCancellationInvoice"] | data["IsNegativeQuantity"]
    data["LineRevenue"] = data["Quantity"] * data["UnitPrice"]

    return_like = data.loc[data["IsReturnOrCancellationLike"]].copy()
    sales = data.loc[
        (~data["IsReturnOrCancellationLike"]) & (data["Quantity"] > 0) & (data["UnitPrice"] > 0)
    ].copy()
    sales["Description"] = sales["Description"].fillna("Unknown product")
    sales["InvoiceMonth"] = sales["InvoiceDate"].dt.to_period("M").astype(str)

    info = {
        "Rows in source file": original_rows,
        "Exact duplicate rows removed": exact_duplicates,
        "Rows in cleaned positive sales": len(sales),
        "Rows flagged as cancellation/return-like": len(return_like),
        "Sales rows with missing CustomerID": int(sales["CustomerID"].isna().sum()),
    }
    return sales, return_like, info


def create_outputs(sales: pd.DataFrame, return_like: pd.DataFrame, info: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Export only useful columns; avoid writing internal flags unnecessarily.
    export_cols = ["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country", "LineRevenue", "InvoiceMonth"]
    sales[export_cols].to_csv(OUTPUT_DIR / "sales_clean.csv", index=False)

    monthly = sales.groupby("InvoiceMonth", as_index=False).agg(
        Revenue=("LineRevenue", "sum"),
        Units_Sold=("Quantity", "sum"),
        Order_Count=("InvoiceNo", "nunique"),
        Unique_Customers=("CustomerID", "nunique"),
    ).sort_values("InvoiceMonth")
    monthly.to_csv(OUTPUT_DIR / "monthly_sales.csv", index=False)

    products = sales.groupby(["StockCode", "Description"], as_index=False).agg(
        Revenue=("LineRevenue", "sum"), Units_Sold=("Quantity", "sum"), Order_Count=("InvoiceNo", "nunique")
    ).sort_values("Revenue", ascending=False)
    products.head(20).to_csv(OUTPUT_DIR / "top_products.csv", index=False)

    countries = sales.groupby("Country", as_index=False).agg(
        Revenue=("LineRevenue", "sum"), Units_Sold=("Quantity", "sum"), Order_Count=("InvoiceNo", "nunique"),
        Unique_Customers=("CustomerID", "nunique")
    ).sort_values("Revenue", ascending=False)
    countries.to_csv(OUTPUT_DIR / "country_sales.csv", index=False)

    valid_customer_sales = sales.dropna(subset=["CustomerID"]).copy()
    if not valid_customer_sales.empty:
        snapshot_date = valid_customer_sales["InvoiceDate"].max().normalize() + pd.Timedelta(days=1)
        customers = valid_customer_sales.groupby("CustomerID", as_index=False).agg(
            Last_Order_Date=("InvoiceDate", "max"), Frequency=("InvoiceNo", "nunique"),
            Monetary_Value=("LineRevenue", "sum"), Total_Units=("Quantity", "sum")
        )
        customers["Recency_Days"] = (snapshot_date - customers["Last_Order_Date"].dt.normalize()).dt.days
        customers = customers[["CustomerID", "Recency_Days", "Frequency", "Monetary_Value", "Total_Units"]]
        customers.sort_values("Monetary_Value", ascending=False).to_csv(OUTPUT_DIR / "customer_summary.csv", index=False)
    else:
        pd.DataFrame(columns=["CustomerID", "Recency_Days", "Frequency", "Monetary_Value", "Total_Units"]).to_csv(OUTPUT_DIR / "customer_summary.csv", index=False)

    returns_by_month = return_like.assign(
        InvoiceMonth=return_like["InvoiceDate"].dt.to_period("M").astype(str)
    ).groupby("InvoiceMonth", as_index=False).agg(
        Flagged_Rows=("InvoiceNo", "size"), Flagged_Invoices=("InvoiceNo", "nunique"),
        Signed_Line_Value=("LineRevenue", "sum")
    ).sort_values("InvoiceMonth")
    returns_by_month.to_csv(OUTPUT_DIR / "return_cancellation_summary.csv", index=False)
    pd.DataFrame([{"Metric": key, "Value": value} for key, value in info.items()]).to_csv(OUTPUT_DIR / "cleaning_summary.csv", index=False)


def main() -> int:
    try:
        raw = load_data(INPUT_FILE)
        sales, return_like, info = clean_data(raw)
        create_outputs(sales, return_like, info)
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("Analysis complete. Generated files in outputs/:")
    for path in sorted(OUTPUT_DIR.glob("*.csv")):
        print(f" - {path.name}")
    print("\nCleaning summary:")
    for key, value in info.items():
        print(f" - {key}: {value:,}")
    print("\nNote: cancellation/return-like rows are a proxy, not proof of a completed refund.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
