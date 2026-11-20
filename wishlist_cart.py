"""
=============================================================================
wishlist_cart.py - Search/Filter, Wishlist, and Cart Module for ReWear
=============================================================================
This module handles:
1. Marketplace Search (by title) and multi-attribute Filters (Category, Size, Sorting).
2. Wishlist Management (Add, Remove, View saved items) linked to SQLite 'wishlist' table.
3. Shopping Cart Management using Streamlit session_state ('st.session_state.cart').
4. Cart pricing calculations (Subtotal, Eco-packaging, Total).
5. All database lookups strictly use parameterized queries (? placeholders).
=============================================================================
"""

import os
import streamlit as st
from database import BASE_DIR, execute_query, fetch_all, fetch_one
from products import render_product_card, CATEGORIES, SIZES


# =============================================================================
# 1. MARKETPLACE BROWSE WITH SEARCH & FILTERS
# =============================================================================

def render_marketplace():
    """
    Renders the main marketplace browsing interface with search, filters,
    and a 3-column product grid with images and interaction buttons.
    """
    st.markdown("## 🛍️ Browse Pre-Loved Clothes")
    st.caption("Shop curated, high-quality thrift fashion and reduce carbon footprint 🌿")

    # Search & Filter Controls
    with st.container(border=True):
        fcol1, fcol2, fcol3, fcol4 = st.columns([3, 2, 2, 2])
        
        with fcol1:
            search_query = st.text_input("🔍 Search by Name / Style", placeholder="e.g. Denim, Dress, Kurta...")
        with fcol2:
            selected_category = st.selectbox("🏷️ Category", options=["All Categories"] + CATEGORIES)
        with fcol3:
            selected_size = st.selectbox("📏 Size", options=["All Sizes"] + SIZES)
        with fcol4:
            sort_order = st.selectbox(
                "⚡ Sort By",
                options=["Newest First", "Price: Low to High", "Price: High to Low"]
            )

    # Build Dynamic Parameterized SQL Query
    base_sql = "SELECT * FROM products WHERE status = 'available'"
    params = []

    if search_query.strip():
        base_sql += " AND title LIKE ?"
        params.append(f"%{search_query.strip()}%")

    if selected_category != "All Categories":
        base_sql += " AND category = ?"
        params.append(selected_category)

    if selected_size != "All Sizes":
        base_sql += " AND size = ?"
        params.append(selected_size)

    # Sorting
    if sort_order == "Newest First":
        base_sql += " ORDER BY product_id DESC"
    elif sort_order == "Price: Low to High":
        base_sql += " ORDER BY price ASC"
    elif sort_order == "Price: High to Low":
        base_sql += " ORDER BY price DESC"

    products = fetch_all(base_sql, tuple(params))

    # Retrieve current user's wishlist IDs for real-time button states
    current_user = st.session_state.get("user")
    user_wishlist_ids = set()
    if current_user:
        w_rows = fetch_all("SELECT product_id FROM wishlist WHERE user_id = ?", (current_user["user_id"],))
        user_wishlist_ids = {r["product_id"] for r in w_rows}

    # Render Product Results Count
    st.markdown(f"**Found {len(products)} available pre-loved item(s)**")

    if not products:
        st.info("🔎 No clothing items matched your search filters. Try selecting 'All Categories' or clearing your search.")
        return

    # Render Responsive 3-Column Grid
    COLS_PER_ROW = 3
    for i in range(0, len(products), COLS_PER_ROW):
        row_products = products[i:i + COLS_PER_ROW]
        cols = st.columns(COLS_PER_ROW)
        for col, prod in zip(cols, row_products):
            with col:
                render_product_card(prod, user_wishlist_ids, current_user)


# =============================================================================
# 2. WISHLIST MANAGEMENT
# =============================================================================

def render_wishlist_page():
    """
    Renders the user's saved wishlist items stored in the SQLite 'wishlist' table.
    """
    st.markdown("## 💖 My Wishlist")
    st.caption("Keep track of your favorite thrifted finds before they're gone!")

    current_user = st.session_state.get("user")
    if not current_user:
        st.warning("⚠️ Please log in to view and manage your saved wishlist.")
        return

    # Fetch wishlist products using parameterized JOIN
    wishlist_items = fetch_all(
        """
        SELECT p.* FROM products p
        JOIN wishlist w ON p.product_id = w.product_id
        WHERE w.user_id = ?
        ORDER BY w.wishlist_id DESC
        """,
        (current_user["user_id"],)
    )

    if not wishlist_items:
        st.info("Your wishlist is currently empty. Browse the marketplace and tap 💖 to save items for later!")
        return

    st.markdown(f"**You have {len(wishlist_items)} saved item(s)**")

    user_wishlist_ids = {p["product_id"] for p in wishlist_items}

    # Render Wishlist Grid
    COLS_PER_ROW = 3
    for i in range(0, len(wishlist_items), COLS_PER_ROW):
        row_items = wishlist_items[i:i + COLS_PER_ROW]
        cols = st.columns(COLS_PER_ROW)
        for col, item in zip(cols, row_items):
            with col:
                render_product_card(item, user_wishlist_ids, current_user)


# =============================================================================
# 3. SHOPPING CART (SESSION STATE)
# =============================================================================

def render_cart_page():
    """
    Renders the shopping cart stored in st.session_state['cart'].
    Allows item removal, shows itemized subtotal, and links to checkout.
    """
    st.markdown("## 🛒 Shopping Cart")
    st.caption("Review your pre-loved picks and proceed to eco-friendly checkout.")

    current_user = st.session_state.get("user")
    if not current_user:
        st.warning("⚠️ Please sign in to access your shopping cart.")
        return

    cart = st.session_state.get("cart", [])
    if not cart:
        st.info("Your cart is empty! Head over to the Marketplace to discover unique vintage & pre-loved styles.")
        return

    # Fetch product details for all IDs currently in cart
    placeholders = ",".join(["?"] * len(cart))
    cart_products = fetch_all(
        f"SELECT * FROM products WHERE product_id IN ({placeholders})",
        tuple(cart)
    )

    # Detect if any item was purchased by another buyer
    available_items = [p for p in cart_products if p["status"] == "available"]
    sold_items = [p for p in cart_products if p["status"] != "available"]

    if sold_items:
        st.warning("⚠️ Note: One or more items in your cart were recently sold to another buyer and cannot be checked out.")

    col_items, col_summary = st.columns([3, 2])

    with col_items:
        st.markdown(f"### Items in Cart ({len(cart_products)})")

        for item in cart_products:
            with st.container(border=True):
                c_img, c_info, c_action = st.columns([1, 3, 1])

                with c_img:
                    img_path = os.path.join(BASE_DIR, item["image_path"]) if item.get("image_path") else None
                    if img_path and os.path.exists(img_path):
                        st.image(img_path, width=80)
                    else:
                        st.markdown("👕")

                with c_info:
                    st.markdown(f"**{item['title']}**")
                    st.caption(f"Category: {item['category']} | Size: {item['size']}")
                    if item["status"] == "available":
                        st.markdown(f"**₹{item['price']:.2f}**")
                    else:
                        st.markdown(f"<span style='color:red;'>Sold Out</span> - ₹{item['price']:.2f}", unsafe_allow_html=True)

                with c_action:
                    if st.button("🗑️ Remove", key=f"remove_cart_{item['product_id']}"):
                        st.session_state["cart"].remove(item["product_id"])
                        st.toast(f"Removed '{item['title']}' from cart.")
                        st.rerun()

        if st.button("🧹 Clear Entire Cart"):
            st.session_state["cart"] = []
            st.toast("Cart cleared.")
            st.rerun()

    # Order Summary Sidebar Card
    with col_summary:
        with st.container(border=True):
            st.markdown("### 📋 Order Summary")
            st.divider()

            subtotal = sum(p["price"] for p in available_items)
            eco_packaging = 0.0  # Free eco-friendly packaging
            delivery_fee = 0.0   # Free sustainable carbon-neutral shipping

            s_col1, s_col2 = st.columns([2, 1])
            with s_col1:
                st.write(f"Subtotal ({len(available_items)} available items):")
                st.write("Eco-Friendly Packaging:")
                st.write("Carbon-Neutral Delivery:")
            with s_col2:
                st.write(f"₹{subtotal:.2f}")
                st.write("FREE")
                st.write("FREE")

            st.divider()
            t_col1, t_col2 = st.columns([2, 1])
            with t_col1:
                st.markdown("#### **Total Amount:**")
            with t_col2:
                st.markdown(f"#### **₹{subtotal:.2f}**")

            st.caption("🌱 By choosing ReWear, this order diverts textile waste from landfills!")

            # Checkout Trigger Button
            if not available_items:
                st.button("Checkout Unavailable", disabled=True, use_container_width=True)
            else:
                if st.button("🚀 Proceed to Checkout", type="primary", use_container_width=True):
                    # Set navigation to checkout page in orders.py
                    st.session_state["page"] = "checkout"
                    st.rerun()
