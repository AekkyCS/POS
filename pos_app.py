import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import matplotlib.pyplot as plt
import time
import uuid
import pandas as pd
from io import StringIO
from datetime import datetime
firebase_api_key = st.secrets["FIREBASE_API_KEY"]
if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_api_key)
    firebase_admin.initialize_app(cred)

db = firestore.client()

st.sidebar.title("🛒 POS System")
menu = st.sidebar.radio("Select Menu", ["🏠 Dashboard", "📦 Manage Products", "🛍️ Sell Products", "📈 Sales Report"])

def update_stock(product_id, quantity):
    product_ref = db.collection("products").document(product_id)
    product = product_ref.get()
    if product.exists:
        new_stock = max(0, product.to_dict()["stock"] - quantity)
        product_ref.update({"stock": new_stock})

# Function to record a sale
def record_sale(cart):
    transaction_id = str(uuid.uuid4())[:8]
    sale_data = {
        "transaction_id": transaction_id,
        "items": cart,
        "total": sum(item["price"] * item["quantity"] for item in cart),
        "timestamp": time.time()
    }
    db.collection("sales").document(transaction_id).set(sale_data)
    return transaction_id
if menu == "🏠 Dashboard":
    st.title("🏠 POS System Dashboard")
    st.markdown("### Welcome to your POS system\nView the inventory and sales summary below")

    product_docs = list(db.collection("products").stream())
    sales_docs = list(db.collection("sales").stream())

    products_count = len(product_docs)
    transactions_count = len(sales_docs)
    total_revenue = sum(sale.to_dict().get("total", 0) for sale in sales_docs)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Products", products_count)
    col2.metric("Sales Transactions", transactions_count)
    col3.metric("Total Revenue (KIP)", f"{total_revenue:,.2f}")

    st.markdown("---")
    st.subheader("Recent Transactions")

    transactions_list = []
    for sale in sales_docs:
        data = sale.to_dict()
        transactions_list.append({
            "Transaction ID": data.get("transaction_id", ""),
            "Date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(data.get("timestamp", 0))),
            "Sales (KIP)": data.get("total", 0),
            "Timestamp": data.get("timestamp", 0)
        })

    transactions_list.sort(key=lambda x: x["Timestamp"], reverse=True)
    recent_transactions = transactions_list[:5]

    for tx in recent_transactions:
        tx.pop("Timestamp", None)

    st.table(recent_transactions)

    # Visualization: Total Revenue Over Time (Line Chart)
    sales_data = []
    for sale in sales_docs:
        data = sale.to_dict()
        sale_date = time.localtime(data['timestamp'])
        sale_date_str = time.strftime("%Y-%m-%d", sale_date)
        sales_data.append({
            "Date": sale_date_str,
            "Revenue": data.get("total", 0)
        })

    df_sales = pd.DataFrame(sales_data)
    df_sales_grouped = df_sales.groupby("Date").sum().reset_index()

    # Plot Total Revenue Over Time using Matplotlib
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df_sales_grouped["Date"], df_sales_grouped["Revenue"], marker='o', linestyle='-', color='b')
    ax.set_xlabel('Date')
    ax.set_ylabel('Total Revenue (KIP)')
    ax.set_title('Total Revenue Over Time')
    ax.set_xticklabels(df_sales_grouped["Date"], rotation=45, ha="right")
    st.pyplot(fig)

    st.markdown("---")

    # Visualization: Sales by Product (Bar Chart)
    product_sales_data = []
    for sale in sales_docs:
        data = sale.to_dict()
        for item in data["items"]:
            product_sales_data.append({
                "Product Name": item["name"],
                "Quantity Sold": item["quantity"],
                "Total Sales (KIP)": item["quantity"] * item["price"]
            })

    df_product_sales = pd.DataFrame(product_sales_data)
    df_product_sales_grouped = df_product_sales.groupby("Product Name").agg(
        Total_Quantity_Sold=("Quantity Sold", "sum"),
        Total_Sales=("Total Sales (KIP)", "sum")
    ).reset_index()

    # Plot Sales by Product using Matplotlib (Bar Chart)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(df_product_sales_grouped["Product Name"], df_product_sales_grouped["Total_Sales"], color='g')
    ax.set_xlabel('Product Name')
    ax.set_ylabel('Total Sales (KIP)')
    ax.set_title('Sales by Product')
    ax.set_xticklabels(df_product_sales_grouped["Product Name"], rotation=45, ha="right")
    st.pyplot(fig)
elif menu == "📦 Manage Products":
    st.title("📦 Manage Products")

    def add_product(name, price, stock):
        db.collection("products").add({
            "name": name,
            "price": price,
            "stock": stock,
            "created_at": time.time()
        })

    def update_product(product_id, name, price, stock):
        db.collection("products").document(product_id).update({
            "name": name,
            "price": price,
            "stock": stock
        })

    def delete_product(product_id):
        db.collection("products").document(product_id).delete()

    # For adding a new product
    product_name = st.text_input("📌 Product Name")
    product_price = st.number_input("💲 Price", min_value=0.0, step=0.1)
    product_stock = st.number_input("📦 Stock", min_value=0, step=1)

    if st.button("✅ Add Product"):
        if product_name and product_price and product_stock:
            add_product(product_name, product_price, product_stock)
            st.success(f"Added {product_name}!")
            st.rerun()  # Use st.rerun() instead of st.experimental_rerun() 
        else:
            st.warning("⚠️ Please fill in all fields.")

    st.subheader("📋 Product List")
    search_query = st.text_input("🔍 Search for Product")
    products = db.collection("products").stream()

    filtered_products = [product for product in products if search_query.lower() in product.to_dict()['name'].lower()]

    if filtered_products:
        for product in filtered_products:
            data = product.to_dict()
            st.write(f"**{data['name']}** - 💲{data['price']} | Stock: {data['stock']}")
            
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                # When the "Edit" button is clicked, show input fields to update the product
                edit_key = f"edit_{data['name']}"
                if st.button(f"✏️ Edit {data['name']}", key=edit_key):
                    # Store the product data in session_state to keep it after rerun
                    st.session_state.editing_product = data
                    st.session_state.is_editing = True
                    st.rerun()  # Rerun to show the edit form

            with col2:
                if st.button(f"🗑️ Delete {data['name']}", key=f"delete_{data['name']}"):
                    delete_product(product.id)
                    st.success(f"Deleted {data['name']}!")
                    st.rerun()

        # Check if we are in editing mode
        if 'is_editing' in st.session_state and st.session_state.is_editing:
            product_data = st.session_state.editing_product
            updated_name = st.text_input("Updated Name", product_data['name'])
            updated_price = st.number_input("Updated Price", min_value=0.0, value=product_data['price'], step=0.1)
            updated_stock = st.number_input("Updated Stock", min_value=0, value=product_data['stock'], step=1)

            if st.button("Update Product"):
                update_product(product.id, updated_name, updated_price, updated_stock)
                st.success(f"Updated {updated_name}!")
                st.session_state.is_editing = False  # Reset the editing flag
                st.rerun()  # Refresh the page to show updated products

    else:
        st.warning("No products found matching your search.")

elif menu == "🛍️ Sell Products":
    st.title("🛍️ Sell Products")

    # Check if there is a cart in session state
    if "cart" not in st.session_state:
        st.session_state.cart = []

    # Get products from Firebase
    products = {doc.id: doc.to_dict() for doc in db.collection("products").stream()}

    # Set default value for quantity if not set in session state
    if "quantity" not in st.session_state:
        st.session_state.quantity = 1

    # Set default value for selected_product if not set in session state
    if "selected_product" not in st.session_state:
        st.session_state.selected_product = "-- Select Product --"

    # Select a product to add to the cart
    selected_product = st.selectbox("🛒 Select Product", ["-- Select Product --"] + list(products.keys()), 
                                    format_func=lambda x: products.get(x, {}).get("name", x))

    # Number input for quantity
    quantity = st.number_input("🔢 Quantity", min_value=1, value=st.session_state.quantity, step=1)

    if selected_product != "-- Select Product --":
        # Get the available stock of the selected product
        available_stock = products[selected_product]["stock"]

        if quantity > available_stock:
            # Inform the user of the maximum available stock
            st.warning(f"⚠️ You can only purchase up to {available_stock} of this product. Please adjust your quantity.")

        # Add to Cart button
        if st.button("🛒 Add to Cart"):
            if quantity <= available_stock:
                # Check if the product is already in the cart
                found = False
                for item in st.session_state.cart:
                    if item["product_id"] == selected_product:
                        item["quantity"] += quantity
                        found = True
                        break
                if not found:
                    st.session_state.cart.append({
                        "product_id": selected_product,
                        "name": products[selected_product]["name"],
                        "price": products[selected_product]["price"],
                        "quantity": quantity
                    })
                st.success(f"Added {quantity} x {products[selected_product]['name']} to cart!")

                # Reset quantity after adding to the cart, but keep the selected product
                st.session_state.quantity = 1

    # Display Cart and Total
    if st.session_state.cart:
        st.subheader("🛒 Cart")
        total_price = 0
        for item in st.session_state.cart:
            st.write(f"{item['quantity']} x {item['name']} - {item['price']} KIP")
            total_price += item["price"] * item["quantity"]

        st.markdown(f"### Total: {total_price:,.2f} KIP")

        # Checkout button
        if st.button("💰 Checkout"):
            # Record the sale only if the quantities are valid
            transaction_id = record_sale(st.session_state.cart)
            for item in st.session_state.cart:
                update_stock(item["product_id"], item["quantity"])
            st.success(f"✅ Sale recorded! Transaction ID: {transaction_id}")
            st.session_state.cart.clear()  # Clear the cart after the sale
            st.rerun()


if menu == "📈 Sales Report":
    st.title("📈 Sales Report")

    current_time = datetime.now()
    start_date = st.date_input("Start Date", current_time.date())
    end_date = st.date_input("End Date", current_time.date())

    def filter_sales_by_date(start_date, end_date):
        sales = db.collection("sales").stream()
        filtered_sales = []

        for sale in sales:
            data = sale.to_dict()
            sale_date = time.localtime(data['timestamp'])
            sale_date_str = time.strftime("%Y-%m-%d", sale_date)
            if start_date <= sale_date_str <= end_date:
                filtered_sales.append(data)

        return filtered_sales

    filtered_sales = filter_sales_by_date(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

    if filtered_sales:

        for sale in filtered_sales:
            st.subheader(f"🧾 Transaction ID: {sale['transaction_id']}")
            st.write(f"📅 Date: {time.ctime(sale['timestamp'])}")
            st.write("🛍️ Items Sold:")
            for item in sale["items"]:
                st.write(f" - {item['quantity']} x {item['name']} ({item['price']} KIP)")
            st.write(f"💰 Total: {sale['total']:,.2f} KIP")
            st.markdown("---")

        sales_data = []
        for sale in filtered_sales:
            for item in sale["items"]:
                sales_data.append({
                    "Transaction ID": sale["transaction_id"],
                    "Date": time.ctime(sale['timestamp']),
                    "Product Name": item["name"],
                    "Quantity": item["quantity"],
                    "Price (KIP)": item["price"],
                    "Total (KIP)": item["quantity"] * item["price"]
                })

        df = pd.DataFrame(sales_data)

        # Provide option to download the filtered data as CSV
        csv = df.to_csv(index=False)
        st.download_button(
            label="Download Sales Report as CSV",
            data=csv,
            file_name="sales_report.csv",
            mime="text/csv"
        )

    else:
        st.warning("No sales found for the selected date range.")
