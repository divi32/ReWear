"""
=============================================================================
products.py - Product Management and Marketplace Browsing for ReWear
=============================================================================
This module handles:
1. Sellers listing pre-loved clothes (Title, Category, Size, Price, Image).
2. Image upload processing and resizing using Pillow (PIL).
3. Displaying available clothes in a responsive, attractive card grid.
4. Quick actions: Add to Cart, Toggle Wishlist, View Details.
5. All database operations strictly use parameterized queries (? placeholders).
=============================================================================
"""

import os
from datetime import datetime
from PIL import Image
import streamlit as st
from database import DB_PATH, BASE_DIR, UPLOADS_DIR, execute_query, fetch_all, fetch_one


# =============================================================================
# 1. IMAGE PROCESSING WITH PILLOW
# =============================================================================

def process_and_save_image(uploaded_file) -> str:
    """
    Takes an uploaded image file from Streamlit, processes it with Pillow:
    - Converts RGBA/P to RGB for safe JPEG saving.
    - Resizes/thumbnails to maximum 600x600 px preserving aspect ratio.
    - Saves into uploads/ folder with timestamped unique filename.
    Returns the relative path string (e.g., 'uploads/filename.jpg').
    """
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    
    # Generate safe unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_original_name = os.path.splitext(uploaded_file.name)[0].replace(" ", "_")
    filename = f"{timestamp}_{clean_original_name}.jpg"
    save_path = os.path.join(UPLOADS_DIR, filename)

    # Process with Pillow
    image = Image.open(uploaded_file)
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    
    # Thumbnail scales down proportionally without distorting aspect ratio
    image.thumbnail((600, 600), Image.Resampling.LANCZOS)
    image.save(save_path, format="JPEG", quality=85)

    return os.path.join("uploads", filename)


# =============================================================================
# 2. SELLER LISTING FORM (ADD PRODUCT)
# =============================================================================

CATEGORIES = [
    "T-Shirts", "Shirts", "Jeans", "Bottoms",
    "Dresses", "Jackets", "Hoodies", "Sweaters",
    "Ethnic Wear", "Activewear", "Accessories"
]

SIZES = ["XS", "S", "M", "L", "XL", "XXL", "Free Size", "28", "30", "32", "34", "36"]


def render_add_product_page():
    """
    Form allowing registered Sellers and Admins to list pre-loved clothes.
    Validates all inputs (no blank title, positive price, valid image).
    """
    st.markdown("## ➕ List Pre-Loved Clothes for Sale")
    st.caption("Give your gently used garments a second life and earn money while saving the planet 🌍")

    # Access control check
    user = st.session_state.get("user")
    if not user or user.get("role") not in ("seller", "admin"):
        st.warning("⚠️ Only registered Sellers or Admins can list products. Please log in with a seller account.")
        return

    with st.form("add_product_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            title = st.text_input("Clothing Title *", placeholder="e.g. Levi's Slim Fit Denim Jacket")
            category = st.selectbox("Category *", options=CATEGORIES)
            size = st.selectbox("Size *", options=SIZES)

        with col2:
            price = st.number_input("Selling Price (₹) *", min_value=10.0, max_value=50000.0, value=499.0, step=50.0)
            uploaded_image = st.file_uploader("Upload Product Photo * (JPG, PNG)", type=["jpg", "jpeg", "png", "webp"])

        st.info("💡 Tip: Upload clear, well-lit photos. Images are automatically resized with Pillow for optimal display.")

        submitted = st.form_submit_button("🌱 Publish Listing", use_container_width=True)

        if submitted:
            # Field Validation
            if not title.strip():
                st.error("⚠️ Title cannot be empty.")
            elif price <= 0:
                st.error("⚠️ Price must be greater than zero.")
            elif not uploaded_image:
                st.error("⚠️ Please upload an image for your clothing item.")
            else:
                try:
                    # Resize and save image with Pillow
                    saved_rel_path = process_and_save_image(uploaded_image)

                    # Parameterized INSERT into products table
                    execute_query(
                        """
                        INSERT INTO products (seller_id, title, category, size, price, image_path, status)
                        VALUES (?, ?, ?, ?, ?, ?, 'available')
                        """,
                        (user["user_id"], title.strip(), category, size, float(price), saved_rel_path)
                    )

                    st.success(f"🎉 Listing '{title.strip()}' published successfully!")
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ Failed to publish listing: {str(e)}")


# =============================================================================
# 3. PRODUCT CARD COMPONENT
# =============================================================================

def render_product_card(product: dict, user_wishlist_ids: set, current_user: dict):
    """
    Renders a single product card with image, details, and actionable buttons.
    """
    with st.container(border=True):
        # Resolve image path
        image_path = product.get("image_path")
        full_image_path = os.path.join(BASE_DIR, image_path) if image_path else None

        if full_image_path and os.path.exists(full_image_path):
            st.image(full_image_path, use_container_width=True)
        else:
            # Fallback decorative box if image is missing
            st.markdown(
                """
                <div style="background:#f0f4f0;height:200px;display:flex;align-items:center;
                            justify-content:center;border-radius:8px;color:#2E7D32;font-size:24px;">
                    👕 ReWear Item
                </div>
                """,
                unsafe_allow_html=True
            )

        # Title & Badges
        st.markdown(f"### {product['title']}")
        
        # Category and Size badges
        st.markdown(
            f"`🏷️ {product['category']}` &nbsp; `📏 Size: {product['size']}`",
            unsafe_allow_html=True
        )

        # Price and Status
        col_price, col_status = st.columns([1, 1])
        with col_price:
            st.markdown(f"#### ₹{product['price']:.2f}")
        with col_status:
            if product["status"] == "available":
                st.markdown("🟢 **Available**")
            else:
                st.markdown("🔴 **Sold Out**")

        st.divider()

        # Action Buttons (Wishlist & Cart)
        btn_col1, btn_col2 = st.columns(2)

        # 1. Wishlist Button
        is_wishlisted = product["product_id"] in user_wishlist_ids
        wishlist_label = "💔 Remove" if is_wishlisted else "💖 Wishlist"
        
        with btn_col1:
            if st.button(wishlist_label, key=f"wish_{product['product_id']}", use_container_width=True):
                if not current_user:
                    st.warning("Please log in to manage your wishlist.")
                else:
                    if is_wishlisted:
                        execute_query(
                            "DELETE FROM wishlist WHERE user_id = ? AND product_id = ?",
                            (current_user["user_id"], product["product_id"])
                        )
                        st.toast(f"Removed '{product['title']}' from wishlist.")
                    else:
                        execute_query(
                            "INSERT OR IGNORE INTO wishlist (user_id, product_id) VALUES (?, ?)",
                            (current_user["user_id"], product["product_id"])
                        )
                        st.toast(f"Added '{product['title']}' to wishlist!")
                    st.rerun()

        # 2. Add to Cart Button
        with btn_col2:
            cart = st.session_state.get("cart", [])
            in_cart = product["product_id"] in cart
            is_sold = product["status"] != "available"

            if is_sold:
                st.button("Sold Out", key=f"cart_{product['product_id']}", disabled=True, use_container_width=True)
            elif in_cart:
                st.button("In Cart ✓", key=f"cart_{product['product_id']}", disabled=True, use_container_width=True)
            else:
                if st.button("🛒 Add Cart", key=f"cart_{product['product_id']}", use_container_width=True):
                    if not current_user:
                        st.warning("Please sign in to add items to your cart.")
                    else:
                        if "cart" not in st.session_state:
                            st.session_state["cart"] = []
                        st.session_state["cart"].append(product["product_id"])
                        st.toast(f"🛒 Added '{product['title']}' to your cart!")
                        st.rerun()

        # Expandable Details
        with st.expander("ℹ️ Item Details"):
            seller = fetch_one("SELECT name, email FROM users WHERE user_id = ?", (product["seller_id"],))
            seller_name = seller["name"] if seller else "Verified Seller"
            st.write(f"**Seller:** {seller_name}")
            st.write(f"**Item ID:** #{product['product_id']}")
            st.write(f"**Category:** {product['category']}")
            st.write(f"**Size:** {product['size']}")
            st.write("**Environmental Impact:** Saves ~2,700 liters of water compared to buying new! 💧")
