"""
=============================================================================
app.py - Main Streamlit Application for ReWear ♻️
=============================================================================
ReWear: Sustainable Pre-Loved Clothes Reselling Platform
Designed for a 2nd-year BTech Mini-Project.

Built strictly using:
- Python 3
- Streamlit (Web UI, Session State & Component rendering)
- SQLite3 (Relational Database with 5 tables & Parameterized Queries)
- Pillow (Image handling, resizing, and placeholder creation)

This file acts as the coordinator / router for the multi-module application.
=============================================================================
"""

import streamlit as st

# 1. Page Configuration (Eco-Green Theme, Responsive Layout)
st.set_page_config(
    page_title="ReWear ♻️ - Give Pre-Loved Clothes a Second Life",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Import Application Modules
from database import init_db, fetch_all
from auth import render_auth_page, logout_user
from products import render_add_product_page
from wishlist_cart import render_marketplace, render_wishlist_page, render_cart_page
from orders import render_checkout_page, render_order_history_page, render_seller_dashboard, render_admin_panel
from donations import render_donate_page


# =============================================================================
# 3. CUSTOM ECO-GREEN CSS STYLING
# =============================================================================
st.markdown(
    """
    <style>
    /* Clean Green Accents */
    :root {
        --primary-green: #2E7D32;
        --secondary-green: #4CAF50;
        --light-green-bg: #E8F5E9;
    }
    
    /* Eco Banner Header */
    .eco-header {
        background: linear-gradient(135deg, #1B5E20, #388E3C);
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    }
    .eco-header h1 {
        margin: 0;
        font-size: 2rem;
        color: white;
    }
    .eco-header p {
        margin: 0.3rem 0 0 0;
        font-size: 1rem;
        opacity: 0.95;
    }

    /* Product Card Border & Hover Effect */
    div[data-testid="stVerticalBlock"] > div[data-testid="stContainer"] {
        border-radius: 10px;
        transition: transform 0.15s ease-in-out;
    }

    /* Sidebar Badge */
    .user-badge {
        background-color: #E8F5E9;
        color: #1B5E20;
        padding: 0.4rem 0.8rem;
        border-radius: 20px;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# =============================================================================
# 4. SESSION STATE INITIALIZATION & DATABASE VERIFICATION
# =============================================================================

# Initialize SQLite database and seed initial demo data if needed
init_db()

# Initialize session state variables if not already set
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if "user" not in st.session_state:
    st.session_state["user"] = None

if "cart" not in st.session_state:
    st.session_state["cart"] = []

if "page" not in st.session_state:
    st.session_state["page"] = "marketplace"


# =============================================================================
# 5. SIDEBAR NAVIGATION & USER STATUS
# =============================================================================

with st.sidebar:
    # App Branding
    st.markdown("## ♻️ **ReWear**")
    st.caption("Sustainable Pre-Loved Clothes Marketplace")
    st.divider()

    # User Status Box
    current_user = st.session_state.get("user")
    cart_count = len(st.session_state.get("cart", []))
    
    # Calculate Wishlist Count for Logged-in User
    wishlist_count = 0
    if current_user:
        w_rows = fetch_all("SELECT COUNT(*) as count FROM wishlist WHERE user_id = ?", (current_user["user_id"],))
        wishlist_count = w_rows[0]["count"] if w_rows else 0

    if current_user:
        role_emojis = {"buyer": "🛍️", "seller": "🏪", "admin": "🛡️"}
        user_role = current_user["role"]
        emoji = role_emojis.get(user_role, "👤")
        
        st.markdown(
            f"""
            <div class="user-badge">
                {emoji} {current_user['name']} ({user_role.capitalize()})
            </div>
            """,
            unsafe_allow_html=True
        )
        st.caption(f"Email: `{current_user['email']}`")
    else:
        st.info("👋 You are browsing as a **Guest**.")

    # Navigation Menu Items (Constructed dynamically based on current user role)
    nav_items = [("marketplace", "🛍️ Browse Clothes")]

    if current_user:
        nav_items.append(("wishlist", f"💖 My Wishlist ({wishlist_count})"))
        nav_items.append(("cart", f"🛒 Shopping Cart ({cart_count})"))
        nav_items.append(("orders", "📦 Order History"))
        nav_items.append(("donate", "♻️ Donate / Recycle"))

        # Seller & Admin capabilities
        if current_user["role"] in ("seller", "admin"):
            nav_items.append(("add_product", "➕ List Clothing Item"))
            nav_items.append(("seller_dashboard", "📊 Seller Dashboard"))

        # Admin exclusive capabilities
        if current_user["role"] == "admin":
            nav_items.append(("admin_panel", "🛡️ Admin Panel"))
    else:
        nav_items.append(("cart", f"🛒 Shopping Cart ({cart_count})"))
        nav_items.append(("auth", "🔐 Sign In / Register"))

    # Extract list of page keys and their human-friendly labels
    menu_options = [page_id for page_id, _ in nav_items]
    page_labels = {page_id: label for page_id, label in nav_items}

    # Resolve safe radio index
    current_page = st.session_state.get("page", "marketplace")

    # If user is in checkout flow, highlight 'cart' in the menu
    target_page = "cart" if current_page == "checkout" else current_page

    # Ensure index is always valid for the CURRENT menu_options list
    if target_page in menu_options:
        safe_index = menu_options.index(target_page)
    else:
        # Fallback to index 0 (marketplace) if page is not in this role's menu
        safe_index = 0
        if current_page != "checkout":
            st.session_state["page"] = menu_options[0]
            current_page = menu_options[0]

    # Double safeguard: clamp safe_index strictly within [0, len(menu_options) - 1]
    safe_index = max(0, min(safe_index, len(menu_options) - 1))

    # Render navigation radio with format_func
    selected_page = st.radio(
        "Navigation",
        options=menu_options,
        index=safe_index,
        format_func=lambda pid: page_labels.get(pid, pid)
    )

    # When user actively clicks a different menu option, update session state
    # (Avoid overwriting 'checkout' when radio defaults to 'cart')
    if selected_page != current_page and not (current_page == "checkout" and selected_page == "cart"):
        st.session_state["page"] = selected_page
        st.rerun()

    st.divider()

    # Log Out or Quick Sign-In Option
    if current_user:
        if st.button("🚪 Log Out", use_container_width=True):
            logout_user()
    else:
        if current_page != "auth":
            if st.button("🔑 Log In / Register", use_container_width=True):
                st.session_state["page"] = "auth"
                st.rerun()

    # Sustainability Impact Counter
    st.markdown("---")
    st.markdown("### 🌍 ReWear Eco Impact")
    st.caption("Every used garment purchased prevents approximately **2.6 kg of CO2** and saves **2,700 liters of water**! 💧")


# =============================================================================
# 6. HEADER BANNER
# =============================================================================

st.markdown(
    """
    <div class="eco-header">
        <h1>ReWear ♻️</h1>
        <p>Give Pre-Loved Clothes a Second Life • Sustainable, Affordable & Circular Fashion</p>
    </div>
    """,
    unsafe_allow_html=True
)


# =============================================================================
# 7. ROUTING / PAGE RENDERING
# =============================================================================

active_page = st.session_state.get("page", "marketplace")

if active_page == "marketplace":
    render_marketplace()

elif active_page == "wishlist":
    render_wishlist_page()

elif active_page == "cart":
    render_cart_page()

elif active_page == "checkout":
    render_checkout_page()

elif active_page == "orders":
    render_order_history_page()

elif active_page == "donate":
    render_donate_page()

elif active_page == "add_product":
    render_add_product_page()

elif active_page == "seller_dashboard":
    render_seller_dashboard()

elif active_page == "admin_panel":
    render_admin_panel()

elif active_page == "auth":
    render_auth_page()

else:
    # Fallback to marketplace
    render_marketplace()
