"""
=============================================================================
orders.py - Checkout, Order History, Seller Dashboard, and Admin View
=============================================================================
This module handles:
1. Checkout processing: Creates an order, saves order_items, marks products as 'sold'.
2. Buyer Order History: Displays past orders and purchased items.
3. Seller Dashboard: Metrics (earnings, active vs sold listings) and inventory management.
4. Admin Panel: Complete system oversight (all users, all products, all orders).
5. All operations strictly utilize parameterized SQL queries (? placeholders).
=============================================================================
"""

import os
from datetime import datetime
import streamlit as st
from database import BASE_DIR, get_connection, execute_query, fetch_all, fetch_one


# =============================================================================
# 1. CHECKOUT PROCESS
# =============================================================================

def render_checkout_page():
    """
    Renders the checkout form, validates shipping info, records order and items,
    saves the chosen payment method, transitions products to 'sold',
    and displays seller UPI ID for direct peer-to-peer payment when chosen.
    """
    st.markdown("## 💳 Order Checkout")
    st.caption("Finalize your sustainable pre-loved clothing purchase.")

    current_user = st.session_state.get("user")
    if not current_user:
        st.warning("⚠️ Please log in to complete checkout.")
        return

    # If an order was just placed, display the complete confirmation & payment screen
    if "placed_order" in st.session_state and st.session_state["placed_order"]:
        order_info = st.session_state["placed_order"]
        st.balloons()
        st.success(f"🎉 Order placed successfully! Your Order ID is **#{order_info['order_id']}**.")
        
        with st.container(border=True):
            st.markdown("### 📋 Order Confirmation Details")
            st.write(f"- **Recipient:** {order_info['recipient_name']} ({order_info['phone']})")
            st.write(f"- **Delivery Address:** {order_info['address']}")
            st.write(f"- **Total Amount:** **₹{order_info['total_amount']:.2f}**")
            st.write(f"- **Payment Method:** `{order_info['payment_method']}`")
            
            st.divider()

            # Payment Instructions
            if order_info["payment_method"] == "Pay seller directly (UPI)":
                st.markdown("### 📱 Pay Seller Directly (UPI)")
                st.caption("No real money or bank account numbers needed. Transfer directly to the seller via any UPI app (GPay, PhonePe, Paytm, BHIM):")
                
                for seller_id, s_data in order_info["sellers"].items():
                    with st.container(border=True):
                        st.markdown(f"**Seller:** {s_data['name']}")
                        st.markdown(f"**Amount Due:** ₹{s_data['amount']:.2f} *(for: {', '.join(s_data['items'])})*")
                        if s_data.get("upi_id"):
                            st.markdown(f"**Seller UPI ID:** `{s_data['upi_id']}`")
                            st.info(f"💡 Open your UPI app and send **₹{s_data['amount']:.2f}** to `{s_data['upi_id']}`.")
                        else:
                            st.info(f"ℹ️ The seller ({s_data['name']}) has not set a UPI ID yet. They will share payment details directly upon order confirmation.")
            else:
                st.info(f"💵 **Cash on Delivery Selected:** Please pay **₹{order_info['total_amount']:.2f}** in cash or scan the delivery agent's QR code upon delivery.")

        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("🛍️ Continue Shopping", use_container_width=True):
                st.session_state["placed_order"] = None
                st.session_state["page"] = "marketplace"
                st.rerun()
        with c_btn2:
            if st.button("📦 View My Orders", use_container_width=True):
                st.session_state["placed_order"] = None
                st.session_state["page"] = "orders"
                st.rerun()
        return

    # Normal checkout flow
    cart = st.session_state.get("cart", [])
    if not cart:
        st.info("Your cart is empty. Nothing to checkout.")
        return

    # Fetch available items in cart
    placeholders = ",".join(["?"] * len(cart))
    items = fetch_all(
        f"SELECT * FROM products WHERE product_id IN ({placeholders}) AND status = 'available'",
        tuple(cart)
    )

    if not items:
        st.error("⚠️ All items in your cart have already been sold or are unavailable.")
        return

    total_amount = sum(item["price"] for item in items)

    col_form, col_review = st.columns([3, 2])

    with col_review:
        with st.container(border=True):
            st.markdown("### 🛒 Items in this Order")
            for item in items:
                st.write(f"- **{item['title']}** ({item['size']}) — ₹{item['price']:.2f}")
            st.divider()
            st.markdown(f"#### **Total to Pay: ₹{total_amount:.2f}**")
            st.caption("🚚 Packaging & Delivery: FREE")

    with col_form:
        with st.form("checkout_form"):
            st.markdown("### 📦 Delivery Details")
            recipient_name = st.text_input("Recipient Full Name *", value=current_user.get("name", ""))
            phone = st.text_input("Mobile Phone Number *", placeholder="e.g. 9876543210")
            address = st.text_area("Complete Delivery Address *", placeholder="House/Flat No, Street, Landmark, City, Pincode")
            
            # Simple payment method choice without real money
            payment_method = st.radio(
                "Payment Method *",
                options=["Cash on Delivery", "Pay seller directly (UPI)"],
                help="Select how you wish to pay. Direct UPI displays the seller's UPI ID upon ordering."
            )

            submit_order = st.form_submit_button("✅ Place Order Now", type="primary", use_container_width=True)

            if submit_order:
                # Validation checks
                if not recipient_name.strip():
                    st.error("⚠️ Please enter the recipient name.")
                elif not phone.strip() or len(phone.strip()) < 10:
                    st.error("⚠️ Please enter a valid 10-digit phone number.")
                elif not address.strip():
                    st.error("⚠️ Please enter your delivery address.")
                else:
                    try:
                        # Transactional DB operations
                        conn = get_connection()
                        cursor = conn.cursor()

                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        # 1. Insert into orders table with chosen payment method
                        cursor.execute(
                            """
                            INSERT INTO orders (buyer_id, total_amount, payment_method, status, created_at)
                            VALUES (?, ?, ?, 'completed', ?)
                            """,
                            (current_user["user_id"], total_amount, payment_method, now_str)
                        )
                        order_id = cursor.lastrowid

                        # 2. Insert each item into order_items and mark product as 'sold'
                        sellers_map = {}
                        for item in items:
                            cursor.execute(
                                """
                                INSERT INTO order_items (order_id, product_id, quantity, price)
                                VALUES (?, ?, 1, ?)
                                """,
                                (order_id, item["product_id"], item["price"])
                            )
                            # Mark product as sold
                            cursor.execute(
                                "UPDATE products SET status = 'sold' WHERE product_id = ?",
                                (item["product_id"],)
                            )
                            # Remove from any user's wishlist
                            cursor.execute(
                                "DELETE FROM wishlist WHERE product_id = ?",
                                (item["product_id"],)
                            )

                            # Aggregate seller info for payment display
                            s_id = item["seller_id"]
                            if s_id not in sellers_map:
                                s_row = fetch_one("SELECT name, upi_id FROM users WHERE user_id = ?", (s_id,))
                                sellers_map[s_id] = {
                                    "name": s_row["name"] if s_row else "Seller",
                                    "upi_id": s_row.get("upi_id") if s_row else None,
                                    "amount": 0.0,
                                    "items": []
                                }
                            sellers_map[s_id]["amount"] += item["price"]
                            sellers_map[s_id]["items"].append(item["title"])

                        conn.commit()
                        conn.close()

                        # Clear cart in session state
                        st.session_state["cart"] = []

                        # Store confirmation data for persistent rendering
                        st.session_state["placed_order"] = {
                            "order_id": order_id,
                            "recipient_name": recipient_name.strip(),
                            "phone": phone.strip(),
                            "address": address.strip(),
                            "total_amount": total_amount,
                            "payment_method": payment_method,
                            "sellers": sellers_map
                        }
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Failed to process order: {str(e)}")


# =============================================================================
# 2. BUYER ORDER HISTORY
# =============================================================================

def render_order_history_page():
    """
    Renders past purchases for the currently logged-in buyer.
    Shows order number, timestamp, purchased products, and total price.
    """
    st.markdown("## 📦 My Order History")
    st.caption("Track all your previous sustainable fashion orders from ReWear.")

    current_user = st.session_state.get("user")
    if not current_user:
        st.warning("⚠️ Please log in to view your order history.")
        return

    # Fetch orders for this buyer (parameterized query)
    user_orders = fetch_all(
        "SELECT * FROM orders WHERE buyer_id = ? ORDER BY order_id DESC",
        (current_user["user_id"],)
    )

    if not user_orders:
        st.info("You haven't placed any orders yet. Visit the Marketplace to explore pre-loved clothes!")
        return

    for order in user_orders:
        with st.container(border=True):
            o_head1, o_head2, o_head3 = st.columns([2, 2, 2])
            with o_head1:
                st.markdown(f"### Order #{order['order_id']}")
                st.caption(f"Placed on: {order['created_at']}")
            with o_head2:
                st.markdown(f"**Total: ₹{order['total_amount']:.2f}**")
                st.caption(f"Payment: `{order.get('payment_method', 'Cash on Delivery')}`")
            with o_head3:
                st.markdown(f"Status: `🟢 {order['status'].capitalize()}`")

            st.divider()

            # Fetch items for this specific order
            order_items = fetch_all(
                """
                SELECT oi.price, p.title, p.category, p.size, p.image_path
                FROM order_items oi
                JOIN products p ON oi.product_id = p.product_id
                WHERE oi.order_id = ?
                """,
                (order["order_id"],)
            )

            for item in order_items:
                col_i, col_t, col_p = st.columns([1, 4, 1])
                with col_i:
                    img_path = os.path.join(BASE_DIR, item["image_path"]) if item.get("image_path") else None
                    if img_path and os.path.exists(img_path):
                        st.image(img_path, width=60)
                    else:
                        st.markdown("👕")
                with col_t:
                    st.write(f"**{item['title']}**")
                    st.caption(f"{item['category']} | Size: {item['size']}")
                with col_p:
                    st.write(f"₹{item['price']:.2f}")


# =============================================================================
# 3. SELLER DASHBOARD
# =============================================================================

def render_seller_dashboard():
    """
    Provides sellers with key sales metrics:
    Total listings, active listings, sold items, and total revenue earned.
    """
    st.markdown("## 📊 Seller Dashboard")
    st.caption("Monitor your pre-loved fashion sales, active inventory, and revenue.")

    current_user = st.session_state.get("user")
    if not current_user or current_user.get("role") not in ("seller", "admin"):
        st.warning("⚠️ Access restricted to Sellers and Admins.")
        return

    seller_id = current_user["user_id"]

    # Optional Seller UPI Payment Configuration
    seller_user = fetch_one("SELECT name, email, upi_id FROM users WHERE user_id = ?", (seller_id,))
    current_upi = seller_user.get("upi_id") or ""

    with st.expander("⚙️ Seller Payment Settings (UPI ID)"):
        st.caption("Add your personal or business UPI ID so buyers can pay you directly. **No bank account numbers or card details needed.**")
        with st.form("seller_upi_form"):
            col_upi1, col_upi2 = st.columns([3, 1])
            with col_upi1:
                new_upi = st.text_input(
                    "Your UPI ID (Optional)",
                    value=current_upi,
                    placeholder="e.g. name@okaxis, shop@upi, mobile@paytm"
                )
            with col_upi2:
                st.write("")
                st.write("")
                save_upi = st.form_submit_button("💾 Save UPI ID", use_container_width=True)

            if save_upi:
                execute_query("UPDATE users SET upi_id = ? WHERE user_id = ?", (new_upi.strip(), seller_id))
                st.success("✅ UPI ID saved! Buyers who select 'Pay seller directly (UPI)' will see this ID at checkout.")
                st.rerun()

    # Calculate metrics with parameterized SQL
    all_listings = fetch_all("SELECT * FROM products WHERE seller_id = ? ORDER BY product_id DESC", (seller_id,))
    active_listings = [p for p in all_listings if p["status"] == "available"]
    sold_listings = [p for p in all_listings if p["status"] == "sold"]
    total_earnings = sum(p["price"] for p in sold_listings)

    # Metric Cards
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Listings", len(all_listings))
    with m2:
        st.metric("Active Listings", len(active_listings))
    with m3:
        st.metric("Items Sold", len(sold_listings))
    with m4:
        st.metric("Total Earnings", f"₹{total_earnings:.2f}")

    st.divider()

    tab_active, tab_sold = st.tabs(["🟢 Active Inventory", "💰 Sold Items"])

    with tab_active:
        if not active_listings:
            st.info("No active listings. Click 'Add Product' from the sidebar to list a new piece of clothing!")
        else:
            for item in active_listings:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1, 4, 1])
                    with c1:
                        img_path = os.path.join(BASE_DIR, item["image_path"]) if item.get("image_path") else None
                        if img_path and os.path.exists(img_path):
                            st.image(img_path, width=70)
                        else:
                            st.markdown("👕")
                    with c2:
                        st.markdown(f"**{item['title']}**")
                        st.caption(f"Category: {item['category']} | Size: {item['size']} | Price: ₹{item['price']:.2f}")
                    with c3:
                        if st.button("🗑️ Delete", key=f"del_prod_{item['product_id']}"):
                            execute_query("DELETE FROM products WHERE product_id = ? AND seller_id = ?", (item["product_id"], seller_id))
                            st.toast(f"Deleted '{item['title']}'.")
                            st.rerun()

    with tab_sold:
        # Fetch sold items joined with orders and buyer information
        sold_orders = fetch_all(
            """
            SELECT 
                p.product_id,
                p.title,
                p.category,
                p.size,
                p.image_path,
                oi.price as sold_price,
                o.order_id,
                o.payment_method,
                o.created_at as order_date,
                u.name as buyer_name,
                u.email as buyer_email
            FROM products p
            JOIN order_items oi ON p.product_id = oi.product_id
            JOIN orders o ON oi.order_id = o.order_id
            JOIN users u ON o.buyer_id = u.user_id
            WHERE p.seller_id = ?
            ORDER BY o.order_id DESC
            """,
            (seller_id,)
        )

        if not sold_orders:
            st.info("No items sold yet. When a customer purchases your pre-loved clothes, order details with buyer name and payment method will appear here.")
        else:
            for item in sold_orders:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1, 3, 2])
                    with c1:
                        img_path = os.path.join(BASE_DIR, item["image_path"]) if item.get("image_path") else None
                        if img_path and os.path.exists(img_path):
                            st.image(img_path, width=70)
                        else:
                            st.markdown("👕")
                    with c2:
                        st.markdown(f"**{item['title']}**")
                        st.caption(f"{item['category']} | Size: {item['size']} | Order #{item['order_id']} • {item['order_date']}")
                        st.markdown(f"👤 **Buyer:** {item['buyer_name']} (`{item['buyer_email']}`)")
                    with c3:
                        st.markdown(f"<span style='color:green;font-size:18px;'>**+ ₹{item['sold_price']:.2f}**</span>", unsafe_allow_html=True)
                        st.markdown(f"💳 **Payment:** `{item['payment_method']}`")
                        st.caption("Status: Sold ✓")


# =============================================================================
# 4. ADMIN PANEL (FULL SYSTEM OVERVIEW)
# =============================================================================

def render_admin_panel():
    """
    Renders simple admin view for platform administrators:
    - Platform-wide statistics (users, products, orders, GMV).
    - Complete tables for all users, all products, and all orders.
    """
    st.markdown("## 🛡️ Admin Control Panel")
    st.caption("Platform-wide administrative overview for ReWear.")

    current_user = st.session_state.get("user")
    if not current_user or current_user.get("role") != "admin":
        st.error("⛔ Access Denied. Only platform administrators can view this page.")
        return

    # System-wide metrics
    users = fetch_all("SELECT user_id, name, email, role FROM users ORDER BY user_id ASC")
    products = fetch_all("SELECT * FROM products ORDER BY product_id DESC")
    orders = fetch_all("SELECT * FROM orders ORDER BY order_id DESC")
    
    total_revenue = sum(o["total_amount"] for o in orders)
    available_count = sum(1 for p in products if p["status"] == "available")
    sold_count = sum(1 for p in products if p["status"] == "sold")

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("Total Users", len(users))
    with kpi2:
        st.metric("Total Products", f"{len(products)} ({available_count} live)")
    with kpi3:
        st.metric("Total Orders", len(orders))
    with kpi4:
        st.metric("Platform GMV", f"₹{total_revenue:.2f}")

    st.divider()

    tab_users, tab_prods, tab_orders, tab_donations = st.tabs(
        ["👥 All Users", "👕 All Products", "📦 All Orders", "♻️ All Donations"]
    )

    with tab_users:
        st.dataframe(users, use_container_width=True)

    with tab_prods:
        st.dataframe(products, use_container_width=True)

    with tab_orders:
        st.dataframe(orders, use_container_width=True)

    with tab_donations:
        all_donations = fetch_all(
            """
            SELECT 
                d.donation_id, d.user_id, d.type, d.quantity, d.condition,
                d.city, d.contact, d.image_path, d.status, d.created_at,
                u.name as donor_name, u.email as donor_email
            FROM donations d
            JOIN users u ON d.user_id = u.user_id
            ORDER BY d.donation_id DESC
            """
        )

        if not all_donations:
            st.info("No clothes donation or recycling requests received yet.")
        else:
            pending_count = sum(1 for d in all_donations if d["status"] == "Pending")
            collected_count = sum(1 for d in all_donations if d["status"] == "Collected")
            st.markdown(f"**Total Requests:** {len(all_donations)} &nbsp;|&nbsp; 🟡 **Pending:** {pending_count} &nbsp;|&nbsp; 🟢 **Collected:** {collected_count}")
            st.divider()

            for don in all_donations:
                with st.container(border=True):
                    c_img, c_detail, c_act = st.columns([1, 3, 2])

                    with c_img:
                        if don.get("image_path"):
                            full_path = os.path.join(BASE_DIR, don["image_path"])
                            if os.path.exists(full_path):
                                st.image(full_path, width=70)
                            else:
                                st.markdown("👕")
                        else:
                            st.markdown("👕")

                    with c_detail:
                        st.markdown(f"**Donation #{don['donation_id']} — {don['type']}**")
                        st.caption(f"Donor: **{don['donor_name']}** (`{don['donor_email']}`) • {don['created_at']}")
                        st.write(f"**Quantity:** {don['quantity']} pieces &nbsp;|&nbsp; **Condition:** `{don['condition']}`")
                        st.write(f"📍 **Pickup City:** {don['city']} &nbsp;|&nbsp; 📞 **Contact:** {don['contact']}")

                    with c_act:
                        if don["status"] == "Collected":
                            st.markdown("🟢 **Collected**")
                            st.caption("Completed ✓")
                        else:
                            st.markdown("🟡 **Pending Pickup**")
                            if st.button("✅ Mark as Collected", key=f"mark_collected_{don['donation_id']}", use_container_width=True):
                                execute_query(
                                    "UPDATE donations SET status = 'Collected' WHERE donation_id = ?",
                                    (don["donation_id"],)
                                )
                                st.toast(f"Donation #{don['donation_id']} marked as Collected!")
                                st.rerun()
