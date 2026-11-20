"""
=============================================================================
auth.py - Authentication Module for ReWear (Register & Login)
=============================================================================
This module handles:
1. Secure password hashing using PBKDF2-HMAC-SHA256 with a unique cryptographic salt.
2. Form validation (empty inputs, valid email format, matching passwords).
3. Registration into the 'users' table with roles ('buyer', 'seller', 'admin').
4. Login verification and Streamlit session state management.
5. Quick Demo Account shortcuts for easy project demonstration & viva examination.
=============================================================================
"""

import os
import re
import hmac
import hashlib
import streamlit as st
from database import execute_query, fetch_one


# =============================================================================
# 1. SECURITY & PASSWORD HASHING (PBKDF2 + Salt)
# =============================================================================

def hash_password(password: str) -> str:
    """
    Hashes a plain-text password using PBKDF2-HMAC-SHA256 with 100,000 iterations
    and a randomly generated 16-byte cryptographic salt.
    Format stored in DB: '<salt_hex>$<hash_hex>'
    Never stores plain text passwords!
    """
    salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        iterations=100000
    )
    return f"{salt}${key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verifies a plain-text password against a stored '<salt>$<hash>' string.
    Uses constant-time comparison (hmac.compare_digest) to prevent timing attacks.
    """
    try:
        salt, key_hex = stored_hash.split("$", 1)
        new_key = hashlib.pbkdf2_hmac(
            hash_name="sha256",
            password=password.encode("utf-8"),
            salt=salt.encode("utf-8"),
            iterations=100000
        )
        return hmac.compare_digest(new_key.hex(), key_hex)
    except Exception:
        return False


def is_valid_email(email: str) -> bool:
    """
    Validates standard email address format using regex.
    """
    email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.match(email_regex, email.strip()))


# =============================================================================
# 2. SESSION STATE HELPERS
# =============================================================================

def login_user(user_dict: dict):
    """
    Stores authenticated user info in Streamlit session state and reruns app.
    """
    st.session_state["logged_in"] = True
    st.session_state["user"] = {
        "user_id": user_dict["user_id"],
        "name": user_dict["name"],
        "email": user_dict["email"],
        "role": user_dict["role"]
    }
    if "cart" not in st.session_state:
        st.session_state["cart"] = []
    # Redirect cleanly to marketplace upon login
    st.session_state["page"] = "marketplace"
    st.success(f"Welcome back, **{user_dict['name']}**! Logged in as **{user_dict['role'].capitalize()}**.")
    st.rerun()


def logout_user():
    """
    Clears user session state on logout.
    """
    st.session_state["logged_in"] = False
    st.session_state["user"] = None
    st.session_state["cart"] = []
    # Reset page back to marketplace for guest
    st.session_state["page"] = "marketplace"
    st.info("You have been successfully logged out.")
    st.rerun()


# =============================================================================
# 3. USER INTERFACE (RENDER AUTH PAGE)
# =============================================================================

def render_auth_page():
    """
    Renders the Authentication Screen with Tabs for Login and Registration.
    Includes quick-fill demo credentials for smooth presentations.
    """
    st.markdown("## 🔐 Account Access")
    st.caption("Sign in to buy, sell, manage your wishlist, or view order history.")

    tab_login, tab_register = st.tabs(["🔑 Sign In", "📝 Create New Account"])

    # -------------------------------------------------------------------------
    # TAB 1: LOGIN
    # -------------------------------------------------------------------------
    with tab_login:
        st.subheader("Welcome to ReWear ♻️")
        
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email Address", placeholder="e.g. buyer@rewear.com")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submit_login = st.form_submit_button("🚀 Log In", use_container_width=True)

            if submit_login:
                # Validation 1: Check empty fields
                if not email.strip() or not password:
                    st.error("⚠️ Please fill in both email and password.")
                elif not is_valid_email(email):
                    st.error("⚠️ Please enter a valid email address.")
                else:
                    # Query user by email using parameterized query
                    user = fetch_one("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
                    if not user:
                        st.error("❌ No account found with this email. Please register first.")
                    else:
                        # Verify PBKDF2 password hash
                        if verify_password(password, user["password_hash"]):
                            login_user(user)
                        else:
                            st.error("❌ Incorrect password. Please try again.")

        # Quick Test Credentials Info Box for Evaluators/Professors
        with st.expander("💡 Mini-Project Demo Accounts (Click to view test logins)"):
            st.markdown("""
            You can use these pre-seeded demo accounts to test different roles:
            - **Buyer Account:** `buyer@rewear.com` | Password: `buyer123`
            - **Seller Account:** `seller@rewear.com` | Password: `seller123`
            - **Admin Account:** `admin@rewear.com` | Password: `admin123`
            """)

    # -------------------------------------------------------------------------
    # TAB 2: REGISTER
    # -------------------------------------------------------------------------
    with tab_register:
        st.subheader("Join the Sustainable Fashion Community")
        
        with st.form("register_form", clear_on_submit=True):
            reg_name = st.text_input("Full Name", placeholder="e.g. Ananya Sen")
            reg_email = st.text_input("Email Address", placeholder="e.g. ananya@example.com")
            
            reg_role = st.selectbox(
                "I want to join primarily as a:",
                options=["buyer", "seller", "admin"],
                format_func=lambda x: {
                    "buyer": "🛍️ Buyer (Browse, Wishlist & Buy Clothes)",
                    "seller": "🏪 Seller (List & Sell Pre-Loved Clothes)",
                    "admin": "🛡️ Admin (System Overview & Management)"
                }.get(x, x)
            )

            reg_pwd = st.text_input("Password (min 6 characters)", type="password")
            reg_confirm_pwd = st.text_input("Confirm Password", type="password")
            
            submit_reg = st.form_submit_button("🌱 Create Account", use_container_width=True)

            if submit_reg:
                # Validation checks
                if not reg_name.strip() or not reg_email.strip() or not reg_pwd:
                    st.error("⚠️ All fields are required.")
                elif not is_valid_email(reg_email):
                    st.error("⚠️ Please enter a valid email address.")
                elif len(reg_pwd) < 6:
                    st.error("⚠️ Password must be at least 6 characters long.")
                elif reg_pwd != reg_confirm_pwd:
                    st.error("⚠️ Passwords do not match.")
                else:
                    # Check if email is already registered (parameterized query)
                    existing = fetch_one("SELECT user_id FROM users WHERE email = ?", (reg_email.strip().lower(),))
                    if existing:
                        st.error("❌ An account with this email already exists. Please log in.")
                    else:
                        # Hash password with salt
                        pwd_hash = hash_password(reg_pwd)
                        execute_query(
                            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                            (reg_name.strip(), reg_email.strip().lower(), pwd_hash, reg_role)
                        )
                        st.success("🎉 Account created successfully! Please switch to the 'Sign In' tab to log in.")
