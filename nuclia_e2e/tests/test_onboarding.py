import pytest


@pytest.mark.asyncio_cooperative
async def test_onboarding(
    request, global_api, email_util, test_config, cleanup_test_account, aiohttp_session
):
    # Request signup using a random alias email
    test_alias_email = email_util.generate_email_address()
    test_password = "notarealpassword"
    response = await global_api.signup("Carles Bruguera E2E", test_alias_email, test_password)
    assert response == {"action": "check-mail"}

    # Retrieve a magic token from the signup link received on the test email address. The link is wrapper
    # in a redirection caused by the click tracking of sendgrid.
    email_link = await email_util.wait_for_email_signup_link(test_alias_email)
    async with aiohttp_session.get(email_link, allow_redirects=False) as response:
        assert response.status == 302
        signup_url = response.headers.get("Location")
        signup_magic_token = signup_url.split("token=")[1]
    tokens = await global_api.finalize_signup(signup_magic_token)
    access_token = tokens["token"]["access_token"]

    # Create the account
    global_api.set_access_token(access_token)
    # the email used on this tests is filtered on the platform to avoid spamming attio, so we don't care about the actual
    # data sent here, as is only a proxy for attio, and all data is optional
    await global_api.send_onboard_inquiry({})
    await global_api.create_account(test_config["test_account_slug"])
