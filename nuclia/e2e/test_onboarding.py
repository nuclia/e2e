import requests

def test_onboarding(global_api, email_util, test_config, cleanup_test_account):
    # Request signup using a random alias email
    test_alias_email = email_util.generate_email_address()
    test_password = "notarealpassword"
    response = global_api.signup("Carles Bruguera E2E", test_alias_email, test_password)
    assert response == {"action": "check-mail"}

    # Retrieve a magic token from the signup link received on the test email address. The link is wrapper
    # in a redirection caused by the click tracking of sendgrid.
    email_link = email_util.wait_for_email_signup_link(test_alias_email)
    assert email_link is not None
    response = requests.get(email_link, allow_redirects=False)
    signup_url = response.headers.get("Location")
    signup_magic_token = signup_url.split("token=")[1]
    tokens = global_api.finalize_signup(signup_magic_token)
    access_token = tokens["token"]["access_token"]

    print(access_token)

    # Create the account
    global_api.set_access_token(access_token)
    global_api.send_onboard_inquiry()
    global_api.create_account(test_config["test_account_slug"])
