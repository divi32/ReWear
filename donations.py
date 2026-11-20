"""
=============================================================================
donations.py - Clothes Donation & Recycling Module for ReWear ♻️
=============================================================================
This module handles:
1. Donating wearable pre-loved garments to charity or recycling worn-out textiles.
2. Form input validation (clothing type, quantity, condition, city, phone).
3. Optional photo upload processed with Pillow (PIL).
4. Viewing user's personal donation & recycling history and pickup status.
5. All operations use parameterized SQL (? placeholders) for full security.
=============================================================================
"""

import os
from datetime import datetime
import streamlit as st
from database import BASE_DIR, execute_query, fetch_all, fetch_one
from products import process_and_save_image

# Standard clothing categories for easy selection
CLOTHING_TYPES = [
    "Everyday Wear (Shirts / T-Shirts / Tops)",
    "Bottomwear (Jeans / Trousers / Skirts)",
    "Winter Wear (Jackets / Sweaters / Shawls)",
    "Ethnic & Festive Wear (Kurtas / Sarees / Dresses)",
    "Kids & Baby Clothes",
    "Mixed Bag / Bulk Clothes (Assorted Items)"
]


def render_donate_page():
    """
    Renders the Donate & Recycle interface for logged-in users.
    Includes a donation request form and a history tracking view.
    """
    st.markdown("## ♻️ Donate & Recycle Clothes")
    st.caption("Prevent textile waste in landfills! Donate wearable clothes to those in need or recycle non-wearable fabrics into new fibers.")

    current_user = st.session_state.get("user")
    if not current_user:
        st.warning("⚠️ Please sign in to submit a donation or clothes recycling request.")
        return

    tab_form, tab_history = st.tabs(["🌱 Request Pickup", "📜 My Donations & Requests"])

    # -------------------------------------------------------------------------
    # TAB 1: DONATION & RECYCLING FORM
    # -------------------------------------------------------------------------
    with tab_form:
        st.subheader("Schedule an Eco-Pickup")

        with st.form("donate_form", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                clothing_type = st.selectbox("Clothing Type *", options=CLOTHING_TYPES)
                quantity = st.number_input("Estimated Quantity (No. of pieces) *", min_value=1, max_value=500, value=3, step=1)
                
                condition = st.radio(
                    "Garment Condition *",
                    options=[
                        "Wearable but donating",
                        "Not wearable - for recycling"
                    ],
                    help="Wearable clothes will be distributed to NGOs/communities. Damaged items will be shredded and recycled into new textile yarn."
                )

            with col2:
                city = st.text_input("Pickup City *", placeholder="e.g. Mumbai, Delhi, Bengaluru, Pune...")
                contact = st.text_input("Contact Phone Number *", placeholder="e.g. 9876543210")
                uploaded_photo = st.file_uploader("Upload Photo of Clothes (Optional)", type=["jpg", "jpeg", "png", "webp"])

            # Eco Information Banner
            st.info("🌿 **Eco Impact:** ReWear partners with local recycling facilities and verified charity partners. Pickups are free and carbon-neutral!")

            submitted = st.form_submit_button("🌱 Schedule Pickup Request", type="primary", use_container_width=True)

            if submitted:
                # Validation
                clean_city = city.strip()
                clean_contact = contact.strip()

                if not clean_city:
                    st.error("⚠️ Please specify your pickup city.")
                elif not clean_contact or len(clean_contact) < 10:
                    st.error("⚠️ Please provide a valid 10-digit contact phone number.")
                elif quantity <= 0:
                    st.error("⚠️ Quantity must be at least 1 item.")
                else:
                    try:
                        # Process optional image with Pillow if provided
                        saved_img_path = None
                        if uploaded_photo:
                            saved_img_path = process_and_save_image(uploaded_photo)

                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        # Parameterized SQL query
                        execute_query(
                            """
                            INSERT INTO donations (user_id, type, quantity, condition, city, contact, image_path, status, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', ?)
                            """,
                            (
                                current_user["user_id"],
                                clothing_type,
                                int(quantity),
                                condition,
                                clean_city,
                                clean_contact,
                                saved_img_path,
                                now_str
                            )
                        )

                        st.balloons()
                        st.success("🎉 Thank you! Your donation/recycling pickup request has been scheduled.")
                        st.info(f"📍 City: **{clean_city}** | 📞 Contact: **{clean_contact}** | Status: **🟡 Pending Pickup**")
                        st.caption("You can check the live status of your pickup under the 'My Donations & Requests' tab.")

                    except Exception as e:
                        st.error(f"❌ Failed to submit request: {str(e)}")

    # -------------------------------------------------------------------------
    # TAB 2: USER'S DONATION HISTORY
    # -------------------------------------------------------------------------
    with tab_history:
        st.subheader("Your Donation & Recycling History")

        user_donations = fetch_all(
            "SELECT * FROM donations WHERE user_id = ? ORDER BY donation_id DESC",
            (current_user["user_id"],)
        )

        if not user_donations:
            st.info("You haven't scheduled any donations yet. Have old clothes sitting in your closet? Schedule a free eco-pickup!")
        else:
            for don in user_donations:
                with st.container(border=True):
                    col_img, col_info, col_status = st.columns([1, 3, 1])

                    with col_img:
                        if don.get("image_path"):
                            full_path = os.path.join(BASE_DIR, don["image_path"])
                            if os.path.exists(full_path):
                                st.image(full_path, width=80)
                            else:
                                st.markdown("📦")
                        else:
                            st.markdown("👕")

                    with col_info:
                        st.markdown(f"**Request #{don['donation_id']} — {don['type']}**")
                        st.caption(f"Quantity: {don['quantity']} pieces • Submitted on: {don['created_at']}")
                        st.write(f"**Condition:** `{don['condition']}`")
                        st.write(f"**Pickup City:** {don['city']} | **Contact:** {don['contact']}")

                    with col_status:
                        if don["status"] == "Collected":
                            st.markdown("### 🟢 Collected")
                            st.caption("Collected & Processed ✓")
                        else:
                            st.markdown("### 🟡 Pending")
                            st.caption("Awaiting Pickup")
