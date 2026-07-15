LOGIN_URL = "https://support.amlogic.com/login"
USERNAME = "input[name='username']"
PASSWORD = "input[name='password']"
LOGIN_SUBMIT = "input[name='login']"
VERIFICATION_INPUT = "input[name='verification_code']"
VERIFICATION_SUBMIT = "button[type='submit']"
AUTHENTICATED_EVIDENCE = ("a.logout", "a[href*='/logout']")
CREDENTIAL_ERRORS = (".flash.error:has-text('Invalid user or password')", ".flash.error:has-text('Invalid credentials')")
VERIFICATION_EVIDENCE = (VERIFICATION_INPUT, "input[name='otp']", "input[name='code']")
