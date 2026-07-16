LOGIN_URL = "https://support.amlogic.com/login"
USERNAME = "input[name='username']"
PASSWORD = "input[name='password']"
LOGIN_SUBMIT = "input[name='login']"
TWOFA_PATH = "/account/twofa/confirm"
TWOFA_CODE_INPUT = "input#twofa_code[name='twofa_code'][autocomplete='one-time-code']"
TWOFA_SUBMIT = "input[name='submit_otp'][type='submit']"
VERIFICATION_INPUT = TWOFA_CODE_INPUT
VERIFICATION_SUBMIT = TWOFA_SUBMIT
AUTHENTICATED_PROJECT_LINK = "a[href^='/projects/']"
AUTHENTICATED_EVIDENCE = ("a.logout", "a[href*='/logout']", AUTHENTICATED_PROJECT_LINK)
CREDENTIAL_ERRORS = (".flash.error:has-text('Invalid user or password')", ".flash.error:has-text('Invalid credentials')")
VERIFICATION_EVIDENCE = (TWOFA_CODE_INPUT,)
INCORRECT_VERIFICATION_EVIDENCE = (
    ".flash.error:has-text('verification code')",
    ".flash.error:has-text('incorrect code')",
    "#otp-error",
)
