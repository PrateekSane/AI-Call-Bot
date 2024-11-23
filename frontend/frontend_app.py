import streamlit as st
import requests

# User information
user_name = "Prateek Sane"
user_email = "prateeksane@gmail.com"
user_phone = "9164729906"

url = 'https://e674-2001-5a8-42a8-7b00-4c18-e257-8329-875a.ngrok-free.app/initiate-call'

# Display user information
st.title("Customer Service Form")
st.markdown(f"""
<style>
.info-card {{
    background-color: #f0f2f6;
    padding: 20px;
    border-radius: 5px;
}}
</style>
<div class="info-card">
    <h3>User Information</h3>
    <p><strong>Name:</strong> {user_name}</p>
    <p><strong>Email:</strong> {user_email}</p>
    <p><strong>Phone Number:</strong> {user_phone}</p>
</div>
""", unsafe_allow_html=True)

# Input fields
st.header("Provide the following information")
customer_service_phone = st.text_input("Customer Service Phone Number", placeholder="Enter the phone number")
reason_for_calling = st.text_area("Reason for calling", placeholder="Describe the reason for calling")

# Additional key-value pairs
st.subheader("Additional Information")

if 'additional_fields' not in st.session_state:
    st.session_state.additional_fields = []

def add_field():
    st.session_state.additional_fields.append({'key': '', 'value': ''})

st.button("\u2795", on_click=add_field)

for i, field in enumerate(st.session_state.additional_fields):
    cols = st.columns(2)
    key_input = cols[0].text_input(f"Key {i+1}", value=field['key'], key=f'key_{i}')
    value_input = cols[1].text_input(f"Value {i+1}", value=field['value'], key=f'value_{i}')
    st.session_state.additional_fields[i]['key'] = key_input
    st.session_state.additional_fields[i]['value'] = value_input

# Submit button
if st.button("Submit"):
    # Collect data
    data = {
        'user_name': user_name,
        'user_email': user_email,
        'user_phone': user_phone,
        'customer_service_phone': customer_service_phone,
        'reason_for_calling': reason_for_calling,
        'additional_info': {field['key']: field['value'] for field in st.session_state.additional_fields if field['key']}
    }
    st.write("Sending data to API...")
    # Send data to API
    try:
        # Replace 'http://localhost:5000/api/process_form' with your actual API endpoint
        response = requests.post(url, json=data)
        if response.status_code == 200:
            st.success("Data successfully sent to API!")
            st.write("Response from API:")
            st.json(response.json())
        else:
            st.error(f"Error sending data to API. Status code: {response.status_code}")
            st.write(response.text)
    except Exception as e:
        st.error(f"An error occurred: {e}")
